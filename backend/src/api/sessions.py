from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from src.services.session_service import session_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

class CreateSessionRequest(BaseModel):
    user_id: Optional[str] = None

class SendMessageRequest(BaseModel):
    content: str

class SubmitClarificationRequest(BaseModel):
    selected_value: str

@router.post("")
async def create_session(req: CreateSessionRequest = Body(...)):
    """创建新会话"""
    session = session_service.create_session(req.user_id)
    return {
        "session_id": session["session_id"],
        "user_id": session["user_id"],
        "created_at": session["created_at"]
    }

@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取会话信息"""
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session["session_id"],
        "user_id": session["user_id"],
        "created_at": session["created_at"],
        "message_count": len(session["messages"])
    }

@router.post("/{session_id}/messages")
async def send_message(session_id: str, req: SendMessageRequest):
    """发送消息"""
    try:
        result = await session_service.send_message(session_id, req.content)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{session_id}/clarification")
async def submit_clarification(session_id: str, req: SubmitClarificationRequest):
    """提交澄清"""
    try:
        result = await session_service.submit_clarification(session_id, req.selected_value)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
