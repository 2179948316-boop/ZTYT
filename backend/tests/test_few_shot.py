"""Unit tests for Few-shot Dynamic Example Retrieval.

Covers:
- JiebaTFIDFEmbedding: tokenization, stop word filtering, IDF computation, vector output
- FewShotStore: add examples, get_similar retrieval, empty store handling
- Semantic similarity quality (related queries should match)
"""

import uuid
import pytest

from app.agent.few_shot import JiebaTFIDFEmbedding, FewShotStore


# ── JiebaTFIDFEmbedding Tests ──

class TestJiebaTFIDFEmbedding:
    """Test the custom jieba-based TF-IDF embedding function."""

    @pytest.fixture
    def embed(self):
        return JiebaTFIDFEmbedding()

    def test_tokenize_basic(self, embed):
        tokens = embed._tokenize("销量最高的产品有哪些")
        # Stop words like "的" and "哪些" should be filtered
        assert "的" not in tokens
        # Meaningful tokens should remain
        assert any(t in tokens for t in ["销量", "最高", "产品"])

    def test_tokenize_stop_words_filtered(self, embed):
        tokens = embed._tokenize("请问帮我查一下看看告诉我一下")
        # All of these are stop words
        for sw in ["请问", "帮我", "查一下", "看看", "告诉", "一下"]:
            assert sw not in tokens

    def test_tokenize_empty_string(self, embed):
        tokens = embed._tokenize("")
        assert tokens == []

    def test_tokenize_only_stop_words(self, embed):
        tokens = embed._tokenize("的了在是我")
        assert tokens == []

    def test_fit_builds_vocabulary(self, embed):
        docs = ["销量最高的产品", "每个城市的客户数量", "订单金额趋势"]
        embed.fit(docs)
        assert embed._fitted
        assert len(embed._vocabulary) > 0
        assert len(embed._idf) > 0

    def test_fit_empty_corpus(self, embed):
        embed.fit([])
        assert embed._fitted
        assert len(embed._vocabulary) == 0

    def test_call_returns_dense_vectors(self, embed):
        docs = ["销量最高的产品", "每个城市的客户数量"]
        result = embed(docs)
        assert len(result) == 2
        # Each vector should have the same length (vocabulary size)
        assert len(result[0]) == len(result[1])
        assert len(result[0]) > 0

    def test_call_auto_fits_if_not_fitted(self, embed):
        assert not embed._fitted
        result = embed(["测试文本", "另一个文本"])
        assert embed._fitted
        assert len(result) == 2

    def test_vectors_have_nonzero_values(self, embed):
        docs = ["产品销量排名", "客户城市分布"]
        result = embed(docs)
        # At least some dimensions should be non-zero
        assert any(v > 0 for v in result[0])
        assert any(v > 0 for v in result[1])

    def test_name(self, embed):
        assert embed.name() == "jieba_tfidf"

    def test_idf_rare_words_higher(self, embed):
        """Rare words should have higher IDF values."""
        docs = [
            "产品销量",
            "产品销量",
            "产品销量",
            "库存预警",  # "库存" and "预警" appear only once
        ]
        embed.fit(docs)
        # "预警" appears in 1/4 docs → higher IDF
        # "产品" appears in 3/4 docs → lower IDF
        if "预警" in embed._idf and "产品" in embed._idf:
            assert embed._idf["预警"] > embed._idf["产品"]


# ── FewShotStore Tests ──

class TestFewShotStore:
    """Test the vector store for question-SQL pairs."""

    @pytest.fixture
    def store(self):
        """Create a fresh store with a unique collection name for each test."""
        import chromadb
        s = FewShotStore.__new__(FewShotStore)
        s._embedding = JiebaTFIDFEmbedding()
        s._client = chromadb.Client()
        s._collection = s._client.get_or_create_collection(
            name=f"test_{uuid.uuid4().hex[:8]}",
            embedding_function=s._embedding,
        )
        return s

    def test_initial_count_zero(self, store):
        assert store.count() == 0

    def test_add_examples(self, store):
        examples = [
            {"question": "销量最高的产品", "sql": "SELECT * FROM products ORDER BY sales DESC", "description": "销量排行"},
            {"question": "各城市客户数", "sql": "SELECT city, COUNT(*) FROM customers GROUP BY city", "description": "城市分布"},
        ]
        store.add_examples(examples)
        assert store.count() == 2

    def test_add_empty_list(self, store):
        store.add_examples([])
        assert store.count() == 0

    def test_get_similar_returns_results(self, store):
        examples = [
            {"question": "销量最高的产品有哪些", "sql": "SELECT name FROM products ORDER BY sales DESC LIMIT 5", "description": "销量排行"},
            {"question": "每个城市的客户数量", "sql": "SELECT city, COUNT(*) FROM customers GROUP BY city", "description": "城市分布"},
            {"question": "最近一个月的订单趋势", "sql": "SELECT DATE(created_at), COUNT(*) FROM orders GROUP BY DATE(created_at)", "description": "趋势分析"},
        ]
        store.add_examples(examples)

        results = store.get_similar("卖得最好的产品")
        assert len(results) > 0
        # Should have the expected fields
        assert "question" in results[0]
        assert "sql" in results[0]
        assert "description" in results[0]
        assert "distance" in results[0]

    def test_get_similar_empty_store(self, store):
        results = store.get_similar("任何问题")
        assert results == []

    def test_get_similar_respects_k(self, store):
        examples = [
            {"question": f"问题{i}", "sql": f"SELECT {i}", "description": f"描述{i}"}
            for i in range(10)
        ]
        store.add_examples(examples)

        results = store.get_similar("测试", k=3)
        assert len(results) == 3

    def test_get_similar_k_larger_than_count(self, store):
        examples = [
            {"question": "唯一问题", "sql": "SELECT 1", "description": "唯一"},
        ]
        store.add_examples(examples)

        results = store.get_similar("测试", k=10)
        assert len(results) == 1

    def test_semantic_similarity_quality(self, store):
        """Related queries should rank higher than unrelated ones."""
        examples = [
            {"question": "销量最高的5个产品", "sql": "SELECT name, SUM(quantity) FROM order_items GROUP BY product_id ORDER BY SUM(quantity) DESC LIMIT 5", "description": "销量排行"},
            {"question": "各支付方式订单占比", "sql": "SELECT payment_method, COUNT(*) FROM orders GROUP BY payment_method", "description": "支付分布"},
            {"question": "最近30天每日订单金额", "sql": "SELECT DATE(created_at), SUM(total_amount) FROM orders GROUP BY DATE(created_at)", "description": "趋势分析"},
            {"question": "不同会员等级平均消费", "sql": "SELECT member_level, AVG(total_amount) FROM customers JOIN orders GROUP BY member_level", "description": "会员分析"},
        ]
        store.add_examples(examples)

        # "卖得最好的产品" should match "销量最高的5个产品" best
        results = store.get_similar("卖得最好的产品", k=2)
        # The top result should be about sales ranking
        top_question = results[0]["question"]
        assert "销量" in top_question or "产品" in top_question

    def test_add_examples_incremental(self, store):
        batch1 = [{"question": "问题A", "sql": "SELECT A", "description": "A"}]
        batch2 = [{"question": "问题B", "sql": "SELECT B", "description": "B"}]
        store.add_examples(batch1)
        assert store.count() == 1
        store.add_examples(batch2)
        assert store.count() == 2
