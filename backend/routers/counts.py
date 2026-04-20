import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.counting_service import get_or_create_service

router = APIRouter()


@router.websocket("/ws/counts")
async def websocket_counts(websocket: WebSocket, profile_id: str):
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    svc = get_or_create_service(profile_id)
    svc.subscribe(queue)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                await websocket.send_text(json.dumps(event))
            except asyncio.TimeoutError:
                # send a keepalive ping so the browser doesn't close the socket
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        svc.unsubscribe(queue)
