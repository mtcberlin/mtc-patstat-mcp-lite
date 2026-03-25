"""MCP tool definitions for PATSTAT queries on EPO TIP."""

import logging

from mcp.types import TextContent, Tool

from .context import ContextStore

logger = logging.getLogger(__name__)


def get_tools() -> list[Tool]:
    """Return list of available tools."""
    return [
        Tool(
            name="list_tables",
            description="List all available PATSTAT database tables with their descriptions. Use this first to understand what data is available.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_table_schema",
            description="Get detailed schema for a specific table including all columns and their descriptions. Use after list_tables to get column details for relevant tables.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to get schema for (e.g., 'tls201_appln')"
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="search_tables",
            description="Search for tables and columns matching a keyword. Useful when you're not sure which tables contain the data you need.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to search for in table/column names and descriptions"
                    }
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="get_table_samples",
            description="Get sample data rows for a specific table. Useful to understand actual data format and values.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to get sample data for (e.g., 'tls201_appln')"
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="execute_query",
            description="Execute a SQL query against the PATSTAT database via TIP PatstatClient. Use this after discovering the schema with the other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute against PATSTAT"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of rows to return (default: 1000, max: 10000)",
                        "default": 1000
                    }
                },
                "required": ["query"]
            }
        ),
    ]


def handle_list_tables(ctx: ContextStore) -> list[TextContent]:
    """Handle list_tables tool call."""
    tables = ctx.list_tables()

    if not tables:
        return [TextContent(type="text", text="No tables found.")]

    lines = [f"**Available Tables ({len(tables)}):**\n"]
    for t in tables:
        lines.append(f"- **{t['table_name']}**: {t['description']}")

    return [TextContent(type="text", text="\n".join(lines))]


def handle_get_table_schema(table_name: str, ctx: ContextStore) -> list[TextContent]:
    """Handle get_table_schema tool call."""
    schema = ctx.get_table_schema(table_name)

    if not schema:
        return [TextContent(
            type="text",
            text=f"Table '{table_name}' not found. Use list_tables to see available tables."
        )]

    lines = [
        f"**Table: {schema['table_name']}**",
        f"_{schema.get('description', 'No description')}_\n",
        "**Columns:**"
    ]

    for col in schema.get("columns", []):
        col_type = col.get("type", "")
        type_str = f" ({col_type})" if col_type else ""
        lines.append(f"- **{col['name']}**{type_str}: {col.get('description', 'No description')}")

    if schema.get("common_joins"):
        lines.append("\n**Common Joins:**")
        for join in schema["common_joins"]:
            lines.append(f"- {join}")

    if schema.get("example_filters"):
        lines.append("\n**Example Filters:**")
        for filter_ex in schema["example_filters"]:
            lines.append(f"- `{filter_ex}`")

    return [TextContent(type="text", text="\n".join(lines))]


def handle_search_tables(keyword: str, ctx: ContextStore) -> list[TextContent]:
    """Handle search_tables tool call."""
    results = ctx.search_tables(keyword)

    if not results:
        return [TextContent(
            type="text",
            text=f"No tables or columns found matching '{keyword}'."
        )]

    lines = [f"**Search Results for '{keyword}':**\n"]

    for result in results:
        lines.append(f"**{result['table_name']}**: {result['description']}")

        col_matches = [m for m in result["matches"] if m["match_type"] == "column"]

        if col_matches:
            cols = ", ".join(m["column"] for m in col_matches)
            lines.append(f"  Matching columns: {cols}")

        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


def handle_get_table_samples(table_name: str, ctx: ContextStore) -> list[TextContent]:
    """Handle get_table_samples tool call."""
    samples = ctx.get_table_samples(table_name)

    if not samples:
        return [TextContent(
            type="text",
            text=f"No sample data found for table '{table_name}'."
        )]

    lines = [
        f"**Sample Data: {samples['table_name']}**",
        f"_{samples.get('row_count', 0)} sample rows_\n",
        "**Columns:** " + ", ".join(samples.get("columns", [])),
        "\n**Sample Rows:**"
    ]

    for i, row in enumerate(samples.get("rows", [])[:5], 1):
        lines.append(f"\n_Row {i}:_")
        for col in samples.get("columns", []):
            val = row.get(col) if isinstance(row, dict) else None
            val_str = str(val) if val is not None else "NULL"
            if len(val_str) > 50:
                val_str = val_str[:47] + "..."
            lines.append(f"  {col}: {val_str}")

    if samples.get("row_count", 0) > 5:
        lines.append(f"\n_... and {samples['row_count'] - 5} more rows_")

    return [TextContent(type="text", text="\n".join(lines))]


def handle_execute_query(
    client: object,
    query: str,
    max_results: int = 1000,
) -> list[TextContent]:
    """Handle execute_query tool call via TIP PatstatClient."""
    try:
        result = client.execute_query(query, max_results=max_results)
    except Exception as e:
        return [TextContent(type="text", text=f"**Query error:** {e}")]

    columns = result["columns"]
    rows = result["rows"]
    lines = []

    if not rows:
        lines.append("**Query returned 0 rows.**")
    else:
        # Markdown table
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join("---" for _ in columns) + " |")

        for row in rows:
            vals = []
            for col in columns:
                v = str(row.get(col, ""))
                if len(v) > 60:
                    v = v[:57] + "..."
                vals.append(v)
            lines.append("| " + " | ".join(vals) + " |")

    # Metadata
    meta = f"\n_Rows: {result['total_rows']}"
    if result["truncated"]:
        meta += f" | **Truncated** (max_results={max_results})"
    meta += "_"
    lines.append(meta)

    return [TextContent(type="text", text="\n".join(lines))]
