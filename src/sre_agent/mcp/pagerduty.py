"""PagerDuty MCP tools. Required fields match the official server."""

from typing import Any

from sre_agent.mcp.tool import McpTool

INCIDENTS = {
    "PINC2041": {
        "id": "PINC2041",
        "incident_number": 2041,
        "title": "checkout-api error rate above 5%",
        "status": "triggered",
        "urgency": "high",
        "service": {"id": "PSVCCHK", "summary": "checkout-api"},
        "created_at": "2026-09-25T00:40:00Z",
    },
    "PINC2052": {
        "id": "PINC2052",
        "incident_number": 2052,
        "title": "search-api p95 latency above 1s",
        "status": "triggered",
        "urgency": "high",
        "service": {"id": "PSVCSRCH", "summary": "search-api"},
        "created_at": "2026-09-25T09:15:00Z",
    },
    "PINC2063": {
        "id": "PINC2063",
        "incident_number": 2063,
        "title": "orders-api 5xx responses above 2%",
        "status": "triggered",
        "urgency": "high",
        "service": {"id": "PSVCORD", "summary": "orders-api"},
        "created_at": "2026-09-25T13:05:00Z",
    },
}


def get_incident(args: dict[str, Any]) -> dict[str, Any]:
    key = args["incident_id"]
    if key not in INCIDENTS:
        raise ValueError(f"incident {key} not found")
    return INCIDENTS[key]


TOOLS = [
    McpTool(
        name="get_incident",
        description="What fired, on which service, how severe, and when.",
        fn=get_incident,
        input_schema={
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "The ID of the incident to retrieve.",
                },
            },
            "required": ["incident_id"],
            "additionalProperties": False,
        },
    ),
]


