from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.logging_config import get_logger

ROOT = Path(__file__).resolve().parents[2]
logger = get_logger(__name__)


def run_migrations() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    logger.info("Running alembic upgrade head")
    command.upgrade(cfg, "head")
    logger.info("Alembic upgrade head finished")

