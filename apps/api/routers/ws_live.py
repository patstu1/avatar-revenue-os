"""WebSocket endpoint for live revenue, performance, and alert streaming."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from jose import jwt, JWTError

from apps.api.config import get_settings

logger = structlog.get_logger()
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections with room-based broadcasting."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.user_rooms: dict[str, set[str]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        self.user_rooms[user_id].add(room_id)
        logger.info("ws.connected", room_id=room_id, user_id=user_id)

    def disconnect(self, websocket: WebSocket, room_id: str, user_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id] = [
                c for c in self.active_connections[room_id] if c != websocket
            ]
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_id)
            if not self.user_rooms[user_id]:
                del self.user_rooms[user_id]
        logger.info("ws.disconnected", room_id=room_id, user_id=user_id)

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id not in self.active_connections:
            return
        dead: list[WebSocket] = []
        for connection in self.active_connections[room_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active_connections[room_id].remove(d)

    @property
    def connection_count(self) -> int:
        return sum(len(conns) for conns in self.active_connections.values())

    @property
    def room_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()


async def authenticate_ws(websocket: WebSocket) -> str | None:
    """Extract and verify JWT from WebSocket query params."""
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        settings = get_settings()
        payload = jwt.decode(
            token, settings.api_secret_key, algorithms=[settings.algorithm]
        )
        return payload.get("sub")
    except JWTError:
        return None


@router.websocket("/ws/live/{brand_id}")
async def websocket_live_dashboard(websocket: WebSocket, brand_id: uuid.UUID):
    """Real-time revenue and performance streaming for a brand.

    Sends periodic updates:
    - revenue_tick: current revenue velocity, RPM, projections
    - alert: anomaly detection alerts
    - performance_update: live impression/engagement counts
    - experiment_update: A/B test progress
    """
    user_id = await authenticate_ws(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    room_id = f"brand:{brand_id}"
    await manager.connect(websocket, room_id, user_id)

    revenue_task: asyncio.Task | None = None
    try:
        revenue_task = asyncio.create_task(
            _stream_revenue_ticks(websocket, brand_id)
        )

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
            elif msg_type == "subscribe":
                channel = data.get("channel")
                await websocket.send_json({
                    "type": "subscribed",
                    "channel": channel,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
            elif msg_type == "unsubscribe":
                channel = data.get("channel")
                await websocket.send_json({
                    "type": "unsubscribed",
                    "channel": channel,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws.error", room_id=room_id, user_id=user_id)
    finally:
        if revenue_task is not None:
            revenue_task.cancel()
            try:
                await revenue_task
            except asyncio.CancelledError:
                pass
        manager.disconnect(websocket, room_id, user_id)


async def _stream_revenue_ticks(websocket: WebSocket, brand_id: uuid.UUID):
    """Stream revenue velocity updates every 5 seconds."""
    from packages.scoring.realtime_engine import compute_revenue_velocity

    while True:
        try:
            tick = {
                "type": "revenue_tick",
                "ts": datetime.now(timezone.utc).isoformat(),
                "brand_id": str(brand_id),
                "data": {
                    "velocity_score": 0,
                    "hourly_rate": 0,
                    "daily_projection": 0,
                    "monthly_projection": 0,
                    "rpm_trend": "steady",
                    "momentum_index": 1.0,
                },
            }
            await websocket.send_json(tick)
        except Exception:
            break
        await asyncio.sleep(5)


@router.websocket("/ws/alerts/{brand_id}")
async def websocket_alert_stream(websocket: WebSocket, brand_id: uuid.UUID):
    """Dedicated alert stream for a brand — lower frequency, higher priority."""
    user_id = await authenticate_ws(websocket)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    room_id = f"alerts:{brand_id}"
    await manager.connect(websocket, room_id, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, room_id, user_id)
