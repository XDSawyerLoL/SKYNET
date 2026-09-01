from __future__ import annotations

from pathlib import Path
from urllib import request
import hashlib
import json
import math
import re
import sqlite3
import time

_TOKEN = re.compile(r"[\w'-]+", re.UNICODE)


class SemanticMemory:
    """Dependency-free semantic retrieval.

    If an Ollama embedding model is configured it is used locally. Otherwise a
    deterministic hashed lexical vector keeps the feature offline and usable.
    """

    def __init__(self, path: Path, ollama_url: str | None = None, embed_model: str | None = None) -> None:
        self.db = sqlite3.connect(path)
        self.ollama_url = (ollama_url or "").rstrip("/")
        self.embed_model = embed_model
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS semantic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                source TEXT NOT NULL,
                text TEXT NOT NULL,
                vector TEXT NOT NULL
            )
        """)
        self.db.commit()

    @staticmethod
    def _hashed_vector(text: str, dims: int = 256) -> list[float]:
        vec = [0.0] * dims
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % dims
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[idx] += sign
        return SemanticMemory._normalize(vec)

    @staticmethod
    def _normalize(vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vec))
        return vec if norm == 0 else [x / norm for x in vec]

    def _ollama_vector(self, text: str) -> list[float] | None:
        if not self.ollama_url or not self.embed_model:
            return None
        payload = json.dumps({"model": self.embed_model, "input": text}).encode("utf-8")
        req = request.Request(
            f"{self.ollama_url}/api/embed", data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            embeddings = data.get("embeddings") or []
            if embeddings and isinstance(embeddings[0], list):
                return self._normalize([float(x) for x in embeddings[0]])
        except Exception:
            return None
        return None

    def vectorize(self, text: str) -> list[float]:
        return self._ollama_vector(text) or self._hashed_vector(text)

    def add(self, text: str, source: str = "memory") -> int:
        clean = text.strip()
        if not clean:
            raise ValueError("semantic memory text cannot be empty")
        vector = self.vectorize(clean)
        cur = self.db.execute(
            "INSERT INTO semantic_memory(ts,source,text,vector) VALUES(?,?,?,?)",
            (time.time(), source, clean, json.dumps(vector, separators=(",", ":"))),
        )
        self.db.commit()
        return int(cur.lastrowid)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return -1.0
        return sum(x * y for x, y in zip(a, b))

    def search(self, query: str, limit: int = 5) -> list[tuple[float, str, str]]:
        q = self.vectorize(query)
        rows = self.db.execute("SELECT source,text,vector FROM semantic_memory ORDER BY id DESC LIMIT 2000").fetchall()
        scored = []
        for source, text, raw in rows:
            vector = json.loads(raw)
            scored.append((self._cosine(q, vector), str(source), str(text)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:max(1, min(limit, 20))]

    def close(self) -> None:
        self.db.close()
