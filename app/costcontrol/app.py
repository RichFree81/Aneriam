"""FastAPI application — Cost Control MVP."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import import_export, packages, procurement, projects
from .config import BUNDLE_DIR
from .startup import initialise_database


app = FastAPI(title="Cost Control MVP")
app.mount("/static", StaticFiles(directory=str(BUNDLE_DIR / "static")), name="static")
app.include_router(import_export.router)
app.include_router(packages.router)
app.include_router(procurement.router)
app.include_router(projects.router)

# ---------------------------------------------------------------------------
# Startup: create tables and seed master data
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    initialise_database()


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8090, reload=False)
