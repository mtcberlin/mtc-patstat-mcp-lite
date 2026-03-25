"""Tests for ContextStore schema/sample loading."""

from pathlib import Path

from patstat_mcp.context import ContextStore


def _get_context() -> ContextStore:
    """Create a ContextStore pointing at the real data directory."""
    repo_root = Path(__file__).resolve().parent.parent
    tables_dir = repo_root / "data" / "tables"
    samples_dir = repo_root / "data" / "samples"
    return ContextStore(tables_dir, samples_dir)


def test_list_tables_returns_results():
    ctx = _get_context()
    tables = ctx.list_tables()
    assert len(tables) > 0
    assert all("table_name" in t for t in tables)
    assert all("description" in t for t in tables)


def test_list_tables_includes_core_table():
    ctx = _get_context()
    tables = ctx.list_tables()
    names = [t["table_name"] for t in tables]
    assert "tls201_appln" in names


def test_get_table_schema_known_table():
    ctx = _get_context()
    schema = ctx.get_table_schema("tls201_appln")
    assert schema is not None
    assert schema["table_name"] == "tls201_appln"
    assert len(schema.get("columns", [])) > 0


def test_get_table_schema_unknown_table():
    ctx = _get_context()
    schema = ctx.get_table_schema("nonexistent_table")
    assert schema is None


def test_search_tables_finds_results():
    ctx = _get_context()
    results = ctx.search_tables("appln")
    assert len(results) > 0


def test_search_tables_no_results():
    ctx = _get_context()
    results = ctx.search_tables("zzz_nonexistent_keyword_zzz")
    assert len(results) == 0


def test_get_table_samples_known_table():
    ctx = _get_context()
    samples = ctx.get_table_samples("tls201_appln")
    assert samples is not None
    assert "rows" in samples
    assert len(samples["rows"]) > 0


def test_get_table_samples_unknown_table():
    ctx = _get_context()
    samples = ctx.get_table_samples("nonexistent_table")
    assert samples is None
