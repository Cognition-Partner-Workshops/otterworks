"""Query both local MCP servers; run with the postgres-mcp image's Python SDK."""

import asyncio
import json

from mcp import ClientSession
from mcp.client.sse import sse_client


async def query(url, name, arguments):
    async with sse_client(url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            tool = next(t for t in tools if t.name == name)
            print(json.dumps({"server": url, "tool": name, "schema": tool.inputSchema}))
            result = await session.call_tool(name, arguments)
            if result.isError:
                raise RuntimeError(result.model_dump_json())
            print(result.model_dump_json())


async def main():
    await query(
        "http://127.0.0.1:8000/sse",
        "query_prometheus",
        {"datasourceUid": "Prometheus", "expr": "up", "queryType": "instant", "startTime": "now"},
    )
    await query(
        "http://127.0.0.1:8001/sse",
        "execute_sql",
        {"sql": "SELECT current_database() AS database, count(*) AS documents FROM documents"},
    )


if __name__ == "__main__":
    asyncio.run(main())
