from __future__ import annotations

from enum import Enum
from collections.abc import Callable


class PermissionLevel(str, Enum):
    OBSERVE = "observe"
    SAFE = "safe"
    CONFIRM = "confirm"
    BLOCKED = "blocked"


DEFAULT_POLICY: dict[str, PermissionLevel] = {
    "list_files": PermissionLevel.OBSERVE,
    "read_file": PermissionLevel.OBSERVE,
    "write_file": PermissionLevel.CONFIRM,
    "powershell": PermissionLevel.CONFIRM,
    "remember": PermissionLevel.SAFE,
    "list_skills": PermissionLevel.OBSERVE,
    "read_skill": PermissionLevel.OBSERVE,
}


class PermissionGate:
    def __init__(self, policy: dict[str, PermissionLevel] | None = None) -> None:
        self.policy = dict(DEFAULT_POLICY)
        if policy:
            self.policy.update(policy)

    def level_for(self, tool_name: str) -> PermissionLevel:
        return self.policy.get(tool_name, PermissionLevel.BLOCKED)

    def authorize(
        self,
        tool_name: str,
        summary: str,
        confirmer: Callable[[str], bool],
    ) -> bool:
        level = self.level_for(tool_name)
        if level is PermissionLevel.BLOCKED:
            return False
        if level is PermissionLevel.CONFIRM:
            return confirmer(summary)
        return True
