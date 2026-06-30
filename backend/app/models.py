"""ORM models for the application database (smart_analyst).

These tables store conversation history, query logs, and data source configs.
The e-commerce demo tables are created separately by the Faker data generator.
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, default="新对话")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    query_logs = relationship("QueryLog", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)  # sql, chart_config, etc.
    created_at = Column(DateTime, default=datetime.now)

    conversation = relationship("Conversation", back_populates="messages")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    question = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)
    chart_type = Column(String(50), nullable=True)
    row_count = Column(Integer, nullable=True)
    execution_time_ms = Column(Float, nullable=True)
    cached = Column(Integer, default=0)  # 0=no, 1=yes
    created_at = Column(DateTime, default=datetime.now)

    conversation = relationship("Conversation", back_populates="query_logs")


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False, default="localhost")
    port = Column(Integer, nullable=False, default=3306)
    username = Column(String(100), nullable=False, default="root")
    password = Column(String(255), nullable=False)
    database_name = Column(String(100), nullable=False)
    is_active = Column(Integer, default=1)
    table_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
