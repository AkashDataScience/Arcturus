"""Nexus gateway router.

Exposes the Unified Message Bus over HTTP so the WebChat widget (and future
channel adapters) can send/receive messages through the Arcturus agent core.

Endpoints
---------
POST /api/nexus/webchat/inbound
    Receive an inbound WebChat message, route it through the bus (agent
    processing + outbound delivery to the session outbox).

GET  /api/nexus/webchat/messages/{session_id}
    Poll for queued outbound messages for a WebChat session. Each call drains
    and returns all pending messages (fire-and-forget delivery model).
"""

import uuid
import asyncio
from typing import Optional, Any

from fastapi import APIRouter, File, UploadFile, Form, BackgroundTasks
from pydantic import BaseModel

from gateway.envelope import MessageEnvelope
from routers.remme import background_smart_scan

router = APIRouter(prefix="/nexus", tags=["Nexus"])

# Lazy reference to the shared MessageBus singleton.
# We defer import so that this module can be imported safely at startup
# before gateway components are fully initialized.
_bus = None


def _get_bus():
    global _bus
    if _bus is None:
        from shared.state import get_message_bus
        _bus = get_message_bus()
    return _bus


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class WebChatInboundRequest(BaseModel):
    """Inbound WebChat message from the widget."""

    session_id: str
    sender_id: str
    sender_name: str
    text: str
    message_id: Optional[str] = None


class MobileInboundRequest(BaseModel):
    """Inbound context from the mobile app."""

    session_id: str
    text: str
    sender_id: str = "mobile-user"
    sender_name: str = "Mobile User"
    device_type: str = "mobile"
    message_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/webchat/inbound")
async def webchat_inbound(req: WebChatInboundRequest, background_tasks: BackgroundTasks):
    """Receive a message from the WebChat widget.

    Builds a ``MessageEnvelope``, runs it through the bus (agent processing +
    formatted reply enqueued in the session outbox), and returns the bus result.

    The widget should follow up with GET ``/api/nexus/webchat/messages/{session_id}``
    to fetch the agent's reply.
    """
    envelope = MessageEnvelope.from_webchat(
        session_id=req.session_id,
        sender_id=req.sender_id,
        sender_name=req.sender_name,
        text=req.text,
        message_id=req.message_id or str(uuid.uuid4()),
    )
    result = await _get_bus().roundtrip(envelope)
    
    # 🧠 Trigger Mnemo Memory Sync
    background_tasks.add_task(background_smart_scan)
    
    return result.to_dict()


@router.get("/webchat/messages/{session_id}")
async def webchat_poll(session_id: str):
    """Poll for pending outbound messages for a WebChat session.

    Drains the session outbox — each message is returned exactly once.
    Returns an empty list if no messages are queued.
    """
    bus = _get_bus()
    adapter = bus.adapters.get("webchat")
    messages = adapter.drain_outbox(session_id) if adapter else []
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }


@router.post("/mobile/inbound")
async def mobile_inbound(req: MobileInboundRequest, background_tasks: BackgroundTasks):
    """Receive a message from the mobile app.

    Routes a ``MessageEnvelope`` through the bus with mobile channel identity.
    """
    envelope = MessageEnvelope.from_mobile(
        session_id=req.session_id,
        sender_id=req.sender_id,
        sender_name=req.sender_name,
        text=req.text,
        message_id=req.message_id or str(uuid.uuid4()),
        device_type=req.device_type,
    )
    result = await _get_bus().roundtrip(envelope)

    # 🧠 Trigger Mnemo Memory Sync
    background_tasks.add_task(background_smart_scan)

    return result.to_dict()


@router.post("/mobile/voice/inbound")
async def mobile_voice_inbound(
    background_tasks: BackgroundTasks,
    session_id: str = Form("mobile-session-1"),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    """Receive a voice clip or transcribed text from the mobile app.
    
    If 'text' is provided (client-side STT), it uses it directly.
    Otherwise, it attempts to transcribe the 'file'.
    """
    if text:
        transcription = text
        print(f"🎙️ [Nexus] Received direct text from client: '{transcription}'")
    elif file:
        # Placeholder for server-side transcription
        # For now, we still mock it, but we prepare the slot for Whisper/Deepgram
        transcription = "[Voice Clip Received]"
        print(f"🎙️ [Nexus] Received audio file: {file.filename}")
    else:
        transcription = "..."

    envelope = MessageEnvelope.from_mobile(
        session_id=session_id,
        sender_id="mobile-user",
        sender_name="Mobile User",
        text=transcription,
        message_id=str(uuid.uuid4()),
    )
    
    result = await _get_bus().roundtrip(envelope)
    
    # Extract the reply text from the agent response
    reply_text = "Arcturus is listening."
    if result and result.success:
        reply_text = result.formatted_text or result.agent_response.get("reply", reply_text)

    # 🧠 Trigger Mnemo Memory Sync
    background_tasks.add_task(background_smart_scan)

    return {
        "status": "ok",
        "transcription": transcription,
        "reply": reply_text,
        "session_id": session_id
    }


@router.get("/mobile/messages/{session_id}")
async def mobile_poll(session_id: str):
    """Poll for pending outbound messages for a mobile session.
    """
    bus = _get_bus()
    adapter = bus.adapters.get("mobile")
    # If no specialized mobile adapter, fallback to webchat for now
    if not adapter:
        adapter = bus.adapters.get("webchat")
    
    messages = adapter.drain_outbox(session_id) if adapter else []
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }
