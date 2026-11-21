from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.market import router as market_router
from app.api.reconcile import router as reconcile_router
from app.api.trades import router as trades_router
from app.config import get_settings
from app.db.migrate import run_migrations
from app.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging(get_settings().log_level)
    logger.info("Starting application; running migrations")
    run_migrations()
    logger.info("Migrations complete; ready to serve")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Trade Recorder & PnL Service",
    version="0.1.0",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(trades_router)
app.include_router(market_router)
app.include_router(reconcile_router)
