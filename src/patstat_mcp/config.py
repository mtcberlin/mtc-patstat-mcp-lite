"""Configuration management for patstat-mcp.

Table and sample metadata ships inside the package at
``src/patstat_mcp/resources/``, so defaults are derived from ``__file__``
and work in every install layout (editable, wheel, pip+git). Set
``CONTEXT_DIR`` or ``PROMPT_FILE`` env vars to override for development.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
DEFAULT_CONTEXT_DIR = _PKG_DIR / "resources"
DEFAULT_PROMPT_FILE = _PKG_DIR / "resources" / "prompts" / "default.txt"


@dataclass
class Config:
    """Server configuration."""

    context_dir: Path = field(default_factory=lambda: DEFAULT_CONTEXT_DIR)
    prompt_file: Path | None = field(default_factory=lambda: DEFAULT_PROMPT_FILE)
    log_level: str = "INFO"

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load config from environment variables, falling back to defaults.

        ``config_path`` is accepted for backwards compatibility but ignored —
        all overrides now go through env vars (``CONTEXT_DIR``, ``PROMPT_FILE``,
        ``LOG_LEVEL``).
        """
        context_dir = Path(os.environ["CONTEXT_DIR"]) if "CONTEXT_DIR" in os.environ else DEFAULT_CONTEXT_DIR
        prompt_file = Path(os.environ["PROMPT_FILE"]) if "PROMPT_FILE" in os.environ else DEFAULT_PROMPT_FILE
        return cls(
            context_dir=context_dir,
            prompt_file=prompt_file,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
