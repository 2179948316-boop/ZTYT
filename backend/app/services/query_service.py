"""Query Service — orchestrates Agent execution with Redis caching and history logging."""

import hashlib
import json
import logging
import time

import redis

from app.agent.sql_agent import agent_runner, AgentResult
from app.core.config import settings
from app.core.database import AppSessionLocal
from app.models import Conversation, Message, QueryLog

logger = logging.getLogger(__name__)

# ── Redis connection (graceful degradation if unavailable) ──
_redis_client: redis.Redis | None = None

try:
    _redis_client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
        socket_connect_timeout=2,
        protocol=2,
    )
    _redis_client.ping()
    logger.info("Redis connected")
except Exception as e:
    logger.warning(f"Redis unavailable, caching disabled: {e}")
    _redis_client = None


CACHE_TTL = 3600  # 1 hour


def _cache_key(question: str) -> str:
    """Generate a SHA-256 cache key from the question."""
    normalized = question.strip().lower()
    return f"nl2sql:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"


def get_cached_answer(question: str) -> AgentResult | None:
    """Try to get a cached answer from Redis."""
    if not _redis_client:
        return None
    try:
        data = _redis_client.get(_cache_key(question))
        if data:
            cached = json.loads(data)
            return AgentResult(
                answer=cached["answer"],
                sql=cached.get("sql", ""),
                chart_config=cached.get("chart_config"),
            )
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
    return None


def set_cached_answer(question: str, result: AgentResult):
    """Cache an agent result in Redis."""
    if not _redis_client:
        return
    try:
        data = {
            "answer": result.answer,
            "sql": result.sql,
            "chart_config": result.chart_config,
        }
        _redis_client.setex(_cache_key(question), CACHE_TTL, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


def ask(question: str, conversation_id: int | None = None) -> dict:
    """
    Process a user question end-to-end:
    1. Check Redis cache
    2. Run Agent if not cached
    3. Cache result
    4. Log to query history
    5. Return structured response
    """
    start_time = time.time()

    # 1. Check cache
    cached = get_cached_answer(question)
    if cached:
        elapsed = (time.time() - start_time) * 1000
        _log_query(question, cached, elapsed, cached=True, conversation_id=conversation_id)
        return {
            "answer": cached.answer,
            "sql": cached.sql,
            "chart_config": cached.chart_config,
            "cached": True,
            "execution_time_ms": elapsed,
        }

    # 2. Run Agent
    result = agent_runner.run(question)
    elapsed = (time.time() - start_time) * 1000

    # 3. Cache on success
    if result.sql:
        set_cached_answer(question, result)

    # 4. Log history
    _log_query(question, result, elapsed, cached=False, conversation_id=conversation_id)

    return {
        "answer": result.answer,
        "sql": result.sql,
        "chart_config": result.chart_config,
        "cached": False,
        "execution_time_ms": round(elapsed, 1),
    }


def ask_stream(question: str, conversation_id: int | None = None):
    """
    Stream version of ask() — yields SSE events.
    Checks cache first, falls back to streaming agent.
    """
    import json as json_lib

    # Check cache
    cached = get_cached_answer(question)
    if cached:
        yield {"type": "answer", "data": cached.answer}
        if cached.sql:
            yield {"type": "sql", "data": cached.sql}
        if cached.chart_config:
            yield {"type": "chart", "data": cached.chart_config}
        yield {"type": "done", "data": {"sql": cached.sql, "cached": True}}
        return

    # Stream from agent
    sql = ""
    for event in agent_runner.run_stream(question):
        if event["type"] == "sql":
            sql = event["data"]
        yield event

    # Cache after stream completes
    # (We'd need to collect the full answer, simplified here)


def _log_query(
    question: str,
    result: AgentResult,
    elapsed_ms: float,
    cached: bool,
    conversation_id: int | None,
):
    """Save query to history in application database."""
    try:
        with AppSessionLocal() as db:
            log = QueryLog(
                conversation_id=conversation_id,
                question=question,
                sql_query=result.sql,
                result_summary=result.answer[:500] if result.answer else None,
                chart_type=result.chart_config.get("chart_type") if result.chart_config else None,
                cached=1 if cached else 0,
                execution_time_ms=round(elapsed_ms, 1),
            )
            db.add(log)
            db.commit()
    except Exception as e:
        logger.warning(f"Failed to log query: {e}")
