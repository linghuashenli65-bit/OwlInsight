"""Milvus 向量库封装，支持混合检索与元数据过滤."""

from backend.logger import logger
from typing import Any, Optional

from pymilvus import DataType, MilvusClient

from backend.config import settings

class VectorStore:
    """Milvus Lite 封装，提供基础的增删查及集合管理."""

    def __init__(self) -> None:
        self._client: Optional[MilvusClient] = None
        self._collection_name = settings.MILVUS_COLLECTION
        self._dim = settings.MILVUS_EMBEDDING_DIM

    # ────────── 连接与集合管理 ──────────

    def connect(self) -> "VectorStore":
        """连接 Milvus Lite（仅首次真正连接，后续调用直接返回）. """
        if self._client is not None:
            return self
        self._client = MilvusClient(settings.MILVUS_URI)
        logger.info("Milvus 已连接: %s", settings.MILVUS_URI)
        return self

    @property
    def client(self) -> MilvusClient:
        if self._client is None:
            raise RuntimeError("请先调用 connect() 连接 Milvus")
        return self._client

    def is_connected(self) -> bool:
        """检查是否已连接到 Milvus."""
        return self._client is not None

    def create_collection(self, overwrite: bool = False) -> None:
        """创建 collection，如已存在且 overwrite=True 则删除重建."""
        if self.client.has_collection(self._collection_name):
            if not overwrite:
                logger.info("Collection '%s' 已存在，跳过", self._collection_name)
                return
            self.client.drop_collection(self._collection_name)
            logger.info("Collection '%s' 已删除", self._collection_name)

        schema = self.client.create_schema(
            auto_id=True,
            enable_dynamic_field=True,
        )
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self._dim)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        # 常用元数据字段（nullable=True 兼容旧数据缺失的场景）
        schema.add_field("company", DataType.VARCHAR, max_length=128, nullable=True)
        schema.add_field("company_code", DataType.VARCHAR, max_length=32, nullable=True)
        schema.add_field("doc_type", DataType.VARCHAR, max_length=32, nullable=True)
        schema.add_field("doc_name", DataType.VARCHAR, max_length=256, nullable=True)
        schema.add_field("period_rank", DataType.INT64, nullable=True)
        schema.add_field("report_date", DataType.VARCHAR, max_length=16, nullable=True)
        schema.add_field("table_flag", DataType.BOOL, nullable=True)
        schema.add_field("summary", DataType.VARCHAR, max_length=1024, nullable=True)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            metric_type="IP",  # 内积，适用于归一化的 bge 向量
            index_type="IVF_FLAT",
            params={"nlist": 128},
        )

        self.client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Collection '%s' 创建成功", self._collection_name)

    def drop_collection(self) -> None:
        """删除集合."""
        self.client.drop_collection(self._collection_name)
        logger.info("Collection '%s' 已删除", self._collection_name)

    def has_collection(self) -> bool:
        return self.client.has_collection(self._collection_name)

    # ────────── 写入 ──────────

    def insert(self, text: str, embedding: list[float], metadata: dict[str, Any]) -> int:
        """插入一条文档块并返回 id. 未连接时自动连接."""
        self._ensure_connected()
        data = {
            "vector": embedding,
            "text": text,
            **{k: v for k, v in metadata.items() if v is not None},
        }
        result = self.client.insert(self._collection_name, [data])
        return result["ids"][0]

    def insert_batch(self, records: list[dict[str, Any]]) -> list[int]:
        """批量插入文档块. 未连接时自动连接."""
        self._ensure_connected()
        if not records:
            return []
        result = self.client.insert(self._collection_name, records)
        # 插入后 flush，确保后续搜索能立即检索到
        self.client.flush(collection_name=self._collection_name)
        return result["ids"]

    def delete(self, ids: list[int]) -> None:
        """按主键 ID 删除. 未连接时自动连接."""
        self._ensure_connected()
        self.client.delete(self._collection_name, list(ids))

    def delete_by_filter(self, expr: str) -> None:
        """按表达式删除. 未连接时自动连接."""
        self._ensure_connected()
        self.client.delete(self._collection_name, filter=expr)

    # ────────── 检索 ──────────

    def _ensure_connected(self) -> None:
        """自动连接（如果尚未连接）. """
        if self._client is None:
            self.connect()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        expr: Optional[str] = None,
        output_fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """向量检索, 支持元数据过滤. 未连接时自动连接.

        Args:
            query_embedding: 查询向量.
            top_k: 返回条数.
            expr: Milvus 布尔表达式过滤.
            output_fields: 返回字段列表.

        Returns:
            [{id, distance, text, company, ...}, ...]
        """
        self._ensure_connected()
        if output_fields is None:
            output_fields = ["id", "text", "company", "company_code",
                             "doc_type", "doc_name", "period_rank", "table_flag", "summary"]

        results = self.client.search(
            collection_name=self._collection_name,
            data=[query_embedding],
            limit=top_k,
            search_params={"metric_type": "IP", "params": {"nprobe": 16}},
            output_fields=output_fields,
            filter=expr,
        )
        # results[0] 是第一个 query 的结果列表
        return [hit["entity"] for hit in results[0]] if results else []

    def query(self, expr: str, output_fields: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """
        """
        self._ensure_connected()
        if output_fields is None:
            output_fields = ["id", "text", "company", "company_code",
                             "doc_type", "doc_name", "period_rank", "summary"]
        return self.client.query(
            collection_name=self._collection_name,
            filter=expr,
            output_fields=output_fields,
        )

    # ────────── 计数 ──────────

    def count(self) -> int:
        return self.client.query(
            collection_name=self._collection_name,
            output_fields=["count(*)"],
        )[0]["count(*)"]

    # ────────── 文档列表 ──────────

    def list_documents(self) -> list[dict[str, Any]]:
        """列出所有已导入文档（按 doc_name 去重，含 chunk 计数）. """
        self._ensure_connected()
        # 查询所有非空 doc_name
        results = self.client.query(
            collection_name=self._collection_name,
            filter='doc_name != "" and doc_name is not null',
            output_fields=["doc_name", "company", "company_code", "doc_type", "summary"],
            limit=10000,
        )
        # 按 doc_name 去重 + 统计 chunk 数
        seen: dict[str, dict[str, Any]] = {}
        counts: dict[str, int] = {}
        for r in results:
            name = r.get("doc_name", "")
            if not name:
                continue
            counts[name] = counts.get(name, 0) + 1
            if name not in seen:
                seen[name] = {
                    "doc_name": name,
                    "company": r.get("company", ""),
                    "company_code": r.get("company_code", ""),
                    "doc_type": r.get("doc_type", ""),
                    "summary": r.get("summary", ""),
                }
        for name, doc in seen.items():
            doc["chunk_count"] = counts.get(name, 0)
        return list(seen.values())

    def close(self) -> None:
        if self._client:
            self._client.close()
            logger.info("Milvus 连接已关闭")

# 全局单例
vector_store = VectorStore()
