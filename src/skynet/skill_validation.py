from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class SkillValidation:
    valid: bool
    errors: list[str]


_REQUIRED_HEADINGS = ("purpose", "preconditions", "steps", "verification", "recovery")
_FORBIDDEN = (
    "bypass permission",
    "disable permission",
    "disable audit",
    "erase audit",
    "ignore user confirmation",
    "disable antivirus",
    "disable defender",
)


class SkillValidator:
    """Static safety/quality gate for learned Markdown procedures before promotion."""

    def validate(self, content: str) -> SkillValidation:
        body = content.strip()
        errors: list[str] = []
        if len(body) < 80:
            errors.append("skill is too short to be a reliable procedure")
        if len(body) > 50_000:
            errors.append("skill exceeds 50 KB")
        lower = body.lower()
        for heading in _REQUIRED_HEADINGS:
            if not re.search(rf"(?im)^#+\s*{re.escape(heading)}\b", body):
                errors.append(f"missing heading: {heading}")
        for phrase in _FORBIDDEN:
            if phrase in lower:
                errors.append(f"forbidden control-bypass instruction: {phrase}")
        if "password" in lower and "never store" not in lower and "do not store" not in lower:
            errors.append("skill mentions passwords without an explicit non-storage rule")
        return SkillValidation(not errors, errors)
