import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

# CodeBuild escribe este archivo en la fase post_build (ver buildspec.yml).
_BUILD_INFO_PATH = Path(__file__).resolve().parent.parent / "build_info.json"


class BuildInfo(TypedDict):
    commit: str
    build_id: str
    built_at: str


@lru_cache
def get_build_info() -> BuildInfo:
    default: BuildInfo = {"commit": "local", "build_id": "local", "built_at": "unknown"}
    try:
        raw = json.loads(_BUILD_INFO_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    if not isinstance(raw, dict):
        return default
    return {
        "commit": str(raw.get("commit", "unknown"))[:40],
        "build_id": str(raw.get("build_id", "unknown"))[:200],
        "built_at": str(raw.get("built_at", "unknown"))[:40],
    }
