import uuid
from typing import Dict, Any, List
from datetime import datetime
from src.graph.builder import app as graph_app

class SessionService:
    """会话管理服务"""

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, user_id: str = None) -> Dict[str, Any]:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "messages": [],
            "graph_state": None
        }
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """获取会话"""
        return self.sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """添加消息"""
        if session_id in self.sessions:
            self.sessions[session_id]["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })

    async def send_message(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """发送消息并执行 Graph"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 添加用户消息
        self.add_message(session_id, "user", user_input)

        # 获取之前的状态
        initial_state = session.get("graph_state") or {
            "session_id": session_id,
            "user_input": user_input,
            "conversation_history": session["messages"][:-1],
            "clarification_count": 0
        }

        # 更新 user_input
        initial_state["user_input"] = user_input

        # 执行 Graph
        result = await graph_app.ainvoke(initial_state)

        # 保存状态
        session["graph_state"] = result

        # 检查是否需要澄清
        ambiguity = result.get("ambiguity", {})
        if ambiguity and ambiguity.get("has_ambiguity", False):
            from src.tools.clarification_generator import generate_clarification_options
            clarification = generate_clarification_options.func(
                ambiguity_type=ambiguity.get("type", "time"),
                context=ambiguity.get("options", {})
            )
            return {
                "status": "waiting_for_clarification",
                "clarification": {
                    "question": clarification.question,
                    "options": clarification.options,
                    "allow_custom_input": clarification.allow_custom_input
                }
            }

        # 返回结果
        return {
            "status": "completed",
            "result": {
                "query_intent": result.get("query_intent"),
                "query_request": result.get("query_request"),
                "query_result": result.get("query_result", {}),
                "analysis": result.get("analysis", {}),
                "warnings": result.get("query_warnings", [])
            }
        }

    async def submit_clarification(self, session_id: str, selected_value: str) -> Dict[str, Any]:
        """提交澄清并继续执行"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        state = session.get("graph_state", {})
        state["user_feedback"] = {"selected_value": selected_value}

        # 继续执行 Graph（从 hitl 节点之后）
        result = await graph_app.ainvoke(state)
        session["graph_state"] = result

        return {
            "status": "completed",
            "result": {
                "query_intent": result.get("query_intent"),
                "query_request": result.get("query_request")
            }
        }

# 单例
session_service = SessionService()
