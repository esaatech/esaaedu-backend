"""Gunicorn worker for the Cloud Run ASGI app.

Each worker process has its own event loop and its own Django sync thread.
A request stuck in that thread only blocks its own worker. The heartbeat
below runs on the event loop, so Gunicorn recycles a worker whose loop has
stopped responding and the other worker keeps serving.
"""

import asyncio

from uvicorn.workers import UvicornWorker


class CloudRunUvicornWorker(UvicornWorker):
    async def _heartbeat(self) -> None:
        while True:
            self.notify()
            await asyncio.sleep(15)

    async def _serve(self) -> None:
        heartbeat = asyncio.create_task(self._heartbeat())
        try:
            await super()._serve()
        finally:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
