import json
import uuid
import requests
import websocket
import threading
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class CopilotClient:
    def __init__(self):
        self.session = requests.Session()
        self.client_id = str(uuid.uuid4())
        self.conversation_id = None
        self._start_conversation()

    def _start_conversation(self):
        url = "https://copilot.microsoft.com/c/api/start"

        payload = {
            "timeZone": "Asia/Kolkata",
            "startNewConversation": True,
            "teenSupportEnabled": True,
            "correctPersonalizationSetting": True,
            "deferredDataUseCapable": True
        }

        headers = {
            "User-Agent": "CopilotNative/30.0.440421003-prod (Android 11; Google; sdk_gphone_arm64)",
            "Content-Type": "application/json",
            "X-Search-UILang": "en-US"
        }

        r = self.session.post(url, json=payload, headers=headers)
        self.conversation_id = r.json()["currentConversationId"]

    def ask(self, message: str):
        ws_url = f"wss://copilot.microsoft.com/c/api/chat?api-version=2&clientSessionId={self.client_id}"
        cookies = "; ".join([f"{k}={v}" for k, v in self.session.cookies.get_dict().items()])

        result = {
            "text": "",
            "message_id": None
        }

        done_event = threading.Event()

        def send_message(ws):
            ws.send(json.dumps({
                "event": "send",
                "content": [{"type": "text", "text": message}],
                "conversationId": self.conversation_id
            }))

        def on_open(ws):
            options = {
                "event": "setOptions",
                "supportedCards": [
                    "createCalendarEvent","consentV2","finance","flashcard",
                    "image","local","personalArtifacts","quiz","recipe",
                    "safetyHelpline","sports","tapToReveal","video","navigation"
                ],
                "supportedActions": [],
                "supportedFeatures": [
                    "composer-prefill-conversation-action",
                    "composer-send-conversation-action-v2",
                    "short-conversation-action",
                    "session-duration-nudge"
                ]
            }

            ws.send(json.dumps(options))
            ws.send(json.dumps(options))

            send_message(ws)

        def on_message(ws, msg):
            data = json.loads(msg)

            if data.get("event") == "startMessage":
                result["message_id"] = data["messageId"]

            elif data.get("event") == "appendText":
                if data.get("messageId") == result["message_id"]:
                    text = data.get("text", "")
                    result["text"] += text

            elif data.get("event") == "done":
                ws.close()
                done_event.set()

        def on_error(ws, err):
            print(f"WebSocket error: {err}")
            done_event.set()

        ws = websocket.WebSocketApp(
            ws_url,
            header=[
                f"Cookie: {cookies}",
                "User-Agent: CopilotNative/30.0.440421003-prod (Android 11; Google; sdk_gphone_arm64)",
                "X-Search-UILang: en-US"
            ],
            on_open=on_open,
            on_message=on_message,
            on_error=on_error
        )

        thread = threading.Thread(target=ws.run_forever)
        thread.start()

        # Wait with timeout (30 seconds)
        done_event.wait(timeout=30)

        if not done_event.is_set():
            ws.close()
            if not result["text"]:
                result["text"] = "Timeout: Copilot took too long to respond"

        return result

# Global client instance
copilot_client = CopilotClient()

@app.get("/")
async def root():
    return {"status": "ok", "message": "Copilot API is running. Use /api/chat?message=your_text"}

@app.get("/api/chat")
async def chat_get(message: str = Query(..., description="Your message to Copilot")):
    try:
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, copilot_client.ask, message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_post(request: ChatRequest):
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, copilot_client.ask, request.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    return {"status": "healthy"}
