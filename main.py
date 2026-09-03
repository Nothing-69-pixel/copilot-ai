import json
import uuid
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class CopilotHTTPClient:
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
        return self.conversation_id

    def ask(self, message: str):
        try:
            # HTTP API endpoint (not WebSocket)
            url = "https://copilot.microsoft.com/c/api/chat"
            
            headers = {
                "User-Agent": "CopilotNative/30.0.440421003-prod (Android 11; Google; sdk_gphone_arm64)",
                "Content-Type": "application/json",
                "X-Search-UILang": "en-US",
                "X-Client-Id": self.client_id,
                "X-Conversation-Id": self.conversation_id
            }
            
            payload = {
                "message": message,
                "conversationId": self.conversation_id,
                "clientId": self.client_id
            }
            
            response = self.session.post(url, json=payload, headers=headers, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "text": data.get("text", ""),
                    "message_id": data.get("messageId", str(uuid.uuid4()))
                }
            else:
                return {
                    "text": f"Error: {response.status_code}",
                    "message_id": None
                }
        except Exception as e:
            return {
                "text": f"Error: {str(e)}",
                "message_id": None
            }

# Global client
copilot_client = CopilotHTTPClient()

@app.get("/")
async def root():
    return {"status": "ok", "message": "Copilot API is running on Vercel"}

@app.get("/api/chat")
async def chat_get(message: str = Query(..., description="Your message")):
    try:
        result = copilot_client.ask(message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_post(request: ChatRequest):
    try:
        result = copilot_client.ask(request.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
