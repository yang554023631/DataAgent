from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.services.session_service import session_service

router = APIRouter(prefix="/api/sessions", tags=["streaming"])


class StreamMessageRequest(BaseModel):
    content: str


@router.post("/{session_id}/messages/stream")
async def stream_message(session_id: str, req: StreamMessageRequest):
    """发送消息并获取 SSE 流式响应"""
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        session_service.stream_message(session_id, req.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
