"""
向量嵌入服务
支持文本嵌入、向量存储、相似度搜索
用于 RAG 检索和语义搜索
"""

import hashlib
import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import sqlite3


@dataclass
class VectorDocument:
    """向量文档"""
    doc_id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SearchResult:
    """搜索结果"""
    doc_id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class EmbeddingService:
    """
    文本嵌入服务

    支持：
    - OpenAI embeddings
    - 本地模型（sentence-transformers）
    - 简化版哈希向量（测试用）
    """

    def __init__(self, provider: str = "mock", model: str = "text-embedding-3-small"):
        self.provider = provider
        self.model = model
        self._client = None

        if provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except ImportError:
                print("OpenAI SDK 未安装，使用 mock 模式")
                self.provider = "mock"

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文本"""
        if self.provider == "openai" and self._client:
            response = self._client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        elif self.provider == "mock":
            return [self._mock_embedding(text) for text in texts]
        else:
            raise ValueError(f"不支持的 provider: {self.provider}")

    def embed_text(self, text: str) -> List[float]:
        """嵌入单个文本"""
        return self.embed_texts([text])[0]

    def _mock_embedding(self, text: str) -> List[float]:
        """
        生成伪向量（用于测试）
        基于文本哈希生成确定性向量
        """
        hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()
        np.random.seed(int.from_bytes(hash_bytes[:4], 'big'))
        vector = np.random.randn(1536).tolist()
        norm = np.linalg.norm(vector)
        return [x / norm for x in vector]


class VectorStore:
    """
    向量存储（SQLite 实现）

    支持：
    - 向量插入
    - 相似度搜索（余弦相似度）
    - 批量检索
    - 元数据过滤
    """

    def __init__(self, db_path: str = "data/vector_store.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化向量存储表"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                doc_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at
            ON vectors(created_at DESC)
        """)
        conn.commit()
        conn.close()

    def insert(self, doc: VectorDocument) -> str:
        """插入向量文档"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO vectors
            (doc_id, text, embedding, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            doc.doc_id,
            doc.text,
            json.dumps(doc.embedding),
            json.dumps(doc.metadata, ensure_ascii=False),
            doc.created_at.isoformat()
        ))
        conn.commit()
        conn.close()
        return doc.doc_id

    def insert_batch(self, docs: List[VectorDocument]) -> List[str]:
        """批量插入"""
        conn = sqlite3.connect(self.db_path)
        conn.executemany("""
            INSERT OR REPLACE INTO vectors
            (doc_id, text, embedding, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, [
            (doc.doc_id, doc.text, json.dumps(doc.embedding),
             json.dumps(doc.metadata, ensure_ascii=False), doc.created_at.isoformat())
            for doc in docs
        ])
        conn.commit()
        conn.close()
        return [doc.doc_id for doc in docs]

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        相似度搜索（余弦相似度）

        注意：这是朴素实现，大规模数据应使用 FAISS/Milvus
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT doc_id, text, embedding, metadata FROM vectors")

        results = []
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        for row in cursor:
            doc_id, text, embedding_json, metadata_json = row
            embedding = np.array(json.loads(embedding_json))
            doc_norm = np.linalg.norm(embedding)

            if query_norm == 0 or doc_norm == 0:
                continue

            similarity = float(np.dot(query_vec, embedding) / (query_norm * doc_norm))

            metadata = json.loads(metadata_json) if metadata_json else {}

            if metadata_filter:
                if not self._match_metadata(metadata, metadata_filter):
                    continue

            results.append(SearchResult(
                doc_id=doc_id,
                text=text,
                score=similarity,
                metadata=metadata
            ))

        conn.close()

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _match_metadata(self, doc_metadata: Dict, filter_metadata: Dict) -> bool:
        """检查元数据是否匹配"""
        for key, value in filter_metadata.items():
            if key not in doc_metadata or doc_metadata[key] != value:
                return False
        return True

    def delete(self, doc_id: str) -> bool:
        """删除向量文档"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("DELETE FROM vectors WHERE doc_id = ?", (doc_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def count(self) -> int:
        """统计向量数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM vectors")
        count = cursor.fetchone()[0]
        conn.close()
        return count


class RAGRetriever:
    """
    RAG 检索器

    流程：
    1. 查询 → 嵌入
    2. 向量相似度搜索
    3. 返回相关文档
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """检索相关文档"""
        query_embedding = self.embedding_service.embed_text(query)
        return self.vector_store.search(query_embedding, top_k, metadata_filter)

    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict]] = None) -> List[str]:
        """添加文档到向量库"""
        if metadatas is None:
            metadatas = [{}] * len(texts)

        embeddings = self.embedding_service.embed_texts(texts)

        docs = [
            VectorDocument(
                doc_id=hashlib.sha256(text.encode()).hexdigest(),
                text=text,
                embedding=embedding,
                metadata=metadata
            )
            for text, embedding, metadata in zip(texts, embeddings, metadatas)
        ]

        return self.vector_store.insert_batch(docs)
