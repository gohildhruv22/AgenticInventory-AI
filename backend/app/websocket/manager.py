import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("agenticinventory")


class ConnectionManager:
    """Manages native FastAPI WebSocket connections with room support."""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}  # room -> websockets
        self._user_rooms: dict[WebSocket, set[str]] = {}  # websocket -> rooms

    async def connect(self, websocket: WebSocket, room: str = "general") -> None:
        await websocket.accept()
        if room not in self._connections:
            self._connections[room] = set()
        self._connections[room].add(websocket)
        if websocket not in self._user_rooms:
            self._user_rooms[websocket] = set()
        self._user_rooms[websocket].add(room)
        logger.info(f"WebSocket connected to room '{room}'. Total in room: {len(self._connections[room])}")

    def disconnect(self, websocket: WebSocket) -> None:
        rooms = self._user_rooms.pop(websocket, set())
        for room in rooms:
            if room in self._connections:
                self._connections[room].discard(websocket)
                if not self._connections[room]:
                    del self._connections[room]
        logger.info("WebSocket disconnected")

    async def join_room(self, websocket: WebSocket, room: str) -> None:
        if room not in self._connections:
            self._connections[room] = set()
        self._connections[room].add(websocket)
        if websocket not in self._user_rooms:
            self._user_rooms[websocket] = set()
        self._user_rooms[websocket].add(room)

    async def leave_room(self, websocket: WebSocket, room: str) -> None:
        if room in self._connections:
            self._connections[room].discard(websocket)
        if websocket in self._user_rooms:
            self._user_rooms[websocket].discard(room)

    async def broadcast(self, room: str, event: str, data: Any) -> None:
        message = {"event": event, "data": data}
        if room not in self._connections:
            return
        dead = []
        for ws in self._connections[room]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_all(self, event: str, data: Any) -> None:
        for room in list(self._connections.keys()):
            await self.broadcast(room, event, data)


ws_manager = ConnectionManager()
