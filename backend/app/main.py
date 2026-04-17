import json
import logging
import os

from dotenv import load_dotenv
load_dotenv()  # loads backend/.env before any module reads os.getenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    audit,
    auth,
    collaboration,
    fields,
    financial_notes,
    health,
    modules,
    portfolio_access,
    portfolios,
    projects,
    settings,
    users,
)
from app.core.database import create_db_and_tables
from app.core.security import validate_security_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_cors_origins() -> list[str]:
    """Parse BACKEND_CORS_ORIGINS env var (JSON array) or default to local dev ports."""
    env_value = os.getenv("BACKEND_CORS_ORIGINS")
    if env_value:
        try:
            parsed = json.loads(env_value)
            if isinstance(parsed, list):
                return parsed
            logger.warning("BACKEND_CORS_ORIGINS is not a list; using defaults")
        except json.JSONDecodeError:
            logger.warning("BACKEND_CORS_ORIGINS is not valid JSON; using defaults")
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app = FastAPI(title="Aneriam API")

# CORS Configuration
origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(modules.router, prefix="/modules", tags=["Modules"])
app.include_router(portfolios.router, prefix="/portfolios", tags=["Portfolios"])
app.include_router(projects.router, prefix="/projects", tags=["Projects"])
app.include_router(settings.router, prefix="/settings", tags=["Settings"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(fields.router, tags=["Fields"])
app.include_router(portfolio_access.router, prefix="/portfolios", tags=["Portfolio Access"])
app.include_router(collaboration.router, tags=["Collaboration"])
app.include_router(financial_notes.router, tags=["Financial Notes"])
app.include_router(audit.router, prefix="/audit", tags=["Audit"])


@app.on_event("startup")
def on_startup():
    validate_security_config()
    create_db_and_tables()
    logger.info("Aneriam API started with CORS origins: %s", origins)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
