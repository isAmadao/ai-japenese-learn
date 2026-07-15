"""JSON utilities — extract structured data from LLM output."""

import json
import re


def extract_json(text: str):
    """Extract JSON object/array from LLM output.

    Handles common LLM JSON issues:
    - Markdown fences around JSON
    - Trailing/missing commas between objects
    - Extra text before/after JSON
    """
    text = text.strip()
    # Remove markdown fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)
    # Find outermost { ... } or [ ... ]
    first = text.find("[")
    if first == -1:
        first = text.find("{")
    last = text.rfind("]")
    if last == -1 or last < first:
        last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first: last + 1]

    # Try parsing as-is first (fast path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # ── Repair common LLM JSON issues ─────────────────────
    # 1. Missing commas between adjacent objects: }{
    text = re.sub(r"}\s*\{", "},{", text)
    # 2. Missing commas between object and array: }[
    text = re.sub(r"}\s*\[", "],[", text)
    # 3. Missing commas between array and object: ]{
    text = re.sub(r"\]\s*\{", "},{", text)
    # 4. Trailing comma before } or ]
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    return json.loads(text)
