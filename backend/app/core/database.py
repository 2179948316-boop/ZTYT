"""Database engine and session factories.

Two separate databases:
- biz_engine: the e-commerce demo data (read-only target for NL2SQL)
- app_engine: application data (conversations, query history)
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# ── Business Database (e-commerce data) ──
biz_engine = create_engine(
    settings.biz_database_url,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)
BizSessionLocal = sessionmaker(bind=biz_engine, autocommit=False, autoflush=False)


# ── Application Database (conversations, history) ──
app_engine = create_engine(
    settings.app_database_url,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)
AppSessionLocal = sessionmaker(bind=app_engine, autocommit=False, autoflush=False)


def get_biz_db() -> Session:
    """Dependency: get business database session."""
    db = BizSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_app_db() -> Session:
    """Dependency: get application database session."""
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_app_db():
    """Create application tables if they don't exist."""
    from app.models import Base
    Base.metadata.create_all(bind=app_engine)


def check_db_connection() -> dict:
    """Check connectivity to both databases."""
    result = {"biz_db": False, "app_db": False}
    try:
        with biz_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["biz_db"] = True
    except Exception as e:
        result["biz_db_error"] = str(e)

    try:
        with app_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["app_db"] = True
    except Exception as e:
        result["app_db_error"] = str(e)

    return result
