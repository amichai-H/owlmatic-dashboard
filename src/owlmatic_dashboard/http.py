"""ASGI adapter: authentication, bounded decoding, service dispatch, serialization."""

import asyncio
import re
from importlib.resources import files

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .domain import ReceiverError
from .security import Credentials
from .service import ReceiverService
from .wire import StatisticsSnapshot

MAX_BODY_BYTES = 1048576
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    "Referrer-Policy": "no-referrer",
}


def error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"code": code}, status_code=status, headers=HEADERS)


def create_app(service: ReceiverService, credentials: Credentials) -> Starlette:
    async def ingest(request: Request) -> Response:
        if not credentials.authorized(request.headers.get("authorization", ""), write=True):
            return error("UNAUTHORIZED", 401)
        if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
            return error("JSON_REQUIRED", 415)
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BODY_BYTES:
                return error("PAYLOAD_TOO_LARGE", 413)
            data.extend(chunk)
        try:
            snapshot = StatisticsSnapshot.model_validate_json(bytes(data))
        except ValidationError:
            return error("INVALID_SNAPSHOT", 400)
        if request.headers.get("idempotency-key") != snapshot.snapshot_id:
            return error("IDEMPOTENCY_KEY_REQUIRED", 400)
        receipt = await asyncio.to_thread(service.ingest, snapshot)
        return Response(receipt.model_dump_json(), media_type="application/json", headers=HEADERS)

    async def sources(request: Request) -> Response:
        if not credentials.authorized(request.headers.get("authorization", ""), write=False):
            return error("UNAUTHORIZED", 401)
        cursor = request.query_params.get("cursor")
        if cursor is not None and not re.fullmatch(r"[0-9a-f]{32}", cursor):
            return error("INVALID_CURSOR", 400)
        page = await asyncio.to_thread(service.sources, cursor)
        return Response(
            page.model_dump_json(exclude_none=True), media_type="application/json", headers=HEADERS
        )

    async def asset(request: Request) -> Response:
        name = request.path_params.get("name", "index.html")
        allowed = {"index.html": "text/html", "app.js": "text/javascript", "app.css": "text/css"}
        if name not in allowed:
            return error("NOT_FOUND", 404)
        body = files("owlmatic_dashboard.static").joinpath(name).read_bytes()
        return Response(body, media_type=allowed[name], headers=HEADERS)

    async def receiver_error(request: Request, exception: Exception) -> Response:
        if isinstance(exception, ReceiverError):
            return error(exception.code, exception.status)
        return error("INTERNAL_ERROR", 500)

    return Starlette(
        debug=False,
        routes=[
            Route("/api/v1/snapshots", ingest, methods=["POST"]),
            Route("/api/v1/sources", sources),
            Route("/", asset),
            Route("/assets/{name}", asset),
        ],
        exception_handlers={ReceiverError: receiver_error, Exception: receiver_error},
    )
