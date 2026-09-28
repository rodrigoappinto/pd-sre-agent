"""Pydantic models for incident state and the orchestrator decision.

Tool payloads stay plain JSON. These models cover only our own data.
"""

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class Observation(BaseModel):
    """One MCP tool result stored on the incident."""

    tool: str
    payload: dict[str, Any] | None = None
    error: str | None = None


class MemoryHit(BaseModel):
    """One relevant, resolved incident recalled from local memory."""

    incident_id: str
    scope: Literal["private", "global"]
    service: str
    summary: str
    resolution: str
    score: float


class ToolChoice(BaseModel):
    """The next MCP tool the orchestrator wants to call."""

    server: Literal["pagerduty", "gitlab", "grafana"] = Field(description="Tool name before the dot.")
    name: str = Field(description="Tool name after the dot, without the server prefix.")
    args: dict[str, Any] = Field(default_factory=dict, description="Must match the tool's inputSchema.")

    @model_validator(mode="after")
    def unqualified_name(self) -> Self:
        self.name = self.name.removeprefix(f"{self.server}.")
        return self

    @property
    def qualified_name(self) -> str:
        return f"{self.server}.{self.name}"


ActionKind = Literal["rollback_deploy", "scale_service", "pause_job", "manual"]


class Proposal(BaseModel):
    """The next step offered to the responder. Nothing here is executed."""

    rationale: str = Field(
        description="Observed values vs baseline and their timestamps, and which causes they rule out."
    )
    hypothesis: str = Field(description="One sentence: failing component and trigger.")
    action: ActionKind = Field(
        description=(
            "rollback_deploy: a deploy shortly before the alert, seen in an observation. "
            "scale_service: load or saturation. "
            "pause_job: a job overloading a dependency. "
            "manual: a concrete production change none of the others covers, never investigation. "
            "If you only know where the fault is, not what to change, call another tool instead."
        )
    )
    proposed_action: str = Field(
        description='One imperative sentence with the exact SHA, service, replica count, or job. Example: "Scale billing-api from 3 to 6 replicas."'
    )
    needs_human_approval: bool = Field(description="True if the action changes production.")
    summary: str = Field(
        description=(
            "Markdown for the responder: **Issue:** what broke, where, since when, value vs baseline. "
            "**Findings:** 2-4 bullets, each a tool fact tagged [source], including what was ruled out. "
            "**Fix:** the action and whether it needs approval. "
            "**Verify:** metric to watch and its target value. "
            "Only facts tools returned, exact numbers with units, no hedging."
        )
    )


class Decision(BaseModel):
    """One orchestrator turn: either a tool call or a proposal."""

    action: Literal["tool", "propose"] = Field(description="tool: call one tool. propose: analysis finished.")
    tool: ToolChoice | None = Field(default=None, description="Set when action is tool.")
    proposal: Proposal | None = Field(default=None, description="Set when action is propose.")

    @model_validator(mode="after")
    def matching_payload(self) -> Self:
        if self.action == "tool" and (self.tool is None or self.proposal is not None):
            raise ValueError("a tool decision must contain only tool")
        if self.action == "propose" and (self.proposal is None or self.tool is not None):
            raise ValueError("a propose decision must contain only proposal")
        return self


class IncidentState(BaseModel):
    """The incident record the graph passes between nodes."""

    incident_id: str
    tenant_id: str
    observations: list[Observation] = Field(default_factory=list)
    previous_similar_incidents: list[MemoryHit] = Field(default_factory=list)
    decision: Decision | None = None
    proposal: Proposal | None = None
    step_count: int = 0
    status: Literal["running", "proposed", "escalated"] = "running"
    escalate_reason: str | None = None
