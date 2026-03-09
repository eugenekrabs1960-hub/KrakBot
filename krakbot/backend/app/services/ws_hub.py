import asyncio
import json
from collections.abc import Iterable
from fastapi import WebSocket


class WsHub:
    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event: dict):
        message = json.dumps(event)
        dead: list[WebSocket] = []
        async with self._lock:
            clients: Iterable[WebSocket] = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


ws_hub = WsHub()
