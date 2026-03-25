"""Configuration management for patstat-mcp."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

def _find_repo_root() -> Path:
    """Find repo root by walking up from this file looking for pyproject.toml.

    Works for both editable installs (src/patstat_mcp/config.py) and
    non-editable installs (.venv/lib/.../patstat_mcp/config.py).
    """
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = candidate.parent
        if (candidate / "pyproject.toml").exists() and (candidate / "data").exists():
            return candidate
    # Fallback: assume editable layout
    return Path(__file__).resolve().parent.parent.parent


REPO_ROOT = _find_repo_root()


def _resolve(p: Path) -> Path:
    """Resolve a path: absolute paths stay as-is, relative paths resolve against REPO_ROOT."""
    if p.is_absolute():
        return p
    return REPO_ROOT / p


@dataclass
class Config:
    """Server configuration."""

    context_dir: Path = field(default_factory=lambda: REPO_ROOT / "data")
    prompt_file: Path | None = None
    log_level: str = "INFO"

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load config from file, env, or defaults."""
        # Priority: explicit path > env var > default location
        path = (
            config_path
            or (Path(p) if (p := os.environ.get("PATSTAT_MCP_CONFIG")) else None)
            or REPO_ROOT / "config" / "patstat-mcp.json"
        )

        if path.exists():
            return cls._from_file(path)
        return cls._from_env()

    @classmethod
    def _from_file(cls, path: Path) -> "Config":
        """Load from JSON config file."""
        data = json.loads(path.read_text())
        return cls(
            context_dir=_resolve(Path(data.get("context_dir", "data"))),
            prompt_file=_resolve(Path(p)) if (p := data.get("prompt_file")) else None,
            log_level=data.get("log_level", "INFO"),
        )

    @classmethod
    def _from_env(cls) -> "Config":
        """Load from environment variables."""
        return cls(
            context_dir=_resolve(Path(os.environ.get("CONTEXT_DIR", "data"))),
            prompt_file=_resolve(Path(p)) if (p := os.environ.get("PROMPT_FILE")) else None,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
