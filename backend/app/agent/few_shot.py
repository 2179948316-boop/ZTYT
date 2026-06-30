"""Few-shot dynamic example retrieval for NL2SQL Agent.

Uses ChromaDB vector store with a lightweight jieba-based TF-IDF embedding
function — zero model downloads, fast for Chinese text, works offline.

How it works:
1. Curated question-SQL pairs are stored in ChromaDB
2. When a user asks a question, the most similar examples are retrieved
3. These examples are injected into the Agent's system prompt
4. The Agent uses them as reference to generate more accurate SQL

This is "context engineering" in practice — dynamically providing relevant
examples to improve LLM output quality without fine-tuning.
"""

import logging
import math
from collections import Counter

import jieba
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)

# Suppress jieba's verbose initialization logs
jieba.setLogLevel(logging.WARNING)


class JiebaTFIDFEmbedding(EmbeddingFunction):
    """
    Lightweight Chinese text embedding using jieba tokenization + TF-IDF.

    Advantages:
    - Zero model downloads (no sentence-transformers needed)
    - Handles Chinese text natively via jieba
    - Fast enough for real-time retrieval (<50ms per query)
    """

    # Common Chinese stop words to filter out
    STOP_WORDS = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
        "吗", "呢", "什么", "哪", "那", "怎么", "多少", "几", "个",
        "些", "为", "从", "以", "对", "与", "及", "等", "中", "被",
        "把", "让", "向", "跟", "按", "比", "最", "更", "还",
        "请问", "帮我", "查一下", "看看", "告诉", "一下",
    }

    def __init__(self):
        self._idf: dict[str, float] = {}
        self._vocabulary: list[str] = {}
        self._vocab_index: dict[str, int] = {}
        self._fitted = False

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize Chinese text with jieba, filtering stop words."""
        tokens = jieba.lcut(text)
        return [
            t.strip().lower()
            for t in tokens
            if t.strip() and len(t.strip()) > 0 and t.strip() not in self.STOP_WORDS
        ]

    def fit(self, documents: list[str]):
        """Compute IDF values from a corpus of documents."""
        n_docs = len(documents)
        if n_docs == 0:
            self._fitted = True
            return

        # Count document frequency for each token
        doc_freq: Counter = Counter()
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                doc_freq[token] += 1

        # Build vocabulary
        self._vocabulary = sorted(doc_freq.keys())
        self._vocab_index = {word: i for i, word in enumerate(self._vocabulary)}

        # Compute IDF: log(N / df)
        self._idf = {}
        for word, df in doc_freq.items():
            self._idf[word] = math.log((n_docs + 1) / (df + 1)) + 1

        self._fitted = True

    def __call__(self, input: Documents) -> Embeddings:
        """Embed documents into TF-IDF vectors."""
        if not self._fitted:
            self.fit(input)

        embeddings = []
        for doc in input:
            tokens = self._tokenize(doc)
            tf = Counter(tokens)
            total = max(len(tokens), 1)

            # Build sparse vector as dict {vocab_index: tfidf_value}
            vec = {}
            for token, count in tf.items():
                if token in self._vocab_index:
                    idx = self._vocab_index[token]
                    tf_val = count / total
                    idf_val = self._idf.get(token, 1.0)
                    vec[idx] = tf_val * idf_val

            # Convert to dense vector (chromadb expects lists of floats)
            vocab_size = len(self._vocabulary)
            dense = [0.0] * vocab_size
            for idx, val in vec.items():
                dense[idx] = val

            embeddings.append(dense)

        return embeddings

    def name(self) -> str:
        return "jieba_tfidf"


class FewShotStore:
    """
    Vector store for question-SQL pairs using ChromaDB.

    Provides:
    - add_examples(): batch add curated pairs
    - get_similar(): retrieve top-k similar examples for a question
    """

    def __init__(self):
        self._embedding = JiebaTFIDFEmbedding()
        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(
            name="nl2sql_examples",
            embedding_function=self._embedding,
            metadata={"description": "Curated NL-to-SQL examples for e-commerce analytics"},
        )
        logger.info(
            f"FewShotStore initialized: {self._collection.count()} examples loaded"
        )

    def add_examples(self, examples: list[dict]):
        """
        Add question-SQL pairs to the vector store.

        Args:
            examples: list of {"question": str, "sql": str, "description": str}
        """
        if not examples:
            return

        ids = []
        documents = []
        metadatas = []

        for i, ex in enumerate(examples):
            example_id = f"ex_{self._collection.count() + i}"
            ids.append(example_id)
            documents.append(ex["question"])
            metadatas.append({
                "sql": ex["sql"],
                "description": ex.get("description", ""),
            })

        self._collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Added {len(examples)} examples (total: {self._collection.count()})")

    def get_similar(self, question: str, k: int = 3) -> list[dict]:
        """
        Retrieve the top-k most similar examples for a given question.

        Returns:
            List of {"question": str, "sql": str, "description": str, "distance": float}
        """
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[question],
            n_results=min(k, self._collection.count()),
        )

        examples = []
        for i in range(len(results["documents"][0])):
            examples.append({
                "question": results["documents"][0][i],
                "sql": results["metadatas"][0][i]["sql"],
                "description": results["metadatas"][0][i]["description"],
                "distance": results["distances"][0][i],
            })

        return examples

    def count(self) -> int:
        return self._collection.count()


# Singleton instance
few_shot_store = FewShotStore()
