"""One tool as an MCP server advertises it."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class McpTool:
    """A tools/list entry (name, description, inputSchema) plus the mock call."""

    name: str
    description: str
    fn: Callable[[dict[str, Any]], dict[str, Any]]
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    server: str = ""

    @property
    def qualified_name(self) -> str:
        return f"{self.server}.{self.name}"

    def listing(self) -> dict[str, Any]:
        return {
            "name": self.qualified_name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
