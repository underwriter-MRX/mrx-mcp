"""Cold stdio test. Pass --live to verify production discovery and a public page."""
import asyncio
import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "mrx_mcp.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=180) as session:
            init = await session.initialize()
            tools = (await session.list_tools()).tools
            assert sorted(t.name for t in tools) == ["fetch", "mrx_get_started", "mrx_read_page", "mrx_search_guides", "mrx_status", "search"]
            assert all(t.output_schema for t in tools if t.name in {"search", "fetch"})
            assert all(t.annotations.read_only_hint and not t.annotations.destructive_hint for t in tools)
            assert len((await session.list_resources()).resources) == 1
            assert len((await session.list_prompts()).prompts) == 1
            await session.read_resource("mrx://about")
            for url in ["https://mineralrightsxchange.com/account/", "https://example.com/", "https://mineralrightsxchange.com//staff/"]:
                result = await session.call_tool("mrx_read_page", {"url": url})
                assert result.is_error
            summary = {"server": init.server_info.name, "tools": [t.name for t in tools], "private_and_cross_origin_rejected": True}
            if "--live" in sys.argv:
                for name, args in [("mrx_status", {}), ("mrx_search_guides", {"query": "inherited rights", "limit": 3}), ("mrx_get_started", {})]:
                    result = await session.call_tool(name, args)
                    assert not result.is_error, result
                    summary[name] = "passed"
            print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
