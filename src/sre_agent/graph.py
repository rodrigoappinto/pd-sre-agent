"""LangGraph loop with deterministic incident and memory bootstrap."""

import json
import logging

from langgraph.graph import END, START, StateGraph

from sre_agent.gather import run_chosen_tool
from sre_agent.mcp.client import McpClient
from sre_agent.memory import retrieve_for_incident
from sre_agent.models import Decision, IncidentState, ToolChoice

logger = logging.getLogger(__name__)

STEP_BUDGET = 8


def build_graph(reasoner, client: McpClient | None = None, step_budget: int = STEP_BUDGET):
    mcp = client or McpClient()

    def load_incident(state: IncidentState) -> dict:
        logger.info("[bootstrap] loading incident %s", state.incident_id)
        bootstrap = state.model_copy(deep=True)
        bootstrap.step_count += 1
        bootstrap.decision = Decision(
            action="tool",
            tool=ToolChoice(
                server="pagerduty",
                name="get_incident",
                args={"incident_id": state.incident_id},
            ),
        )
        updated = run_chosen_tool(bootstrap, mcp)
        error = updated.observations[-1].error
        return {
            "observations": updated.observations,
            "step_count": updated.step_count,
            "status": "escalated" if error else updated.status,
            "escalate_reason": f"could not load incident: {error}" if error else None,
        }

    def orchestrator(state: IncidentState) -> dict:
        try:
            decision = reasoner(state)
        except ValueError as exc:
            logger.warning("[step %s] model failed: %s", state.step_count + 1, exc)
            return {
                "status": "escalated",
                "escalate_reason": str(exc),
                "step_count": state.step_count + 1,
            }
        if decision.action == "tool" and decision.tool is not None:
            logger.info("[step %s] model chose %s", state.step_count + 1, decision.tool.qualified_name)
        elif decision.proposal is not None:
            logger.info(
                "[step %s] model proposed %s",
                state.step_count + 1,
                decision.proposal.action,
            )
        return {"decision": decision, "step_count": state.step_count + 1, "status": "running"}

    def call_tool(state: IncidentState) -> dict:
        updated = run_chosen_tool(state.model_copy(deep=True), mcp)
        return {
            "observations": updated.observations,
            "status": updated.status,
            "escalate_reason": updated.escalate_reason,
        }

    def retrieve_memory(state: IncidentState) -> dict:
        matches = retrieve_for_incident(state)
        if matches:
            logger.info(
                "[memory] retrieved %s similar incident(s):\n%s",
                len(matches),
                json.dumps([item.model_dump() for item in matches], indent=2),
            )
        else:
            logger.info("[memory] no similar incidents found; continuing with an empty list")
        return {"previous_similar_incidents": matches}

    def propose(state: IncidentState) -> dict:
        proposal = state.decision.proposal if state.decision else None
        if proposal is None:
            return {"status": "escalated", "escalate_reason": "proposal was empty"}
        logger.info("[finish] proposal ready for human approval")
        return {"proposal": proposal, "status": "proposed"}

    def escalate(state: IncidentState) -> dict:
        if state.escalate_reason:
            logger.warning("[finish] escalated: %s", state.escalate_reason)
            return {"status": "escalated"}
        if state.step_count >= step_budget:
            logger.warning("[finish] escalated: step budget exhausted")
            return {"status": "escalated", "escalate_reason": "step budget exhausted"}
        logger.warning("[finish] escalated: stopped without a proposal")
        return {"status": "escalated", "escalate_reason": "stopped without a proposal"}

    def route(state: IncidentState) -> str:
        if state.status == "escalated":
            return "ESCALATE"
        decision = state.decision
        if decision is not None and decision.action == "propose":
            return "PROPOSE"
        if state.step_count >= step_budget:
            return "ESCALATE"
        if decision is not None and decision.action == "tool":
            return "CALL_TOOL"
        return "ESCALATE"

    def route_after_tool(state: IncidentState) -> str:
        if state.status == "escalated":
            return "ESCALATE"
        return "ORCHESTRATOR"

    def route_after_incident(state: IncidentState) -> str:
        if state.status == "escalated":
            return "ESCALATE"
        return "RETRIEVE_MEMORY"

    graph = StateGraph(IncidentState)
    graph.add_node("LOAD_INCIDENT", load_incident)
    graph.add_node("ORCHESTRATOR", orchestrator)
    graph.add_node("CALL_TOOL", call_tool)
    graph.add_node("RETRIEVE_MEMORY", retrieve_memory)
    graph.add_node("PROPOSE", propose)
    graph.add_node("ESCALATE", escalate)
    graph.add_edge(START, "LOAD_INCIDENT")
    graph.add_conditional_edges(
        "LOAD_INCIDENT",
        route_after_incident,
        {"RETRIEVE_MEMORY": "RETRIEVE_MEMORY", "ESCALATE": "ESCALATE"},
    )
    graph.add_conditional_edges(
        "ORCHESTRATOR",
        route,
        {"CALL_TOOL": "CALL_TOOL", "PROPOSE": "PROPOSE", "ESCALATE": "ESCALATE"},
    )
    graph.add_conditional_edges(
        "CALL_TOOL",
        route_after_tool,
        {"ORCHESTRATOR": "ORCHESTRATOR", "ESCALATE": "ESCALATE"},
    )
    graph.add_edge("RETRIEVE_MEMORY", "ORCHESTRATOR")
    graph.add_edge("PROPOSE", END)
    graph.add_edge("ESCALATE", END)
    return graph.compile()


def initial_state(incident_id: str = "PINC2041", tenant_id: str = "acme") -> IncidentState:
    return IncidentState(incident_id=incident_id, tenant_id=tenant_id)
