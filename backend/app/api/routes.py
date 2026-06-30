"""API routes for the smart data analyst."""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_app_db, AppSessionLocal
from app.models import Conversation, Message, QueryLog, DataSource
from app.services import query_service
from app.services.preview_service import preview_service
from app.scheduler.tasks import get_all_dashboard_data, get_dashboard_data

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request/Response Models ──

class AskRequest(BaseModel):
    question: str
    conversation_id: int | None = None


class AskResponse(BaseModel):
    answer: str
    sql: str = ""
    chart_config: dict | None = None
    cached: bool = False
    execution_time_ms: float = 0


class ConversationCreate(BaseModel):
    title: str = "新对话"


class ExecuteSqlRequest(BaseModel):
    sql: str


class DataSourceCreate(BaseModel):
    name: str
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str
    database_name: str


class SqlPreviewRequest(BaseModel):
    sql: str


class SqlConfirmRequest(BaseModel):
    sql: str


# ── Health Check ──

@router.get("/health")
def health_check():
    from app.core.database import check_db_connection
    db_status = check_db_connection()
    return {"status": "ok", "databases": db_status}


@router.post("/api/execute-sql")
def execute_sql(req: ExecuteSqlRequest):
    """Safely execute a SQL query and return structured data for chart rendering."""
    from sqlalchemy import text as sa_text
    from app.core.database import BizSessionLocal
    from app.core.sql_validator import validator

    try:
        sql = validator.validate(req.sql)
        with BizSessionLocal() as session:
            result = session.execute(sa_text(sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]

        # Convert Decimal and datetime to JSON-serializable types
        for row in rows:
            for i, val in enumerate(row):
                if hasattr(val, '__float__'):
                    row[i] = float(val)
                elif hasattr(val, 'isoformat'):
                    row[i] = val.isoformat()

        return {"columns": columns, "rows": rows, "count": len(rows)}
    except Exception as e:
        return {"error": str(e), "columns": [], "rows": [], "count": 0}


# ── Chat / Query Endpoints ──

@router.post("/api/ask", response_model=AskResponse)
def ask_question(req: AskRequest, db: Session = Depends(get_app_db)):
    """Ask a natural language question — synchronous response."""
    # Create or get conversation
    conv_id = req.conversation_id
    if not conv_id:
        conv = Conversation(title=req.question[:50])
        db.add(conv)
        db.flush()
        conv_id = conv.id

    # Save user message
    user_msg = Message(conversation_id=conv_id, role="user", content=req.question)
    db.add(user_msg)
    db.commit()

    # Run query
    result = query_service.ask(req.question, conversation_id=conv_id)

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=result["answer"],
        metadata_json={
            "sql": result["sql"],
            "chart_config": result.get("chart_config"),
            "cached": result["cached"],
            "execution_time_ms": result["execution_time_ms"],
        },
    )
    db.add(assistant_msg)

    # Update conversation title if it's the first message
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if conv and conv.title == "新对话":
        conv.title = req.question[:50]

    db.commit()

    return AskResponse(
        answer=result["answer"],
        sql=result["sql"],
        chart_config=result.get("chart_config"),
        cached=result["cached"],
        execution_time_ms=result["execution_time_ms"],
    )


@router.post("/api/ask/stream")
def ask_question_stream(req: AskRequest):
    """Ask a question with SSE streaming for real-time feedback."""
    conv_id = req.conversation_id

    # Create conversation if needed
    if not conv_id:
        with AppSessionLocal() as db:
            conv = Conversation(title=req.question[:50])
            db.add(conv)
            db.commit()
            conv_id = conv.id

    def event_stream():
        full_answer = ""
        full_sql = ""

        for event in query_service.ask_stream(req.question, conversation_id=conv_id):
            if event["type"] == "answer":
                full_answer = event["data"]
            elif event["type"] == "sql":
                full_sql = event["data"]

            # Send as SSE
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # Save messages to DB after stream completes
        try:
            with AppSessionLocal() as db:
                user_msg = Message(conversation_id=conv_id, role="user", content=req.question)
                db.add(user_msg)
                assistant_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_answer,
                    metadata_json={"sql": full_sql},
                )
                db.add(assistant_msg)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to save stream messages: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Conversations ──

@router.get("/api/conversations")
def list_conversations(db: Session = Depends(get_app_db)):
    """List all conversations."""
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "message_count": len(c.messages),
        }
        for c in convs
    ]


@router.post("/api/conversations")
def create_conversation(req: ConversationCreate, db: Session = Depends(get_app_db)):
    """Create a new conversation."""
    conv = Conversation(title=req.title)
    db.add(conv)
    db.commit()
    return {"id": conv.id, "title": conv.title}


@router.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: int, db: Session = Depends(get_app_db)):
    """Get conversation with all messages."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        return {"error": "对话不存在"}

    messages = []
    for msg in sorted(conv.messages, key=lambda m: m.created_at):
        messages.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "metadata": msg.metadata_json,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return {
        "id": conv.id,
        "title": conv.title,
        "messages": messages,
    }


@router.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_app_db)):
    """Delete a conversation and its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if conv:
        db.delete(conv)
        db.commit()
    return {"ok": True}


# ── Query History ──

@router.get("/api/history")
def get_query_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_app_db),
):
    """Get query history with pagination."""
    total = db.query(QueryLog).count()
    logs = (
        db.query(QueryLog)
        .order_by(QueryLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "question": log.question,
                "sql_query": log.sql_query,
                "result_summary": log.result_summary,
                "chart_type": log.chart_type,
                "row_count": log.row_count,
                "execution_time_ms": log.execution_time_ms,
                "cached": bool(log.cached),
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# ── Data Sources ──

@router.get("/api/datasources")
def list_datasources(db: Session = Depends(get_app_db)):
    """List all configured data sources."""
    sources = db.query(DataSource).order_by(DataSource.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "host": s.host,
            "port": s.port,
            "database_name": s.database_name,
            "is_active": bool(s.is_active),
            "table_count": s.table_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sources
    ]


@router.post("/api/datasources")
def create_datasource(req: DataSourceCreate, db: Session = Depends(get_app_db)):
    """Add a new data source configuration."""
    ds = DataSource(
        name=req.name,
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        database_name=req.database_name,
    )
    db.add(ds)
    db.commit()

    # Test connection
    from sqlalchemy import create_engine, text
    url = f"mysql+pymysql://{req.username}:{req.password}@{req.host}:{req.port}/{req.database_name}"
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = :db"
            ), {"db": req.database_name})
            table_count = result.scalar()
        ds.table_count = table_count
        db.commit()
        return {"id": ds.id, "name": ds.name, "table_count": table_count, "status": "connected"}
    except Exception as e:
        return {"id": ds.id, "name": ds.name, "status": "error", "error": str(e)}


# ── Dashboard (Pre-computed Analytics) ──

@router.get("/api/dashboard/stats")
def dashboard_stats():
    """Return all pre-computed dashboard analytics from Redis."""
    data = get_all_dashboard_data()
    # Check if any data exists
    has_data = any(v is not None for v in data.values())
    return {
        "success": True,
        "has_data": has_data,
        "modules": data,
    }


@router.get("/api/dashboard/stats/{key}")
def dashboard_stat_module(key: str):
    """Return a single pre-computed dashboard module."""
    data = get_dashboard_data(key)
    if data is None:
        return {"success": False, "error": f"模块 '{key}' 暂无数据"}
    return {"success": True, "data": data}


# ── SQL Write Preview & Confirm ──

@router.post("/api/sql/preview")
def sql_preview(req: SqlPreviewRequest):
    """
    Detect if a SQL is a write operation and return a preview of affected rows.
    If it's a SELECT, returns {"is_write": false}.
    If it's UPDATE/DELETE/INSERT, returns preview data for user confirmation.
    """
    op_type = preview_service.detect_write(req.sql)
    if not op_type:
        return {
            "is_write": False,
            "message": "只读查询，无需确认",
        }

    try:
        result = preview_service.generate_preview(req.sql)
        return {
            "is_write": True,
            "operation_type": result.operation_type,
            "preview_sql": result.preview_sql,
            "affected_rows": result.affected_rows,
            "sample_data": result.sample_data,
            "columns": result.columns,
            "original_sql": result.original_sql,
        }
    except ValueError as e:
        return {"is_write": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Preview generation failed: {e}")
        return {
            "is_write": True,
            "operation_type": op_type,
            "error": f"预览生成失败: {str(e)}",
            "original_sql": req.sql,
        }


@router.post("/api/sql/confirm")
def sql_confirm(req: SqlConfirmRequest):
    """
    Execute a confirmed write operation.
    Only called after the user has reviewed the preview and confirmed.
    """
    op_type = preview_service.detect_write(req.sql)
    if not op_type:
        return {"success": False, "error": "该 SQL 不是写操作，请使用 /api/execute-sql"}

    result = preview_service.execute_write(req.sql)
    return result


# ── SQL EXPLAIN (Execution Plan Visualization) ──

@router.post("/api/sql/explain")
def sql_explain(req: ExecuteSqlRequest):
    """
    Run EXPLAIN on a SQL query and return the execution plan in structured format.
    Useful for understanding index usage, join strategies, and query optimization.
    """
    from sqlalchemy import text as sa_text
    from app.core.database import BizSessionLocal
    from app.core.sql_validator import validator

    try:
        # Validate SQL first (only SELECT allowed)
        sql = validator.validate(req.sql)
        explain_sql = f"EXPLAIN {sql}"

        with BizSessionLocal() as session:
            result = session.execute(sa_text(explain_sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]

        # Convert non-serializable types
        for row in rows:
            for i, val in enumerate(row):
                if val is None:
                    row[i] = None
                elif hasattr(val, "__float__"):
                    row[i] = float(val)
                elif hasattr(val, "isoformat"):
                    row[i] = val.isoformat()
                else:
                    row[i] = str(val)

        # Parse into structured format for frontend visualization
        steps = []
        for row in rows:
            step = dict(zip(columns, row))
            # Classify access type for visual indicators
            access_type = (step.get("type") or "").upper()
            if access_type in ("ALL",):
                step["_level"] = "danger"     # Full table scan
            elif access_type in ("INDEX", "RANGE"):
                step["_level"] = "warning"    # Index scan / range
            elif access_type in ("REF", "EQ_REF", "CONST", "SYSTEM"):
                step["_level"] = "success"    # Efficient index lookup
            else:
                step["_level"] = "info"
            steps.append(step)

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "steps": steps,
            "step_count": len(steps),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Query Performance Comparison ──

@router.get("/api/performance/stats")
def performance_stats(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_app_db),
):
    """
    Return query performance metrics from history for comparison panel.
    Shows Agent execution time vs cache hit time for repeated queries.
    """
    logs = (
        db.query(QueryLog)
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    agent_times = []
    cache_times = []

    for log in logs:
        item = {
            "id": log.id,
            "question": log.question[:60],
            "execution_time_ms": log.execution_time_ms,
            "cached": bool(log.cached),
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "chart_type": log.chart_type,
        }
        items.append(item)

        if log.execution_time_ms is not None:
            if log.cached:
                cache_times.append(log.execution_time_ms)
            else:
                agent_times.append(log.execution_time_ms)

    # Summary statistics
    summary = {
        "total_queries": len(items),
        "agent_queries": len(agent_times),
        "cache_queries": len(cache_times),
        "avg_agent_ms": round(sum(agent_times) / max(len(agent_times), 1), 1),
        "avg_cache_ms": round(sum(cache_times) / max(len(cache_times), 1), 1),
        "max_agent_ms": round(max(agent_times), 1) if agent_times else 0,
        "max_cache_ms": round(max(cache_times), 1) if cache_times else 0,
        "speedup_ratio": round(
            (sum(agent_times) / max(len(agent_times), 1))
            / max(sum(cache_times) / max(len(cache_times), 1), 0.01),
            1
        ) if cache_times and agent_times else None,
    }

    return {
        "success": True,
        "summary": summary,
        "items": items,
    }
