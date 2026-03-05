from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from graph.core.mcp_client import MCP_URL


def _repo_root() -> Path:
    # This file is: school-ai-agent/graph/core/prompt_loader.py
    # prompts folder is: school-ai-agent/prompts
    return Path(__file__).resolve().parents[2]


PROMPTS_DIR = _repo_root() / "prompts"


def _overlay_filename_from_mcp_url(url: str) -> str:
    """
    Convert MCP URL -> overlay filename.
    Example: http://localhost:4000/mcp -> localhost_4000.txt
    """
    p = urlparse(url)
    host = (p.hostname or "unknown").replace(".", "_")
    port = p.port
    if port is None:
        port = 443 if p.scheme == "https" else 80
    return f"{host}_{port}.txt"


def load_prompt(base_name: str) -> str:
    """
    Load base prompt + optional server-specific overlay prompt.

    - base: prompts/<base_name> (optional)
    - overlay: prompts/overlays/<host_port>.txt (optional)
    - fallback overlay: prompts/overlays/default.txt (optional)

    Returns merged string (may be empty).
    """
    parts: list[str] = []

    base_file = PROMPTS_DIR / base_name
    if base_file.exists():
        parts.append(base_file.read_text(encoding="utf-8"))

    overlay_dir = PROMPTS_DIR / "overlays"
    specific_overlay = overlay_dir / _overlay_filename_from_mcp_url(MCP_URL)
    default_overlay = overlay_dir / "default.txt"

    if specific_overlay.exists():
        parts.append("\n# MCP Server Overlay\n")
        parts.append(specific_overlay.read_text(encoding="utf-8"))
    elif default_overlay.exists():
        parts.append("\n# Default Overlay\n")
        parts.append(default_overlay.read_text(encoding="utf-8"))

    return "\n".join(parts).strip()