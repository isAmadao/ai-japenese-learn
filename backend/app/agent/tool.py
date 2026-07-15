"""Agent Tool — lightweight tool definition for agent use."""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, get_type_hints


@dataclass
class AgentTool:
    """A tool that an agent can call during generation.

    Attributes:
        name: Unique tool identifier (snake_case).
        description: What the tool does — shown to LLM for decision making.
        fn: The callable that implements the tool.
        parameters: JSON Schema describing accepted arguments.
    """
    name: str
    description: str
    fn: Callable
    parameters: dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": [],
    })

    def __call__(self, **kwargs) -> Any:
        return self.fn(**kwargs)

    def format_for_prompt(self) -> str:
        """Return a text block for LLM system prompts.

        Example:
            ## verify_kana
            验证并修正日语单词的假名读音
            参数：
              - word (必填): 日语单词（汉字/假名混写）
              - kana (必填): 需要校验的假名读音
        """
        lines = [f"## {self.name}", self.description, "参数："]
        props = self.parameters.get("properties", {})
        required = set(self.parameters.get("required", []))
        for pname, pschema in props.items():
            req = " (必填)" if pname in required else " (可选)"
            desc = pschema.get("description", pschema.get("type", ""))
            lines.append(f"  - {pname}{req}: {desc}")
        return "\n".join(lines)


def make_tool(
    fn: Callable,
    name: Optional[str] = None,
    description: Optional[str] = None,
    param_descriptions: Optional[dict[str, str]] = None,
) -> AgentTool:
    """Create an AgentTool from a function, inferring schema from its signature.

    Args:
        fn: The function to wrap.
        name: Tool name (defaults to function name).
        description: Tool description (defaults to function docstring).
        param_descriptions: Optional map of parameter name → human-readable description.
    """
    actual_name = name or fn.__name__
    actual_desc = description or (fn.__doc__ or "").strip()

    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    properties = {}
    required = []

    TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}

    for pname, param in sig.parameters.items():
        if pname == "return":
            continue
        py_type = hints.get(pname, str)
        json_type = TYPE_MAP.get(py_type, "string")
        prop: dict[str, Any] = {"type": json_type}
        if param_descriptions and pname in param_descriptions:
            prop["description"] = param_descriptions[pname]
        properties[pname] = prop
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    return AgentTool(
        name=actual_name,
        description=actual_desc,
        fn=fn,
        parameters={"type": "object", "properties": properties, "required": required},
    )
