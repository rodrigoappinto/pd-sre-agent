"""GitLab MCP tool. Required fields match list_deployments."""

from typing import Any
from urllib.parse import unquote

from sre_agent.mcp.tool import McpTool

DEPLOYMENTS = {
    "checkout-api": {
        "deployments": [
            {
                "id": 4821,
                "status": "success",
                "ref": "main",
                "sha": "a1b2c3d",
                "created_at": "2026-09-25T00:28:00Z",
                "environment": {"name": "production"},
                "deployable": {
                    "commit": {
                        "title": "Retry change that treats HTTP 409 from payments-db as success.",
                        "web_url": "https://gitlab.example/acme/checkout-api/-/commit/a1b2c3d",
                    }
                },
            }
        ]
    },
    "search-api": {
        "deployments": [
            {
                "id": 4790,
                "status": "success",
                "ref": "main",
                "sha": "9f8e7d6",
                "created_at": "2026-09-22T14:02:00Z",
                "environment": {"name": "production"},
                "deployable": {
                    "commit": {
                        "title": "Bump search client timeout logging.",
                        "web_url": "https://gitlab.example/acme/search-api/-/commit/9f8e7d6",
                    }
                },
            }
        ]
    },
    "orders-api": {
        "deployments": [
            {
                "id": 4655,
                "status": "success",
                "ref": "main",
                "sha": "3c4d5e6",
                "created_at": "2026-09-18T10:40:00Z",
                "environment": {"name": "production"},
                "deployable": {
                    "commit": {
                        "title": "Add order export endpoint.",
                        "web_url": "https://gitlab.example/acme/orders-api/-/commit/3c4d5e6",
                    }
                },
            }
        ]
    },
}


def list_deployments(args: dict[str, Any]) -> dict[str, Any]:
    project = unquote(str(args["project_id"])).rstrip("/").split("/")[-1]
    deployments = DEPLOYMENTS.get(project, {"deployments": []})["deployments"]
    if "environment" in args:
        deployments = [
            item
            for item in deployments
            if item["environment"]["name"] == args["environment"]
        ]
    if "status" in args:
        deployments = [item for item in deployments if item["status"] == args["status"]]
    return {"deployments": deployments[: args.get("per_page", 20)]}


TOOLS = [
    McpTool(
        name="list_deployments",
        description="Did code change shortly before the incident? Deployments with SHA, time, and commit title.",
        fn=list_deployments,
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path. Each PagerDuty service maps to the project acme/<service name>, for example acme%2Fcheckout-api.",
                },
                "environment": {
                    "type": "string",
                    "description": "Only deployments to this environment, for example production.",
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "created",
                        "running",
                        "success",
                        "failed",
                        "canceled",
                        "blocked",
                    ],
                    "description": "Only deployments with this status.",
                },
                "order_by": {
                    "type": "string",
                    "enum": ["id", "iid", "created_at", "updated_at", "ref"],
                    "description": "Order by this field.",
                },
                "sort": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort direction.",
                },
                "per_page": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Results per page. Defaults to 20.",
                },
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
    ),
]
