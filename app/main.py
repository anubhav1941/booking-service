import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import inventory_client
from app.config import settings
from app.database import Base, db_is_healthy, engine, wait_for_db
from app.routers import bookings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [" + settings.service_name + "] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    Base.metadata.create_all(engine)
    log.info("%s started on %s, inventory at %s", settings.service_name, settings.instance_name,
             settings.inventory_url)
    yield


app = FastAPI(
    title="RailBook - Booking Service",
    description="Owns bookings and passengers (PNR). Orchestrates the booking saga: holds seats in "
                "inventory-service over REST, takes payment (mocked), then confirms or compensates.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_instance_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Served-By"] = settings.instance_name
    return response


@app.get("/health", tags=["Ops"], summary="Liveness probe")
def health():
    return {"status": "UP", "service": settings.service_name, "instance": settings.instance_name}


@app.get("/ready", tags=["Ops"], summary="Readiness probe (checks DB and inventory-service)")
def ready():
    db_ok = db_is_healthy()
    inv_ok = inventory_client.is_reachable()
    body = {"database": "UP" if db_ok else "DOWN", "inventory_service": "UP" if inv_ok else "DOWN"}
    # Only the DB decides readiness. If inventory is down we still serve PNR lookups.
    if db_ok:
        return {"status": "READY", **body}
    return JSONResponse(status_code=503, content={"status": "NOT_READY", **body})


app.include_router(bookings.router)
