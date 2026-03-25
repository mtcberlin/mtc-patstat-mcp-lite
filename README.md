# PATSTAT MCP Lite

MCP (Model Context Protocol) server for PATSTAT patent database schema discovery and query execution on the **EPO TIP platform**.

This is a lightweight version of [mtc-patstat-mcp](https://github.com/mtcberlin/mtc-patstat-mcp) -- stripped of authentication, BigQuery direct access, and cost-cap logic. It runs exclusively inside EPO TIP using `epo.tipdata.patstat.PatstatClient`.

## Requirements

- Python >= 3.10
- **EPO TIP environment** (provides `epo.tipdata.patstat`)
- Schema discovery tools work anywhere; `execute_query` requires TIP

## Installation

```bash
pip install git+https://github.com/mtcberlin/mtc-patstat-mcp-lite.git@develop
```

## Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List all available PATSTAT tables with descriptions |
| `get_table_schema` | Get column details (name, type, description) for a specific table |
| `search_tables` | Search for tables/columns by keyword |
| `get_table_samples` | Get sample data rows for a specific table |
| `execute_query` | Execute SQL against PATSTAT via TIP PatstatClient |

**Workflow:**
1. `list_tables()` -- overview of all tables
2. Identify relevant tables for your query
3. `get_table_schema(table_name)` -- column details with types
4. `get_table_samples(table_name)` -- understand actual data values
5. Generate SQL using MCP-provided context
6. `execute_query(query)` -- run the query and get results

## Usage

### stdio (default, for Claude Code / MCP clients)

```bash
patstat-mcp-lite
```

### HTTP (for Svelte app / sidecar integration)

```bash
patstat-mcp-lite --http --port 8080
```

Serves both SSE (`/sse` + `/messages`) and Streamable HTTP (`/mcp`) on one port.

### MCP Client Configuration

Copy `.mcp.json.example` to `.mcp.json`:

```json
{
  "mcpServers": {
    "patstat-mcp-lite": {
      "command": "patstat-mcp-lite"
    }
  }
}
```

## Transport Options

| Transport | Flag | Endpoints | Use with |
|-----------|------|-----------|----------|
| stdio | _(default)_ | -- | Claude Code manages the process |
| SSE | `--sse` | `/sse` + `/messages` | Claude Code CLI (`"type": "sse"`) |
| Streamable HTTP | `--streamable-http` | `/mcp` | Claude Code CLI (`"type": "http"`) |
| Combined | `--http` | `/sse` + `/messages` + `/mcp` | All clients on one port |

## Architecture

```
src/patstat_mcp/
  server.py      -- MCP server entry point (stdio/SSE/HTTP transports)
  tools.py       -- Tool definitions and handlers
  tip_client.py  -- TIP PatstatClient wrapper + SQLite reference tables
  config.py      -- Configuration loading
  context.py     -- Schema/sample JSON file loading
data/
  tables/        -- Per-table schema JSON files
  samples/       -- Per-table sample data JSON files (10 rows each)
  reference.db.gz -- SQLite with 5 IPC/CPC reference tables
config/
  patstat-mcp.json   -- Server configuration
  prompts/default.txt -- System prompt template
```

## Reference Tables

Five IPC/CPC hierarchy tables are not available via TIP's PatstatClient. These are served from a local SQLite database (`data/reference.db.gz`, auto-decompressed on first use):

- `tls_cpc_hierarchy`
- `tls_ipc_catchword`
- `tls_ipc_concordance`
- `tls_ipc_everused`
- `tls_ipc_hierarchy`

Queries mixing TIP tables and reference tables are not supported -- query them separately.

## Extending

Add new PATSTAT tables by dropping two JSON files -- no code changes needed:

1. `data/tables/<table_name>.json` -- schema definition
2. `data/samples/<table_name>.json` -- 10 sample rows

## Development

```bash
git clone https://github.com/mtcberlin/mtc-patstat-mcp-lite.git
cd mtc-patstat-mcp-lite
pip install -e ".[dev]"
pytest
```

### Branching

- `develop` -- active development (default branch)
- `main` -- stable, branch-protected (PRs only)

## License

Internal use -- MTC Berlin / EPO TIP.
