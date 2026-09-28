"""Load static instructions and attach MCP tools or incident context."""

import json
from pathlib import Path

from sre_agent.mcp.client import listed_tools
from sre_agent.models import Decision, IncidentState

_PROMPTS = Path(__file__).parent / "prompts"


def system_prompt() -> str:
    text = (_PROMPTS / "sre.md").read_text().strip()
    schema = json.dumps(Decision.model_json_schema(), separators=(",", ":"))
    return f"{text}\n\nMCP tools:\n{listed_tools()}\n\nReply schema:\n{schema}"


def user_message(state: IncidentState) -> str:
    text = (_PROMPTS / "turn.md").read_text().strip()
    context = state.model_dump(
        include={
            "incident_id",
            "tenant_id",
            "step_count",
            "observations",
            "previous_similar_incidents",
        },
        exclude_none=True,
    )
    return f"{text}\n\nIncident context:\n{json.dumps(context, separators=(',', ':'))}"
