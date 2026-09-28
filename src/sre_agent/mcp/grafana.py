"""Grafana MCP tool. Required fields match query_prometheus."""

from typing import Any

from sre_agent.mcp.tool import McpTool

SERIES = {
    "checkout-api": {
        "error_rate": {
            "current": 0.08,
            "baseline": 0.002,
            "rose_at": "2026-09-25T00:29:00Z",
        },
        "latency_p95_ms": {"current": 1200, "baseline": 180},
        "request_rate_rps": {"current": 410, "baseline": 400},
        "cpu_utilization": {"current": 0.41, "baseline": 0.38},
    },
    "search-api": {
        "error_rate": {"current": 0.004, "baseline": 0.003},
        "latency_p95_ms": {
            "current": 1450,
            "baseline": 220,
            "rose_at": "2026-09-25T09:02:00Z",
        },
        "request_rate_rps": {
            "current": 3100,
            "baseline": 950,
            "rose_at": "2026-09-25T09:00:00Z",
        },
        "cpu_utilization": {"current": 0.97, "baseline": 0.45},
        "replicas": {"current": 4, "max": 12},
    },
    "orders-api": {
        "error_rate": {
            "current": 0.031,
            "baseline": 0.001,
            "rose_at": "2026-09-25T13:01:00Z",
        },
        "latency_p95_ms": {"current": 2900, "baseline": 240},
        "request_rate_rps": {"current": 520, "baseline": 510},
        "cpu_utilization": {"current": 0.35, "baseline": 0.33},
        "upstream_errors": {
            "payments-db": "connection pool timeout",
            "share_of_5xx": 0.94,
        },
    },
}


def query_prometheus(args: dict[str, Any]) -> dict[str, Any]:
    if args.get("queryType") == "range" and not (
        args.get("startTime") and args.get("stepSeconds")
    ):
        raise ValueError(
            "startTime and stepSeconds are required when queryType is range"
        )
    if args["datasourceUid"] != "prom-prod":
        raise ValueError(f"datasource {args['datasourceUid']} not found")
    expr = str(args["expr"])
    matched = [service for service in SERIES if service in expr]
    return {
        "data": {
            "result": [
                {
                    "metric": {"service": service},
                    "values": list(SERIES[service].items()),
                }
                for service in matched
            ]
        }
    }


TOOLS = [
    McpTool(
        name="query_prometheus",
        description="How is the service behaving? Error rate, p95 latency, traffic, CPU, replicas, and upstream errors vs baseline. Tells load or saturation apart from a code change or a failing dependency.",
        fn=query_prometheus,
        input_schema={
            "type": "object",
            "properties": {
                "datasourceUid": {
                    "type": "string",
                    "description": "The UID of the Prometheus datasource. Production is prom-prod.",
                },
                "expr": {
                    "type": "string",
                    "description": 'The PromQL expression. Filter by the service label, for example service="checkout-api"; a query without it returns no series.',
                },
                "endTime": {
                    "type": "string",
                    "description": "End of the query window, RFC3339 or relative such as now. Use the incident created_at.",
                },
                "startTime": {
                    "type": "string",
                    "description": "Start of the query window. Required when queryType is range.",
                },
                "stepSeconds": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Step in seconds. Required when queryType is range.",
                },
                "queryType": {
                    "type": "string",
                    "enum": ["instant", "range"],
                    "description": "Instant or range query. Defaults to instant.",
                },
            },
            "required": ["datasourceUid", "expr", "endTime"],
            "additionalProperties": False,
        },
    ),
]
