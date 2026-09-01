from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import time


@dataclass(slots=True)
class IntegrationSpec:
    name: str
    kind: str
    enabled: bool = False
    capabilities: list[str] = field(default_factory=list)
    trust: str = "untrusted"
    config: dict = field(default_factory=dict)
    source: str = "local"
    updated_at: float = 0.0


class IntegrationRegistry:
    """Capability-oriented registry for replaceable integrations.

    The registry stores declarations only. Execution remains in dedicated
    adapters (MCP, browser, channels, Windows, etc.) so a manifest cannot grant
    itself executable authority.
    """

    ALLOWED_KINDS = {"builtin", "mcp", "channel", "webhook", "plugin", "adapter"}

    def __init__(self, path: Path, manifest_dir: Path | None = None) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_dir = (manifest_dir or (path.parent / "integrations.d"))
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({})

    def _load(self) -> dict[str, dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self, data: dict[str, dict]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def _validate(spec: IntegrationSpec) -> IntegrationSpec:
        spec.name = spec.name.strip()[:100]
        spec.kind = spec.kind.strip().lower()
        if not spec.name:
            raise ValueError("integration name is required")
        if spec.kind not in IntegrationRegistry.ALLOWED_KINDS:
            raise ValueError("unsupported integration kind")
        spec.capabilities = sorted({str(x).strip()[:100] for x in spec.capabilities if str(x).strip()})[:100]
        spec.trust = spec.trust.strip()[:64] or "untrusted"
        spec.updated_at = time.time()
        return spec

    def upsert(self, spec: IntegrationSpec) -> IntegrationSpec:
        spec = self._validate(spec)
        data = self._load()
        data[spec.name] = asdict(spec)
        self._save(data)
        return spec

    def get(self, name: str) -> IntegrationSpec:
        data = self._load().get(name)
        if not isinstance(data, dict):
            raise KeyError(name)
        return IntegrationSpec(**data)

    def set_enabled(self, name: str, enabled: bool) -> IntegrationSpec:
        spec = self.get(name)
        spec.enabled = bool(enabled)
        return self.upsert(spec)

    def list(self, enabled_only: bool = False) -> list[IntegrationSpec]:
        items: dict[str, IntegrationSpec] = {}
        for raw in self._load().values():
            try:
                spec = IntegrationSpec(**raw)
                items[spec.name] = spec
            except Exception:
                continue
        for manifest in sorted(self.manifest_dir.glob("*.json")):
            try:
                raw = json.loads(manifest.read_text(encoding="utf-8"))
                spec = IntegrationSpec(**raw)
                spec.source = f"manifest:{manifest.name}"
                if spec.name not in items:
                    items[spec.name] = self._validate(spec)
            except Exception:
                continue
        values = sorted(items.values(), key=lambda x: (not x.enabled, x.name.casefold()))
        return [x for x in values if x.enabled] if enabled_only else values

    def seed_builtin(self, name: str, capabilities: list[str], enabled: bool = True) -> None:
        try:
            self.get(name)
            return
        except KeyError:
            pass
        self.upsert(IntegrationSpec(name=name, kind="builtin", enabled=enabled, capabilities=capabilities,
                                    trust="owner-local", source="core"))

    def discover_mcp(self, server_names: list[str]) -> None:
        for name in server_names:
            key = f"mcp:{name}"
            try:
                self.get(key)
                continue
            except KeyError:
                pass
            self.upsert(IntegrationSpec(name=key, kind="mcp", enabled=True,
                                        capabilities=["dynamic-tools"], trust="configured-local",
                                        config={"server": name}, source="mcp-config"))

    def capability_index(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        for spec in self.list(enabled_only=True):
            for capability in spec.capabilities:
                index.setdefault(capability, []).append(spec.name)
        return {key: sorted(value) for key, value in sorted(index.items())}
