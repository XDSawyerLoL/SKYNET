from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import time
import zipfile


@dataclass(frozen=True, slots=True)
class BackupResult:
    path: str
    mode: str
    files: int
    sha256: str


class BackupManager:
    """Verified SKYNET state backup/export.

    Portable exports intentionally exclude identity.key. Full-identity backups
    use Windows DPAPI and are bound to the Windows user profile; SKYNET does not
    invent custom cryptography for portable secret export.
    """

    def __init__(self, data_dir: Path, output_dir: Path) -> None:
        self.data_dir = data_dir.resolve()
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _collect(self, include_identity: bool) -> list[Path]:
        files: list[Path] = []
        if not self.data_dir.exists():
            return files
        for path in sorted(self.data_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.data_dir)
            if not include_identity and rel.as_posix() == "identity.key":
                continue
            if rel.parts and rel.parts[0] == "backups":
                continue
            if path.name.endswith(("-journal", "-wal", "-shm")):
                continue
            files.append(path)
        return files

    def _read_consistent(self, path: Path) -> bytes:
        if path.suffix.lower() != ".db":
            return path.read_bytes()
        snapshot: Path | None = None
        source = None
        dest = None
        try:
            fd, raw = tempfile.mkstemp(prefix="skynet-backup-", suffix=".db", dir=self.output_dir)
            os.close(fd)
            snapshot = Path(raw)
            source = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
            dest = sqlite3.connect(snapshot, timeout=10)
            source.backup(dest)
            dest.commit()
            dest.close(); dest = None
            source.close(); source = None
            return snapshot.read_bytes()
        except sqlite3.DatabaseError:
            return path.read_bytes()
        finally:
            if dest is not None:
                dest.close()
            if source is not None:
                source.close()
            if snapshot is not None:
                snapshot.unlink(missing_ok=True)

    def _archive_bytes(self, include_identity: bool) -> tuple[bytes, int]:
        files = self._collect(include_identity)
        manifest_files: list[dict] = []
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                rel = path.relative_to(self.data_dir).as_posix()
                body = self._read_consistent(path)
                manifest_files.append({"path": rel, "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)})
                zf.writestr(f"state/{rel}", body)
            manifest = {
                "format": 1,
                "created_at": time.time(),
                "identity_included": include_identity,
                "files": manifest_files,
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return memory.getvalue(), len(files)

    @staticmethod
    def _verify_archive(body: bytes) -> dict:
        with zipfile.ZipFile(io.BytesIO(body), "r") as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            for item in manifest.get("files", []):
                raw = zf.read("state/" + item["path"])
                if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    raise ValueError(f"backup hash mismatch: {item['path']}")
            return manifest

    def export_portable(self, name: str | None = None) -> BackupResult:
        body, count = self._archive_bytes(include_identity=False)
        digest = hashlib.sha256(body).hexdigest()
        target = self.output_dir / (name or f"skynet-portable-{int(time.time())}.zip")
        target.write_bytes(body)
        return BackupResult(str(target), "portable-no-identity", count, digest)

    def import_portable(self, archive: Path, overwrite: bool = False) -> int:
        body = archive.read_bytes()
        manifest = self._verify_archive(body)
        if manifest.get("identity_included"):
            raise ValueError("identity-bearing archives must use protected import")
        restored = 0
        with zipfile.ZipFile(io.BytesIO(body), "r") as zf:
            for item in manifest.get("files", []):
                rel = Path(item["path"])
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("unsafe backup path")
                target = (self.data_dir / rel).resolve()
                target.relative_to(self.data_dir)
                if target.exists() and not overwrite:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read("state/" + item["path"]))
                restored += 1
        return restored

    @staticmethod
    def _dpapi(data: bytes, protect: bool) -> bytes:
        if os.name != "nt":
            raise RuntimeError("Windows DPAPI is available only on Windows")

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = ctypes.create_string_buffer(data)
        source = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        target = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
        if protect:
            ok = crypt32.CryptProtectData(ctypes.byref(source), "SKYNET backup", None, None, None, flags, ctypes.byref(target))
        else:
            description = ctypes.c_wchar_p()
            ok = crypt32.CryptUnprotectData(ctypes.byref(source), ctypes.byref(description), None, None, None, flags, ctypes.byref(target))
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(target.pbData, target.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(target.pbData)

    def export_windows_protected(self, name: str | None = None) -> BackupResult:
        body, count = self._archive_bytes(include_identity=True)
        protected = self._dpapi(body, True)
        digest = hashlib.sha256(protected).hexdigest()
        target = self.output_dir / (name or f"skynet-protected-{int(time.time())}.dpapi")
        target.write_bytes(protected)
        return BackupResult(str(target), "windows-dpapi-full-identity", count, digest)

    def import_windows_protected(self, archive: Path, overwrite: bool = False) -> int:
        body = self._dpapi(archive.read_bytes(), False)
        manifest = self._verify_archive(body)
        if not manifest.get("identity_included"):
            raise ValueError("protected archive does not contain full identity state")
        restored = 0
        with zipfile.ZipFile(io.BytesIO(body), "r") as zf:
            for item in manifest.get("files", []):
                rel = Path(item["path"])
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("unsafe backup path")
                target = (self.data_dir / rel).resolve()
                target.relative_to(self.data_dir)
                if target.exists() and not overwrite:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read("state/" + item["path"]))
                restored += 1
        return restored
