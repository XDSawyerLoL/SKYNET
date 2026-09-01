from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import time
import zipfile

from .identity import LocalIdentityStore


EXCLUDED_NAMES = {"identity.key", "KILL_SWITCH.json"}


@dataclass(frozen=True, slots=True)
class BundleManifest:
    created_at: float
    files: dict[str, str]
    include_identity: bool
    signer: str
    signature: str


class StateBundle:
    """Portable signed state bundle.

    This provides integrity/provenance. It is deliberately not advertised as
    encryption. Identity material is excluded by default and only included when
    explicitly requested.
    """

    def __init__(self, data_dir: Path, identity: LocalIdentityStore) -> None:
        self.data_dir = data_dir.resolve()
        self.identity = identity

    def export(self, target: Path, include_identity: bool = False) -> Path:
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        files: dict[str, str] = {}
        candidates: list[Path] = []
        for path in self.data_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.name == "KILL_SWITCH.json":
                continue
            if path.name == "identity.key" and not include_identity:
                continue
            candidates.append(path)
        for path in candidates:
            rel = path.relative_to(self.data_dir).as_posix()
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        core = {
            "created_at": time.time(),
            "files": files,
            "include_identity": include_identity,
            "signer": self.identity.identity.fingerprint,
        }
        body = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = self.identity.sign(body)
        manifest = BundleManifest(signature=signature, **core)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in candidates:
                zf.write(path, arcname="state/" + path.relative_to(self.data_dir).as_posix())
            zf.writestr("manifest.json", json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
        return target

    def inspect(self, source: Path) -> tuple[BundleManifest, bool]:
        with zipfile.ZipFile(source, "r") as zf:
            data = json.loads(zf.read("manifest.json").decode("utf-8"))
            manifest = BundleManifest(**data)
            valid_files = True
            for rel, expected in manifest.files.items():
                try:
                    actual = hashlib.sha256(zf.read("state/" + rel)).hexdigest()
                except KeyError:
                    valid_files = False
                    break
                if actual != expected:
                    valid_files = False
                    break
            core = {
                "created_at": manifest.created_at,
                "files": manifest.files,
                "include_identity": manifest.include_identity,
                "signer": manifest.signer,
            }
            body = json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
            signature_ok = manifest.signer == self.identity.identity.fingerprint and self.identity.verify(body, manifest.signature)
            return manifest, bool(valid_files and signature_ok)
