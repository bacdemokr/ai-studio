"""Read a structured object from a model response."""
import json
import re


def object_reply(answer):
    candidates = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', answer, re.S) + [answer]
    for raw in candidates:
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except (ValueError, TypeError):
            pass
    return {}
