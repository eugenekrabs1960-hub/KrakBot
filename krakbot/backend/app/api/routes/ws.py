from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_hub import ws_hub

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def market_ws(websocket: WebSocket):
    await ws_hub.connect(websocket)
    try:
        while True:
            # Keepalive + optional future command channel
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_hub.disconnect(websocket)
    except Exception:
        await ws_hub.disconnect(websocket)
