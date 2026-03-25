"""Tests for MCP tool handlers."""

from pathlib import Path
from unittest.mock import MagicMock

from patstat_mcp.context import ContextStore
from patstat_mcp.tools import (
    handle_list_tables,
    handle_get_table_schema,
    handle_search_tables,
    handle_get_table_samples,
    handle_execute_query,
)


def _get_context() -> ContextStore:
    """Create a ContextStore pointing at the real data directory."""
    repo_root = Path(__file__).resolve().parent.parent
    return ContextStore(repo_root / "data" / "tables", repo_root / "data" / "samples")


def _mock_tip_client(rows: list[dict] | None = None) -> MagicMock:
    """Create a mock TipClient that returns canned results."""
    client = MagicMock()
    if rows is None:
        rows = [{"appln_id": 1, "appln_filing_year": 2023}]
    client.execute_query.return_value = {
        "rows": rows,
        "total_rows": len(rows),
        "bytes_processed": 0,
        "truncated": False,
        "columns": list(rows[0].keys()) if rows else [],
    }
    return client


def test_handle_list_tables():
    ctx = _get_context()
    result = handle_list_tables(ctx)
    assert len(result) == 1
    assert "Available Tables" in result[0].text
    assert "tls201_appln" in result[0].text


def test_handle_get_table_schema_found():
    ctx = _get_context()
    result = handle_get_table_schema("tls201_appln", ctx)
    assert len(result) == 1
    assert "tls201_appln" in result[0].text
    assert "Columns" in result[0].text


def test_handle_get_table_schema_not_found():
    ctx = _get_context()
    result = handle_get_table_schema("nonexistent", ctx)
    assert "not found" in result[0].text


def test_handle_search_tables():
    ctx = _get_context()
    result = handle_search_tables("person", ctx)
    assert len(result) == 1
    assert "person" in result[0].text.lower()


def test_handle_get_table_samples():
    ctx = _get_context()
    result = handle_get_table_samples("tls201_appln", ctx)
    assert len(result) == 1
    assert "Sample Data" in result[0].text


def test_handle_execute_query_success():
    client = _mock_tip_client()
    result = handle_execute_query(client, "SELECT 1", max_results=10)
    assert len(result) == 1
    assert "appln_id" in result[0].text
    client.execute_query.assert_called_once_with("SELECT 1", max_results=10)


def test_handle_execute_query_empty():
    client = _mock_tip_client(rows=[])
    client.execute_query.return_value = {
        "rows": [],
        "total_rows": 0,
        "bytes_processed": 0,
        "truncated": False,
        "columns": [],
    }
    result = handle_execute_query(client, "SELECT 1 WHERE FALSE")
    assert "0 rows" in result[0].text


def test_handle_execute_query_error():
    client = MagicMock()
    client.execute_query.side_effect = RuntimeError("TIP connection failed")
    result = handle_execute_query(client, "SELECT 1")
    assert "Query error" in result[0].text
    assert "TIP connection failed" in result[0].text
