
import importlib
import logging
import pkgutil
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import find_origin_problems, get_settings
from app.db import create_pool
import app.routes as routes_package


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the database connection pool on startup and close it on shutdown."""
    pool = create_pool()
    try:
        pool.open(wait=True)
        app.state.db_pool = pool
        logger.info("Database connection pool opened")
        yield
    finally:
        pool.close()
        logger.info("Database connection pool closed")


settings = get_settings()
for _problem in find_origin_problems(settings.cors_origins):
    logger.warning("CORS configuration: %s", _problem)

app = FastAPI(
    title="BrandGuard API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def register_routers() -> None:
    """Import route modules and register those exposing a router."""
    for module_info in pkgutil.iter_modules(routes_package.__path__):
        module_name = module_info.name

        if module_name.startswith("_"):
            continue

        try:
            module = importlib.import_module(
                f"{routes_package.__name__}.{module_name}"
            )
        except Exception:
            logger.exception("Failed to import route module: %s", module_name)
            raise

        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
            logger.info("Registered router: %s", module_name)
            print(f"Registered router: {module_name}")


register_routers()


@app.get("/api/health")
def health_check() -> dict[str, object]:
    """Return application health, the database check, and whether optional services are set up.

    Only yes/no flags are returned, never the values of keys or tokens.
    """
    current = get_settings()
    services = {
        # Without a Gemini key the AI claim check is skipped and only the rules run.
        "ai": "configured" if current.gemini_api_key else "not_configured",
        "slack": "configured" if current.slack_bot_token and current.slack_channel_id else "not_configured",
        "email": "configured" if current.smtp_host and current.smtp_from else "not_configured",
    }

    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        return {"status": "ok", "database": "down", "services": services}

    try:
        with pool.connection() as connection:
            connection.execute("SELECT 1").fetchone()

        return {"status": "ok", "database": "ok", "services": services}
    except Exception:
        logger.exception("Database health check failed")
        return {"status": "ok", "database": "down", "services": services}
