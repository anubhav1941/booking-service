import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

log = logging.getLogger(__name__)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    """In Kubernetes the DB pod may start after the app pod, so retry instead of crashing."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("Database is reachable")
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("DB not ready (attempt %s/%s): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError("Database not reachable, giving up")


def db_is_healthy() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
