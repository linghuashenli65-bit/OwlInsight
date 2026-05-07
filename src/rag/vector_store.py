"""Milvus 向量库封装，支持混合检索与元数据过滤."""

import logging
from typing import Any, Optional

from pymilvus import DataType, MilvusClient

from src.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Milvus Lite 封装，提供基础的增删查及集合管理."""

    def __init__(self) -> None:
        self._client: Optional[MilvusClient] = None
        self._collection_name = settings.MILVUS_COLLECTION
        self._dim = settings.MILVUS_EMBEDDING_DIM

    # ────────── 连接与集合管理 ──────────

    def connect(self) -> "VectorStore":
        """连接 Milvus Lite（单文件嵌入式数据库）. """
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
        """插入一条文档块并返回 id."""
        data = {
            "vector": embedding,
            "text": text,
            **{k: v for k, v in metadata.items() if v is not None},
        }
        result = self.client.insert(self._collection_name, [data])
        return result["ids"][0]

    def insert_batch(self, records: list[dict[str, Any]]) -> list[int]:
        """批量插入文档块."""
        if not records:
            return []
        result = self.client.insert(self._collection_name, records)
        # 插入后 flush，确保后续搜索能立即检索到
        self.client.flush(collection_name=self._collection_name)
        return result["ids"]

    def delete(self, ids: list[int]) -> None:
        """按主键 ID 删除."""
        self.client.delete(self._collection_name, list(ids))

    def delete_by_filter(self, expr: str) -> None:
        """按表达式删除，例如 'company_code == \"600519\"'."""
        self.client.delete(self._collection_name, filter=expr)

    # ────────── 检索 ──────────

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        expr: Optional[str] = None,
        output_fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """向量检索，支持元数据过滤.

        Args:
            query_embedding: 查询向量。
            top_k: 返回条数。
            expr: Milvus 布尔表达式过滤，如 'period_rank >= -3'。
            output_fields: 返回字段列表，默认返回所有。

        Returns:
            [{id, distance, text, company, ...}, ...]
        """
        if output_fields is None:
            output_fields = ["id", "text", "company", "company_code",
                             "doc_type", "doc_name", "period_rank", "table_flag"]

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
        """通过表达式查询（不依赖向量），用于元数据过滤场景.

        例如：'period_rank >= -3 and company_code == "600519"'
        并按 period_rank 降序排列返回最近 N 期.
        """
        if output_fields is None:
            output_fields = ["id", "text", "company", "company_code",
                             "doc_type", "doc_name", "period_rank"]
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

    def close(self) -> None:
        if self._client:
            self._client.close()
            logger.info("Milvus 连接已关闭")


# 全局单例
vector_store = VectorStore()
