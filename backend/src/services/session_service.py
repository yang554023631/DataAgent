import uuid
import json
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from datetime import datetime
from src.graph.builder import app as graph_app
from src.graph.callbacks import get_logging_callbacks

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

        # 执行 Graph（使用 thread_id 管理 checkpoint，中断后可恢复）
        result = await graph_app.ainvoke(
            initial_state,
            config={
                "callbacks": get_logging_callbacks(),
                "configurable": {"thread_id": session_id},
            },
        )

        # 保存状态
        session["graph_state"] = result

        # 检查是否需要澄清 - 优先使用新的 needs_clarification 字段
        needs_clarification = result.get("needs_clarification", False)
        # 向后兼容：如果旧的 ambiguity 字段存在且有数据，也处理
        ambiguity = result.get("ambiguity", {})

        if needs_clarification or (ambiguity and ambiguity.get("has_ambiguity", False)):
            # 获取澄清信息
            clarification_info = result.get("clarification", {})

            # 如果是旧格式，生成澄清信息（向后兼容）
            if not clarification_info and ambiguity and ambiguity.get("has_ambiguity", False):
                from src.tools.clarification_generator import generate_clarification_options
                # context 需要是 dict，options 是 list，需要包装一下
                options = ambiguity.get("options", [])
                # 把广告主选项转换成澄清问题的格式
                formatted_options = []
                for opt in options:
                    if isinstance(opt, dict) and "name" in opt and "id" in opt:
                        formatted_options.append({
                            "value": f"查看 {opt['name']} 的数据",
                            "label": opt["name"]
                        })
                context = {
                    "question": ambiguity.get("reason", "未找到匹配的广告主"),
                    "options": formatted_options
                }
                clarification = generate_clarification_options.func(
                    ambiguity_type=ambiguity.get("type", "time"),
                    context=context
                )
                clarification_info = {
                    "question": clarification.question,
                    "options": clarification.options,
                    "allow_custom_input": clarification.allow_custom_input
                }

            # 构建返回结果
            response = {
                "status": "waiting_for_clarification",
                "clarification": {
                    "question": clarification_info.get("question", "需要您的澄清"),
                    "options": clarification_info.get("options", []),
                    "allow_custom_input": clarification_info.get("allow_custom_input", True)
                }
            }

            # 如果存在 final_report，也包含进去（某些澄清类型可能已经生成了报告）
            if result.get("final_report"):
                response["result"] = {
                    "final_report": result.get("final_report"),
                    "warnings": result.get("query_warnings", [])
                }

            return response

        # 返回结果
        return {
            "status": "completed",
            "result": {
                "query_intent": result.get("query_intent"),
                "query_request": result.get("query_request"),
                "query_result": result.get("query_result", {}),
                "analysis": result.get("analysis_result", {}),
                "final_report": result.get("final_report"),
                "warnings": result.get("query_warnings", [])
            }
        }

    async def submit_clarification(self, session_id: str, selected_value: str) -> Dict[str, Any]:
        """提交澄清并继续执行"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        state = session.get("graph_state", {})

        # 检查是否超限重置
        clarify_next = state.get("clarify_next")
        if clarify_next == "max_reentry_exceeded":
            # 重置后用新的输入重新开始一轮
            state = {
                "session_id": session_id,
                "user_input": selected_value,
                "conversation_history": session.get("messages", []),
                "clarification_count": 0,
                "reentry_count": 0,
            }
            result = await graph_app.ainvoke(
                state,
                config={
                    "callbacks": get_logging_callbacks(),
                    "configurable": {"thread_id": session_id},
                },
            )
            session["graph_state"] = result
        else:
            # 将用户反馈写入 state，然后恢复 graph 执行
            # 先用 update_state 注入用户反馈
            graph_app.update_state(
                {"configurable": {"thread_id": session_id}},
                {"user_feedback": {"selected_value": selected_value}},
            )
            # 从中断点（clarify 节点）继续执行
            result = await graph_app.ainvoke(
                None,
                config={
                    "callbacks": get_logging_callbacks(),
                    "configurable": {"thread_id": session_id},
                },
            )
            session["graph_state"] = result

        # 检查是否仍然需要澄清
        needs_clarification = result.get("needs_clarification", False)
        if needs_clarification:
            clarification_info = result.get("clarification", {})
            return {
                "status": "waiting_for_clarification",
                "clarification": {
                    "question": clarification_info.get("question", "需要您的澄清"),
                    "options": clarification_info.get("options", []),
                    "allow_custom_input": clarification_info.get("allow_custom_input", True)
                }
            }

        # 返回最终结果
        return {
            "status": "completed",
            "result": {
                "query_intent": result.get("query_intent"),
                "query_request": result.get("query_request"),
                "query_result": result.get("query_result", {}),
                "analysis": result.get("analysis_result", {}),
                "final_report": result.get("final_report"),
                "warnings": result.get("query_warnings", [])
            }
        }

    async def stream_message(self, session_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """发送消息并流式返回执行进度"""
        session = self.get_session(session_id)
        if not session:
            # 发送错误事件
            yield f"data: {json.dumps({'type': 'error', 'message': f'Session {session_id} not found'})}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            return

        try:
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
            result = await graph_app.ainvoke(
                initial_state,
                config={
                    "callbacks": get_logging_callbacks(),
                    "configurable": {"thread_id": session_id},
                },
            )

            # 保存状态
            session["graph_state"] = result

            # 从 execution_trace 回放步骤
            execution_trace = result.get("execution_trace", [])
            for step in execution_trace:
                step_name = step.get("step")
                status = step.get("status")

                if status == "started":
                    # 步骤开始事件
                    yield f"data: {json.dumps({'type': 'step_start', 'step': step_name, 'status': 'started'})}\n\n"
                else:
                    # 步骤完成事件
                    event_data = {
                        "type": "step_complete",
                        "step": step_name,
                        "status": status
                    }
                    if "duration_ms" in step:
                        event_data["duration_ms"] = step["duration_ms"]
                    yield f"data: {json.dumps(event_data)}\n\n"

                # 小延迟制造流式效果
                await asyncio.sleep(0.1)

            # 发送 CoT reasoning 事件（如果有）
            cot_reasoning = result.get("cot_reasoning")
            if cot_reasoning:
                yield f"data: {json.dumps({'type': 'cot_reasoning', 'data': cot_reasoning})}\n\n"

            # 检查是否需要澄清
            needs_clarification = result.get("needs_clarification", False)
            ambiguity = result.get("ambiguity", {})

            if needs_clarification or (ambiguity and ambiguity.get("has_ambiguity", False)):
                # 获取澄清信息
                clarification_info = result.get("clarification", {})

                # 向后兼容
                if not clarification_info and ambiguity and ambiguity.get("has_ambiguity", False):
                    from src.tools.clarification_generator import generate_clarification_options
                    options = ambiguity.get("options", [])
                    formatted_options = []
                    for opt in options:
                        if isinstance(opt, dict) and "name" in opt and "id" in opt:
                            formatted_options.append({
                                "value": f"查看 {opt['name']} 的数据",
                                "label": opt["name"]
                            })
                    context = {
                        "question": ambiguity.get("reason", "未找到匹配的广告主"),
                        "options": formatted_options
                    }
                    clarification = generate_clarification_options.func(
                        ambiguity_type=ambiguity.get("type", "time"),
                        context=context
                    )
                    clarification_info = {
                        "question": clarification.question,
                        "options": clarification.options,
                        "allow_custom_input": clarification.allow_custom_input
                    }

                # 发送澄清事件
                yield f"data: {json.dumps({'type': 'hitl', 'question': clarification_info.get('question'), 'options': clarification_info.get('options', [])})}\n\n"

                # 如果存在 final_report，也发送
                if result.get("final_report"):
                    yield f"data: {json.dumps({'type': 'final_report', 'data': result.get('final_report')})}\n\n"
            else:
                # 发送最终报告
                final_report = result.get("final_report")
                if final_report:
                    yield f"data: {json.dumps({'type': 'final_report', 'data': final_report})}\n\n"

            # 完成事件
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # 错误事件
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

# 单例
session_service = SessionService()
