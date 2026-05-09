"""SQLAlchemy ORM 模型 — 设置 / 关注公司 / 研究笔记."""

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AppSetting(Base):
    """应用设置键值对."""
    __tablename__ = "app_settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)


class WatchedCompany(Base):
    """关注公司."""
    __tablename__ = "watched_companies"

    company_code = Column(String(32), primary_key=True)
    company_name = Column(String(128), nullable=False)
    analysis_count = Column(Integer, default=1, nullable=False)
    last_analyzed = Column(DateTime, default=func.now(), nullable=True)


class ResearchNote(Base):
    """研究笔记."""
    __tablename__ = "research_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_code = Column(
        String(32),
        ForeignKey("watched_companies.company_code", ondelete="CASCADE"),
        nullable=False,
    )
    company_name = Column(String(128), nullable=False)
    filename = Column(String(256))
    content = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=True)
