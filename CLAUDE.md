# CLAUDE.md

## Project Overview

Lightweight MCP server for PATSTAT patent database on EPO TIP. Provides schema discovery and query execution via `epo.tipdata.patstat.PatstatClient`. No authentication, no API keys, no BigQuery credentials needed -- TIP handles everything.

## Architecture

- `src/patstat_mcp/` -- MCP server source
  - `server.py` -- Entry point, transport setup (stdio/SSE/HTTP)
  - `tools.py` -- 5 MCP tools (list_tables, get_table_schema, search_tables, get_table_samples, execute_query)
  - `tip_client.py` -- TIP PatstatClient wrapper + SQLite reference table routing
  - `config.py` -- Config loading, repo root detection
  - `context.py` -- Schema/sample JSON loading
- `data/tables/` -- Per-table schema JSON files
- `data/samples/` -- Per-table sample data JSON files (10 rows each)
- `data/reference.db.gz` -- SQLite with 5 IPC/CPC reference tables (auto-decompressed)
- `config/` -- Server config and prompt templates

## Development

- Python >= 3.10
- Install: `pip install -e ".[dev]"`
- Run: `patstat-mcp-lite` (stdio) or `patstat-mcp-lite --http --port 8080`
- Tests: `pytest`

## Branching

- `develop` -- active development (default branch)
- `main` -- stable, branch-protected (PRs only)

## Key Patterns

- **TIP-only**: `execute_query` requires `epo.tipdata.patstat` (only available in TIP)
- **Schema discovery works anywhere**: `list_tables`, `get_table_schema`, etc. just read JSON files
- **Adding tables**: Drop JSON in `data/tables/` + `data/samples/` -- no code changes
- **Reference tables**: 5 IPC/CPC tables served from local SQLite, not via PatstatClient
- **No env vars needed**: TIP provides auth transparently. Only `LOG_LEVEL` and `MCP_PORT` are optional.
