"""Explicit remote transport, restricted to public read-only tools."""
import os
import asyncio
from contextlib import asynccontextmanager, suppress
from . import retrieval
from urllib.parse import urlsplit
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.routing import Route
from .server import server


class AdmissionLimit:
    """Bound active HTTP requests per process; provider rate limits remain required."""
    def __init__(self, app):
        self.app = app
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if self.active >= 4:
            response = JSONResponse({"error": "Server busy; retry later."}, status_code=429,
                                    headers={"Retry-After": "5"})
            return await response(scope, receive, send)
        self.active += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.active -= 1


def create_app():
    origin = os.environ.get("MRX_MCP_PUBLIC_ORIGIN", "http://127.0.0.1:8000")
    parsed = urlsplit(origin)
    local = parsed.hostname in {"127.0.0.1", "localhost"}
    if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("MRX_MCP_PUBLIC_ORIGIN must be an exact HTTPS origin (localhost HTTP allowed).")
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                        allowed_hosts=[parsed.netloc], allowed_origins=[origin])
    app = server.streamable_http_app(stateless_http=True, json_response=True,
                                    max_request_body_size=32768, transport_security=security)

    async def health(request):
        return JSONResponse({"service": "mrx-public", "version": "0.2.0", "status": "running",
                             "read_only": True, "content_readiness": "checked on tool calls"},
                            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})

    app.routes.append(Route("/health", health))
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with original_lifespan(app):
            # Explicit deployment option: do not crawl from unit tests or merely
            # importing the ASGI application. A warm index is process-local.
            task = None
            if os.environ.get("MRX_MCP_PREWARM") == "1":
                await asyncio.to_thread(retrieval.warm_index, max_seconds=180)
                async def maintain_index():
                    while True:
                        await asyncio.sleep(1800)
                        try:
                            await asyncio.to_thread(retrieval.warm_index, max_seconds=180)
                        except Exception:
                            # Tool calls independently fail closed. Do not log
                            # source text, research queries or arbitrary errors.
                            pass
                task = asyncio.create_task(maintain_index())
            try:
                yield
            finally:
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

    app.router.lifespan_context = lifespan
    app.add_middleware(AdmissionLimit)
    return app


def main():
    import uvicorn
    uvicorn.run(create_app(), host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", "8000")), access_log=False)


if __name__ == "__main__":
    main()
