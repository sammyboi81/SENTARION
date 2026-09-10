# Glama / Smithery container build for the free, open-source line (Apache-2.0).
# stdio MCP server: the host talks JSON-RPC over stdin/stdout. Nothing paid is in this image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .
RUN python -m pip install --no-cache-dir .

CMD ["sentarion"]
