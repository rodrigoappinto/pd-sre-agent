"""MCP client. Checks arguments against each tool's inputSchema and parses bodies as JSON."""

import json
from dataclasses import replace
from typing import Any

from jsonschema import Draft202012Validator

from sre_agent.mcp import gitlab, grafana, pagerduty
from sre_agent.mcp.tool import McpTool

REGISTRY: dict[str, McpTool] = {}


def _register(server: str, tools: list[McpTool]) -> None:
    for tool in tools:
        registered = replace(tool, server=server)
        REGISTRY[registered.qualified_name] = registered


_register("pagerduty", pagerduty.TOOLS)
_register("gitlab", gitlab.TOOLS)
_register("grafana", grafana.TOOLS)

BOOTSTRAP_TOOLS = frozenset({"pagerduty.get_incident"})


def list_tools() -> list[dict[str, Any]]:
    """The tools/list result: name, description, and inputSchema for each tool."""
    return [tool.listing() for tool in REGISTRY.values()]


def listed_tools() -> str:
    """Agent-selectable tools attached to the SRE prompt."""
    tools = [
        tool.listing()
        for qualified_name, tool in REGISTRY.items()
        if qualified_name not in BOOTSTRAP_TOOLS
    ]
    return json.dumps(tools, separators=(",", ":"))


def _invalid_arguments(tool: McpTool, args: dict[str, Any]) -> str | None:
    errors = sorted(Draft202012Validator(tool.input_schema).iter_errors(args), key=lambda error: list(error.path))
    if not errors:
        return None
    return "invalid arguments: " + "; ".join(error.message for error in errors)


class McpClient:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()

    def call_tool(self, server: str, name: str, args: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        qualified = f"{server}.{name}"
        tool = REGISTRY.get(qualified)
        if tool is None:
            return None, f"unknown tool {qualified}"
        invalid = _invalid_arguments(tool, args)
        if invalid:
            return None, invalid
        if qualified in self.failures:
            return None, f"{qualified} failed"
        try:
            body = json.dumps(tool.fn(args))
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return None, f"{qualified} returned unparseable JSON"
        except Exception as exc:
            return None, str(exc)
        if not isinstance(parsed, dict):
            return None, f"{qualified} did not return a JSON object"
        return parsed, None
