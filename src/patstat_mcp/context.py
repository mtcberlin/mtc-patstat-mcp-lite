"""Context loading and management for multi-tool MCP."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextStore:
    """Stores and provides access to database schema context.

    Extensible design: Add new tables by dropping JSON files in the tables directory.
    No code changes required.
    """

    def __init__(self, tables_dir: Path | None = None, samples_dir: Path | None = None) -> None:
        self.tables_dir = tables_dir
        self.samples_dir = samples_dir
        self._table_cache: dict[str, dict] = {}
        self._samples_cache: dict[str, dict] = {}

    def _ensure_loaded(self) -> None:
        """Lazy load all table metadata into cache."""
        if self._table_cache or not self.tables_dir:
            return

        for f in self.tables_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                table_name = data.get("table_name", f.stem)
                self._table_cache[table_name] = data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load {f.name}: {e}")

        logger.info(f"Loaded {len(self._table_cache)} tables from {self.tables_dir}")

    def list_tables(self, platform: str | None = None) -> list[dict]:
        """Return all table names with descriptions.

        Args:
            platform: If set, filter to tables available on this platform
                      (e.g., 'bigquery', 'tip'). None returns all tables.

        Returns:
            List of dicts with 'table_name', 'description', and 'availability' keys.
        """
        self._ensure_loaded()
        results = []
        for name, data in sorted(self._table_cache.items()):
            availability = data.get("availability", ["bigquery", "tip"])
            if platform and platform not in availability:
                continue
            results.append({
                "table_name": name,
                "description": data.get("description", ""),
                "availability": availability,
            })
        return results

    def get_table_schema(self, table_name: str) -> dict | None:
        """Get full schema details for a specific table.

        Args:
            table_name: Name of the table (with or without 'public.' prefix)

        Returns:
            Full table schema dict with columns, or None if not found.
        """
        self._ensure_loaded()

        # Handle both 'tls201_appln' and 'public.tls201_appln'
        clean_name = table_name.replace("public.", "")
        return self._table_cache.get(clean_name)

    def search_tables(self, keyword: str) -> list[dict]:
        """Search tables and columns for a keyword.

        Args:
            keyword: Search term to match against table/column names and descriptions.

        Returns:
            List of matching tables with relevant columns highlighted.
        """
        # Stub for future implementation
        self._ensure_loaded()
        keyword_lower = keyword.lower()
        results = []

        for name, data in self._table_cache.items():
            matches = []

            # Check table name/description
            if keyword_lower in name.lower() or keyword_lower in data.get("description", "").lower():
                matches.append({"match_type": "table", "field": "name/description"})

            # Check columns
            for col in data.get("columns", []):
                if keyword_lower in col.get("name", "").lower() or keyword_lower in col.get("description", "").lower():
                    matches.append({"match_type": "column", "column": col.get("name")})

            if matches:
                results.append({
                    "table_name": name,
                    "description": data.get("description", ""),
                    "matches": matches
                })

        return results

    @property
    def table_count(self) -> int:
        """Return number of loaded tables."""
        self._ensure_loaded()
        return len(self._table_cache)

    def get_table_samples(self, table_name: str) -> dict | None:
        """Get sample data for a specific table.

        Args:
            table_name: Name of the table (with or without 'public.' prefix)

        Returns:
            Sample data dict with columns and rows, or None if not found.
        """
        if not self.samples_dir:
            return None

        clean_name = table_name.replace("public.", "")

        # Lazy load from cache
        if clean_name not in self._samples_cache:
            path = self.samples_dir / f"{clean_name}.json"
            if path.exists():
                try:
                    self._samples_cache[clean_name] = json.loads(path.read_text())
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to load samples for {clean_name}: {e}")
                    return None
            else:
                return None

        return self._samples_cache.get(clean_name)


# Legacy support: keep old interface working
def load(context_dir: Path) -> ContextStore:
    """Legacy loader - creates ContextStore from old-style directory."""
    tables_dir = context_dir / "tables"
    if tables_dir.exists():
        store = ContextStore(tables_dir)
    else:
        # Fallback: no tables directory yet
        store = ContextStore()
        logger.warning(f"No tables directory found at {tables_dir}")
    return store
