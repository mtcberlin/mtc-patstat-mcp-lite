# Dockerfile for patstat-mcp-lite (primarily for local testing).
# Inside TIP, install via: pip install git+https://github.com/mtcberlin/mtc-patstat-mcp-lite.git@develop
#
#   docker build -t patstat-mcp-lite .
#   docker run -p 8080:8080 patstat-mcp-lite
#
# Note: execute_query only works inside EPO TIP (epo.tipdata.patstat required).
# Schema discovery tools (list_tables, get_table_schema, etc.) work everywhere.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
COPY config/ config/
COPY data/ data/

RUN pip install --no-cache-dir .

ENV CONTEXT_DIR=/app/data

EXPOSE 8080

CMD ["patstat-mcp-lite", "--http", "--port", "8080"]
