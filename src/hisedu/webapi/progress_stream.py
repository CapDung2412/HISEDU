from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .errors import WebApiError


ProgressStage = Literal[
    "received",
    "retrieval",
    "generation",
    "enrichment",
    "finalizing",
]

_END = object()


class ProgressChannel:
    """Small, request-local channel used by the SSE response.

    Image bytes never enter the queue. Partial lesson payloads are accepted
    only after the caller has applied the same server-side sanitization used
    for the final response.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue(maxsize=16)
        self._closed = False

    async def publish(self, stage: ProgressStage, message: str) -> None:
        if self._closed:
            return
        await self._queue.put(
            {"type": "progress", "stage": stage, "message": message}
        )

    async def publish_partial(self, payload: BaseModel | dict[str, Any]) -> None:
        """Publish usable lesson content while optional enrichment continues."""

        if self._closed:
            return
        data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        await self._queue.put({"type": "partial_result", "data": data})

    async def finish(self, payload: BaseModel | dict[str, Any]) -> None:
        if self._closed:
            return
        data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        await self._queue.put({"type": "result", "data": data})
        await self.close()

    async def fail(
        self, *, code: str, message: str, request_id: str, status: int
    ) -> None:
        if self._closed:
            return
        await self._queue.put(
            {
                "type": "error",
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id,
                    "status": status,
                },
            }
        )
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._queue.put(_END)

    async def events(self) -> AsyncIterator[bytes]:
        # An opening comment makes proxies flush the response headers early.
        yield b": connected\n\n"
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                # Keep long OpenAI/retrieval requests alive without inventing
                # a fake stage transition in the UI.
                yield b": keep-alive\n\n"
                continue
            if item is _END:
                break
            encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
            yield f"data: {encoded}\n\n".encode("utf-8")


async def publish_progress(
    request: Any, stage: ProgressStage, message: str
) -> None:
    channel = getattr(request.state, "progress_channel", None)
    if isinstance(channel, ProgressChannel):
        await channel.publish(stage, message)


async def publish_partial_result(
    request: Any, payload: BaseModel | dict[str, Any]
) -> None:
    channel = getattr(request.state, "progress_channel", None)
    if isinstance(channel, ProgressChannel):
        await channel.publish_partial(payload)


def stream_operation(
    *,
    request: Any,
    request_id: str,
    operation: Callable[[], Awaitable[BaseModel | dict[str, Any]]],
) -> StreamingResponse:
    """Run an existing endpoint operation and expose progress over SSE.

    Existing JSON endpoints remain untouched. Stream errors are terminal SSE
    events because HTTP headers have already been sent by that point.
    """

    channel = ProgressChannel()
    request.state.progress_channel = channel

    async def run() -> None:
        try:
            await channel.publish("received", "Đã tiếp nhận câu hỏi.")
            result = await operation()
        except WebApiError as exc:
            await channel.fail(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                status=exc.status_code,
            )
        except RequestValidationError:
            await channel.fail(
                code="INVALID_REQUEST",
                message="Dữ liệu gửi lên không hợp lệ.",
                request_id=request_id,
                status=422,
            )
        except asyncio.CancelledError:
            await channel.close()
            raise
        except Exception:
            await channel.fail(
                code="INTERNAL_ERROR",
                message="Đã xảy ra lỗi. Vui lòng thử lại sau.",
                request_id=request_id,
                status=500,
            )
        else:
            await channel.finish(result)

    async def event_stream() -> AsyncIterator[bytes]:
        worker = asyncio.create_task(run(), name=f"hisedu-stream-{request_id}")
        try:
            async for event in channel.events():
                yield event
        finally:
            if not worker.done():
                worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
