import json
from pathlib import Path

from skynet.mcp import MCPHub


def test_mcp_config_loads_only_valid_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({
        "servers": {
            "good": {"command": "python", "args": ["server.py"], "env": {"X": "1"}},
            "bad": {"args": []},
        }
    }), encoding="utf-8")
    hub = MCPHub(path)
    assert hub.list_servers() == ["good"]
    hub.close()


def test_missing_mcp_config_is_empty(tmp_path: Path) -> None:
    hub = MCPHub(tmp_path / "missing.json")
    assert hub.list_servers() == []
    hub.close()
