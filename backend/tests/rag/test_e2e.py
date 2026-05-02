"""RAG 系统端到端集成测试"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.rag.database import init_db, get_db_session
from src.rag.sync import DocumentSyncer
from src.rag.retriever import RagRetriever
from src.rag.agents import IntentRouter, RagAnswerGenerator
from src.graph.builder import build_graph


@pytest.fixture(scope="module")
def test_docs_dir():
    """创建测试文档目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建子目录和测试文档
        concept_dir = Path(tmpdir) / "01_基础概念"
        concept_dir.mkdir()

        # 创建测试文档
        ctr_doc = concept_dir / "CTR是什么.md"
        ctr_doc.write_text("""# 点击率 CTR

## 定义
CTR（Click-Through Rate，点击率）是广告点击量除以曝光量的百分比。

## 计算公式
CTR = 点击次数 / 曝光次数 × 100%

## 行业参考值
搜索广告：2% - 5%
信息流广告：0.5% - 2%
""")

        roi_doc = concept_dir / "ROI是什么.md"
        roi_doc.write_text("""# 投资回报率 ROI

## 定义
ROI（Return on Investment，投资回报率）是衡量广告投放效益的核心指标。

## 计算公式
ROI = (总收入 - 总花费) / 总花费 × 100%
""")

        yield Path(tmpdir)


@pytest.fixture(scope="module")
def synced_db(test_docs_dir):
    """初始化同步后的数据库"""
    init_db()
    session = get_db_session()

    # 同步测试文档
    syncer = DocumentSyncer(docs_dir=test_docs_dir)
    syncer.sync_all(session)

    yield session
    session.close()


class TestSyncE2E:
    """同步流程端到端测试"""

    def test_full_sync_flow(self, test_docs_dir):
        """测试完整同步流程"""
        init_db()
        session = get_db_session()

        syncer = DocumentSyncer(docs_dir=test_docs_dir)
        count = syncer.sync_all(session)

        assert count == 2  # 两个测试文档

        from src.rag.models import RagDocument
        docs = session.query(RagDocument).all()
        assert len(docs) == 2

        # 验证分片存在
        for doc in docs:
            assert len(doc.chunks) > 0
            for chunk in doc.chunks:
                assert chunk.embedding is not None
                assert len(chunk.embedding) > 0

        session.close()

    def test_incremental_sync(self, test_docs_dir):
        """测试增量同步"""
        init_db()
        session = get_db_session()

        syncer = DocumentSyncer(docs_dir=test_docs_dir)

        # 第一次同步
        count1 = syncer.sync_all(session)
        assert count1 == 2

        # 修改一个文档
        ctr_file = test_docs_dir / "01_基础概念" / "CTR是什么.md"
        content = ctr_file.read_text(encoding="utf-8")
        ctr_file.write_text(content + "\n\n新增内容")

        # 第二次同步（增量）
        count2 = syncer.sync_all(session, incremental=True)
        assert count2 == 2  # 所有文件都会被检查，但只有一个会更新

        session.close()


class TestRetrievalE2E:
    """检索流程端到端测试"""

    def test_vector_search(self, synced_db):
        """测试向量检索功能"""
        retriever = RagRetriever()
        results = retriever.search("什么是 CTR", synced_db)

        assert len(results) > 0
        # 结果应该包含 CTR 相关内容
        contents = [r.content for r in results]
        assert any("CTR" in c or "点击率" in c for c in contents)

    def test_retrieval_with_doc_type(self, synced_db):
        """测试按文档类型过滤检索"""
        retriever = RagRetriever()
        results = retriever.search("ROI", synced_db, doc_type="基础概念")

        assert len(results) > 0
        for result in results:
            assert result.doc_type == "基础概念"


class TestRagAnswerE2E:
    """RAG 回答生成端到端测试"""

    def test_answer_generation_with_context(self):
        """测试基于上下文的回答生成"""
        generator = RagAnswerGenerator()

        query = "什么是 CTR？"
        context = [
            "CTR（Click-Through Rate，点击率）是广告点击量除以曝光量的百分比",
            "CTR 反映了广告对用户的吸引力程度",
        ]

        with patch.object(generator.llm, 'invoke') as mock_invoke:
            mock_invoke.return_value = Mock(
                content="CTR（点击率）是指广告点击量除以曝光量的百分比，它反映了广告对用户的吸引力程度。"
            )

            answer = generator.generate(query, context)
            assert answer is not None
            assert len(answer) > 0

    def test_empty_context_response(self):
        """测试空上下文场景"""
        generator = RagAnswerGenerator()

        query = "这个问题没有相关文档"
        context = []

        answer = generator.generate(query, context)
        assert "抱歉" in answer or "没有找到" in answer


class TestGraphRagIntegration:
    """LangGraph RAG 集成端到端测试"""

    @pytest.mark.asyncio
    async def test_knowledge_query_routing(self):
        """测试知识类查询路由"""
        graph = build_graph()

        initial_state = {
            "session_id": "test-rag-001",
            "user_id": "test-user",
            "user_input": "什么是 CTR",
            "conversation_history": [],
            "advertiser_ids": [],
            "query_type": None,
            "rag_context": [],
            "rag_answer": None,
        }

        # Mock intent router to return knowledge
        with patch('src.rag.agents.IntentRouter') as mock_router_cls:
            mock_router = Mock()
            mock_router.classify.return_value = "knowledge"
            mock_router_cls.return_value = mock_router

            # Mock RAG retrieval and answer
            with patch('src.rag.agents.RagAnswerGenerator') as mock_generator_cls:
                mock_generator = Mock()
                mock_generator.retrieve_context.return_value = ["CTR 是点击率"]
                mock_generator.generate.return_value = "CTR 是点击率"
                mock_generator_cls.return_value = mock_generator

                result = await graph.ainvoke(initial_state)

                assert result["query_type"] == "knowledge"
                assert result["rag_answer"] == "CTR 是点击率"
                assert result["final_report"] is not None
                assert result["final_report"]["title"] == "知识库查询结果"

    @pytest.mark.asyncio
    async def test_report_query_routing(self):
        """测试报表类查询路由"""
        graph = build_graph()

        initial_state = {
            "session_id": "test-rag-002",
            "user_id": "test-user",
            "user_input": "看上周的曝光点击",
            "conversation_history": [],
            "advertiser_ids": ["1"],
            "query_type": None,
            "rag_context": [],
            "rag_answer": None,
        }

        # Mock intent router to return report
        with patch('src.rag.agents.IntentRouter') as mock_router_cls:
            mock_router = Mock()
            mock_router.classify.return_value = "report"
            mock_router_cls.return_value = mock_router

            result = await graph.ainvoke(initial_state)

            # 应该路由到报表流程，query_type 为 report
            assert result["query_type"] == "report"
            # 应该继续执行到 NLU 节点
            assert "query_intent" in result or "error" in result


class TestFullWorkflow:
    """完整工作流测试"""

    def test_complete_rag_pipeline(self, test_docs_dir):
        """测试完整的 RAG 流程：同步 -> 检索 -> 回答"""
        # 1. 初始化数据库
        init_db()
        session = get_db_session()

        # 2. 同步文档
        syncer = DocumentSyncer(docs_dir=test_docs_dir)
        synced_count = syncer.sync_all(session)
        assert synced_count > 0

        # 3. 检索相关文档
        retriever = RagRetriever()
        results = retriever.search("CTR 怎么计算", session)
        assert len(results) > 0

        # 4. 生成回答
        generator = RagAnswerGenerator()
        context = [r.content for r in results]

        with patch.object(generator.llm, 'invoke') as mock_invoke:
            mock_invoke.return_value = Mock(
                content="CTR 的计算公式是：点击次数除以曝光次数再乘以100%。"
            )

            answer = generator.generate("CTR 怎么计算", context)
            assert "CTR" in answer or "点击" in answer

        session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
