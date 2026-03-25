"""MCP Server entry point (TIP Lite)."""

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Prompt, PromptMessage, GetPromptResult

from .config import Config
from .context import ContextStore
from .tools import (
    get_tools,
    handle_list_tables,
    handle_get_table_schema,
    handle_search_tables,
    handle_get_table_samples,
    handle_execute_query,
)

logger = logging.getLogger(__name__)

# Global state
server = Server("patstat-mcp-lite")
ctx: ContextStore
cfg: Config
query_client: object  # TipClient, initialized at startup


def _ensure_tip_importable() -> bool:
    """Check whether epo.tipdata.patstat is importable.

    Inside a virtual-env the TIP library lives in the *base* Python's
    site-packages (e.g. /opt/conda/...).  If the venv was created without
    --system-site-packages the library is invisible.  We detect this and
    extend sys.path so the import works.
    """
    try:
        import epo.tipdata.patstat  # noqa: F401
        return True
    except ImportError:
        pass

    # Not directly importable -- if we're inside a venv, try the base
    # interpreter's site-packages (e.g. conda env on TIP).
    if sys.prefix == sys.base_prefix:
        return False  # not a venv -- genuinely absent

    base_site = os.path.join(
        sys.base_prefix, "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
    if not os.path.isdir(base_site) or base_site in sys.path:
        return False

    # Clear any partially cached namespace imports from the failed attempt
    for mod_name in list(sys.modules):
        if mod_name.startswith("epo"):
            del sys.modules[mod_name]

    sys.path.append(base_site)
    try:
        import epo.tipdata.patstat  # noqa: F401
        logger.info("Added base site-packages for TIP: %s", base_site)
        return True
    except ImportError:
        sys.path.remove(base_site)
        return False


USAGE_PROMPT = """PATSTAT Patent Database Query Helper (TIP Lite)

I provide schema information for the EPO PATSTAT database to help you generate SQL queries.
This server runs exclusively on the EPO TIP platform using PatstatClient.

**Workflow:**
1. Call `list_tables` to see all available tables
2. Identify relevant tables for your query
3. Call `get_table_schema(table_name)` to get column names and types
4. Generate SQL using the schema information
5. Call `execute_query(query)` to run the query

**Tips:**
- Use `search_tables(keyword)` to find tables/columns by keyword
- Pay attention to column types (INT64, STRING, DATE) for correct comparisons
- For applicants: use `tls207_pers_appln.applt_seq_nr > 0`
- For inventors: use `tls207_pers_appln.invt_seq_nr > 0`
- Country codes are 2-letter ISO codes (e.g., 'AT' for Austria, 'GB' for UK)

**Common tables:**
- `tls201_appln` - Patent applications (appln_id, appln_filing_year, granted)
- `tls206_person` - Applicants/inventors (person_id, person_name, person_ctry_code)
- `tls207_pers_appln` - Links persons to applications (appln_id, person_id, applt_seq_nr)
"""


@server.list_prompts()
async def list_prompts():
    return [
        Prompt(
            name="usage",
            description="How to use this MCP server to generate PATSTAT queries"
        )
    ]


@server.get_prompt()
async def get_prompt(name: str) -> GetPromptResult:
    if name == "usage":
        return GetPromptResult(
            description="PATSTAT query generation guide",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=USAGE_PROMPT)
                )
            ]
        )
    raise ValueError(f"Unknown prompt: {name}")


@server.list_tools()
async def list_tools():
    return get_tools()


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_tables":
        return handle_list_tables(ctx)
    elif name == "get_table_schema":
        return handle_get_table_schema(arguments.get("table_name", ""), ctx)
    elif name == "search_tables":
        return handle_search_tables(arguments.get("keyword", ""), ctx)
    elif name == "get_table_samples":
        return handle_get_table_samples(arguments.get("table_name", ""), ctx)
    elif name == "execute_query":
        return handle_execute_query(
            query_client,
            query=arguments.get("query", ""),
            max_results=arguments.get("max_results", 1000),
        )
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def run_stdio() -> None:
    """Run server with stdio transport."""
    async def run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    asyncio.run(run())


def run_sse(host: str, port: int) -> None:
    """Run server with SSE transport over HTTP."""
    from mcp.server.sse import SseServerTransport
    import uvicorn

    sse = SseServerTransport("/messages")

    async def handle_sse(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    async def app(scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]
            if path == "/sse":
                await handle_sse(scope, receive, send)
            elif path == "/messages" and scope["method"] == "POST":
                await sse.handle_post_message(scope, receive, send)
            else:
                await send({"type": "http.response.start", "status": 404, "headers": []})
                await send({"type": "http.response.body", "body": b"Not Found"})

    logger.info(f"Starting SSE server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


def run_streamable_http(host: str, port: int) -> None:
    """Run server with Streamable HTTP transport."""
    import contextlib
    from collections.abc import AsyncIterator
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    import uvicorn

    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    async def handle_request(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    app = Starlette(lifespan=lifespan)

    async def routing_app(scope, receive, send):
        if scope["type"] == "lifespan":
            await app(scope, receive, send)
        elif scope["type"] == "http" and scope["path"] in ("/mcp", "/mcp/"):
            await handle_request(scope, receive, send)
        else:
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b"Not Found"})

    logger.info(f"Starting Streamable HTTP server on http://{host}:{port}/mcp")
    uvicorn.run(routing_app, host=host, port=port)


def run_http(host: str, port: int) -> None:
    """Run server with both SSE and Streamable HTTP on one port.

    - /sse + /messages  -> SSE transport
    - /mcp              -> Streamable HTTP transport
    """
    import contextlib
    from collections.abc import AsyncIterator
    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    import uvicorn

    sse = SseServerTransport("/messages")

    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
    )

    async def handle_streamable(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(lifespan=lifespan)

    async def combined_app(scope, receive, send):
        if scope["type"] == "lifespan":
            await app(scope, receive, send)
        elif scope["type"] != "http":
            return
        elif scope["path"] == "/sse":
            async with sse.connect_sse(scope, receive, send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())
        elif scope["path"] == "/messages" and scope["method"] == "POST":
            await sse.handle_post_message(scope, receive, send)
        elif scope["path"] in ("/mcp", "/mcp/"):
            await handle_streamable(scope, receive, send)
        else:
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b"Not Found"})

    logger.info(f"Starting HTTP server on http://{host}:{port}")
    logger.info(f"  SSE transport:             /sse + /messages")
    logger.info(f"  Streamable HTTP transport:  /mcp")
    uvicorn.run(combined_app, host=host, port=port)


def main() -> None:
    """Entry point."""
    global cfg, ctx, query_client

    load_dotenv()

    parser = argparse.ArgumentParser(description="PATSTAT MCP Lite (TIP)")
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--sse", action="store_true", help="Run with SSE-only transport")
    transport.add_argument("--streamable-http", action="store_true", help="Run with Streamable HTTP-only transport")
    transport.add_argument("--http", action="store_true", help="Run with both SSE + Streamable HTTP transports")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8080")), help="Port for HTTP server (default: 8080)")
    args = parser.parse_args()

    cfg = Config.load()
    logging.basicConfig(level=cfg.log_level)

    # Initialize context store with tables and samples directories
    tables_dir = cfg.context_dir / "tables"
    samples_dir = cfg.context_dir / "samples"
    logger.info(f"Loading tables from: {tables_dir}")
    logger.info(f"Loading samples from: {samples_dir}")
    ctx = ContextStore(tables_dir, samples_dir)

    # Initialize TIP backend
    if not _ensure_tip_importable():
        logger.error(
            "epo.tipdata.patstat is not available. "
            "This MCP server only works inside the EPO TIP environment."
        )
        sys.exit(1)

    from .tip_client import TipClient
    query_client = TipClient()
    logger.info("Using TIP PatstatClient backend")

    if args.sse:
        run_sse(args.host, args.port)
    elif args.streamable_http:
        run_streamable_http(args.host, args.port)
    elif args.http:
        run_http(args.host, args.port)
    else:
        run_stdio()


if __name__ == "__main__":
    main()
