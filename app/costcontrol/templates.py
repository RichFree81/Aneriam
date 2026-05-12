"""Jinja template environment for the Cost Control app."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from .config import BUNDLE_DIR
from .formatting import fmt_zar


TEMPLATES_DIR = BUNDLE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["zar"] = fmt_zar
