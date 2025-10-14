from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from admin.handlers.unified_websocket import admin_websocket_handler

def create_admin_app() -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws")
    async def root(websocket: WebSocket):
        await admin_websocket_handler(websocket)

    return app