"""Smart Data Analyst — FastAPI Application Entry Point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.api.routes import router
from app.core.database import init_app_db
from app.scheduler.tasks import ALL_TASKS, run_all_tasks

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ──
app = FastAPI(
    title="智能数据分析助手",
    description="NL2SQL + Agent：用自然语言提问，AI 自动生成 SQL、执行查询、返回分析结论和可视化图表",
    version="2.0.0",
)

# CORS — allow Vue dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router)

# ── APScheduler ──
scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup():
    """Initialize DB, seed few-shot examples, run pre-computation, start scheduler."""
    logger.info("Initializing application database...")
    init_app_db()

    # Load few-shot examples
    logger.info("Loading few-shot examples...")
    try:
        from app.agent.few_shot import few_shot_store
        if few_shot_store.count() == 0:
            from data.seed_examples import SEED_EXAMPLES
            few_shot_store.add_examples(SEED_EXAMPLES)
            logger.info(f"Loaded {len(SEED_EXAMPLES)} few-shot examples")
        else:
            logger.info(f"Few-shot store: {few_shot_store.count()} examples already loaded")
    except Exception as e:
        logger.warning(f"Failed to load few-shot examples: {e}")

    # Run initial pre-computation
    logger.info("Running initial dashboard pre-computation...")
    try:
        run_all_tasks()
    except Exception as e:
        logger.warning(f"Initial pre-computation failed: {e}")

    # Register scheduled tasks
    for task in ALL_TASKS:
        scheduler.add_job(
            task["func"],
            "interval",
            minutes=task["interval_minutes"],
            id=task["id"],
            name=task["name"],
        )
    scheduler.start()
    logger.info(f"APScheduler started with {len(ALL_TASKS)} tasks")

    logger.info("Smart Data Analyst v2.0 started.")


@app.on_event("shutdown")
def on_shutdown():
    """Shut down the scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down.")


if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
