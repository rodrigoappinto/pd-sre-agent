"""Run the single tool the orchestrator just chose."""

import json
import logging

from sre_agent.mcp.client import REGISTRY, McpClient
from sre_agent.models import IncidentState, Observation, ToolChoice

logger = logging.getLogger(__name__)

ALLOWLIST = frozenset(REGISTRY)


def run_chosen_tool(state: IncidentState, client: McpClient) -> IncidentState:
    decision = state.decision
    if decision is None or decision.action != "tool" or decision.tool is None:
        state.status = "escalated"
        state.escalate_reason = "orchestrator named no tool"
        return state

    tool = decision.tool
    header = f"[step {state.step_count}] {tool.qualified_name}"
    if tool.qualified_name not in ALLOWLIST:
        logger.warning("%s\n  refused: not on the allowlist\n  args:\n%s\n", header, _block(tool.args))
        state.observations.append(Observation(tool=tool.qualified_name, error="tool is not on the allowlist"))
        return state
    if tool.qualified_name == "pagerduty.get_incident" and already_called(state, tool):
        error = "incident details were already loaded; use the existing observation"
        logger.warning("%s\n  skipped: %s\n", header, error)
        state.observations.append(Observation(tool=tool.qualified_name, error=error))
        return state

    payload, error = client.call_tool(tool.server, tool.name, dict(tool.args))
    if error:
        logger.warning("%s\n  args:\n%s\n  failed: %s\n", header, _block(tool.args), error)
    else:
        logger.info("%s\n  args:\n%s\n  returned:\n%s\n", header, _block(tool.args), _block(payload))
    state.observations.append(Observation(tool=tool.qualified_name, payload=payload, error=error))

    return state


def _block(value: object) -> str:
    return "\n".join(f"    {line}" for line in json.dumps(value, indent=2).splitlines())


def already_called(state: IncidentState, tool: ToolChoice) -> bool:
    return any(item.tool == tool.qualified_name and item.payload is not None for item in state.observations)