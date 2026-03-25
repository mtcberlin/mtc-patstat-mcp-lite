"""TIP PatstatClient wrapper for executing PATSTAT queries on the EPO TIP platform.

Drop-in replacement for BigQueryClient — same execute_query() interface,
but uses epo.tipdata.patstat.PatstatClient under the hood.
No cost tracking (queries are included in the TIP platform).

BQ-only reference tables (IPC/CPC hierarchies etc.) are served from a
local SQLite cache (data/reference.db) so no BigQuery credentials are needed.
The repo ships data/reference.db.gz; it is decompressed on first access.
"""

from __future__ import annotations

import gzip
import logging
import re
import shutil
import sqlite3
import time
from pathlib import Path

import pandas as pd

from .config import REPO_ROOT

logger = logging.getLogger(__name__)

MAX_RESULTS_HARD_LIMIT = 10000

REFERENCE_TABLES = frozenset({
    "tls_cpc_hierarchy",
    "tls_ipc_catchword",
    "tls_ipc_concordance",
    "tls_ipc_everused",
    "tls_ipc_hierarchy",
})

REFERENCE_DB_PATH = REPO_ROOT / "data" / "reference.db"


def _tables_in_query(sql: str) -> set[str]:
    """Extract table names referenced in a SQL query (best-effort)."""
    # Match FROM/JOIN followed by a table name (with optional dataset prefix)
    pattern = r'(?:FROM|JOIN)\s+(?:`?[\w.-]+`?\.)?`?(\w+)`?'
    return {m.lower() for m in re.findall(pattern, sql, re.IGNORECASE)}


class TipClient:
    """Lazy-initialized PatstatClient for query execution on TIP."""

    platform = "tip"

    def __init__(self, env: str = "PROD", reference_db: Path | None = None):
        self._env = env
        self._client: PatstatClient | None = None
        self._ref_db_path = reference_db or REFERENCE_DB_PATH
        self._ref_conn: sqlite3.Connection | None = None

    @property
    def cost_per_tb_eur(self) -> float:
        return 0.0

    @property
    def cost_cap_eur(self) -> float:
        return float("inf")

    def estimate_cost_eur(self, bytes_processed: int) -> float:
        return 0.0

    def _get_client(self) -> PatstatClient:
        if self._client is None:
            from epo.tipdata.patstat import PatstatClient
            self._client = PatstatClient(env=self._env)
            logger.info("PatstatClient initialized (env=%s)", self._env)
        return self._client

    def _get_ref_conn(self) -> sqlite3.Connection | None:
        """Lazily open the SQLite reference database.

        If only the .gz archive exists, decompress it first.
        """
        if self._ref_conn is not None:
            return self._ref_conn
        gz_path = self._ref_db_path.with_suffix(".db.gz")
        if not self._ref_db_path.exists() and gz_path.exists():
            logger.info("Decompressing %s ...", gz_path)
            with gzip.open(gz_path, "rb") as f_in, open(self._ref_db_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            logger.info("Decompressed to %s", self._ref_db_path)
        if self._ref_db_path.exists():
            self._ref_conn = sqlite3.connect(str(self._ref_db_path))
            self._ref_conn.row_factory = sqlite3.Row
            logger.info("Reference SQLite loaded: %s", self._ref_db_path)
            return self._ref_conn
        logger.warning("Reference DB not found at %s", self._ref_db_path)
        return None

    def _execute_sqlite(self, sql: str, max_results: int) -> dict:
        """Execute a query against the local SQLite reference database."""
        conn = self._get_ref_conn()
        if conn is None:
            raise RuntimeError(
                f"Reference database not found at {self._ref_db_path}. "
                "Run: python -m patstat_mcp.sync_reference"
            )

        start = time.time()
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        all_rows = cursor.fetchall()
        elapsed = time.time() - start

        total_rows = len(all_rows)
        truncated = total_rows > max_results
        rows = [dict(r) for r in all_rows[:max_results]]

        logger.info(
            "SQLite query took %.2fs (%d rows%s)",
            elapsed,
            total_rows,
            f", truncated to {max_results}" if truncated else "",
        )

        return {
            "rows": rows,
            "total_rows": len(rows),
            "bytes_processed": 0,
            "truncated": truncated,
            "columns": columns,
        }

    def execute_query(
        self,
        sql: str,
        max_results: int = 1000,
        dry_run: bool = False,
        timeout: float = 30,
    ) -> dict:
        """Execute SQL via PatstatClient or SQLite (for reference tables).

        Returns the same dict shape as BigQueryClient.execute_query().
        dry_run is accepted for interface compatibility but just returns zeros.
        """
        if dry_run:
            return {
                "rows": [],
                "total_rows": 0,
                "bytes_processed": 0,
                "truncated": False,
                "columns": [],
                "dry_run": True,
            }

        max_results = min(max_results, MAX_RESULTS_HARD_LIMIT)

        # Route to SQLite if the query only touches reference tables
        tables_used = _tables_in_query(sql)
        ref_tables_used = tables_used & REFERENCE_TABLES
        tip_tables_used = tables_used - REFERENCE_TABLES

        if ref_tables_used and not tip_tables_used:
            # Pure reference query → SQLite
            return self._execute_sqlite(sql, max_results)

        if ref_tables_used and tip_tables_used:
            # Mixed query — can't split across backends
            raise RuntimeError(
                f"Query mixes TIP tables ({', '.join(sorted(tip_tables_used))}) "
                f"with BQ-only reference tables ({', '.join(sorted(ref_tables_used))}). "
                f"Query these separately or use BigQuery for the full query."
            )

        # Pure TIP query → PatstatClient
        client = self._get_client()

        start = time.time()
        result = client.sql_query(sql, use_legacy_sql=False)
        elapsed = time.time() - start

        df = pd.DataFrame(result)
        columns = list(df.columns)
        total_rows = len(df)
        truncated = total_rows > max_results
        rows = df.head(max_results).to_dict("records")

        logger.info(
            "TIP query took %.2fs (%d rows%s)",
            elapsed,
            total_rows,
            f", truncated to {max_results}" if truncated else "",
        )

        return {
            "rows": rows,
            "total_rows": len(rows),
            "bytes_processed": 0,
            "truncated": truncated,
            "columns": columns,
        }
