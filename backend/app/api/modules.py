"""
Modules API.

Lists available modules and (C-7) allows company admins to enable/disable
modules per company via the ModuleSettings store.
"""
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_current_user, get_request_context, require_company_admin
from app.core.database import get_session
from app.models import Module, User
from app.models.module_settings import ModuleSettings
from app.schemas import RequestContext

router = APIRouter()


class ModuleWithStatus(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    enabled: bool           # global enabled flag
    company_enabled: bool   # per-company override (resolves to enabled if no override)
    sort_order: int

    class Config:
        from_attributes = True


def _company_enabled(module_key: str, company_id: Optional[int], session: Session, global_enabled: bool) -> bool:
    """Return the effective enabled state for a company, falling back to the global flag."""
    if not company_id:
        return global_enabled
    row = session.exec(
        select(ModuleSettings).where(
            ModuleSettings.company_id == company_id,
            ModuleSettings.module_key == module_key,
            ModuleSettings.key == "enabled",
        )
    ).first()
    if row:
        return row.value.lower() == "true"
    return global_enabled


@router.get("", response_model=List[ModuleWithStatus])
def get_modules(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    List all modules with their effective enabled status for the current company.
    The company_enabled field reflects any per-company override.
    """
    modules = session.exec(select(Module).order_by(Module.sort_order, Module.name)).all()
    return [
        ModuleWithStatus(
            id=m.id,
            key=m.key,
            name=m.name,
            description=m.description,
            enabled=m.enabled,
            company_enabled=_company_enabled(m.key, context.company_id, session, m.enabled),
            sort_order=m.sort_order,
        )
        for m in modules
    ]


@router.patch("/{module_key}/enabled", response_model=ModuleWithStatus)
def set_module_enabled(
    module_key: str,
    enabled: bool,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Enable or disable a module for the current company.
    C-7: Connects the enabled flag to actual per-company configuration storage.
    Company admin only.
    """
    module = session.exec(select(Module).where(Module.key == module_key)).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    if not context.company_id:
        raise HTTPException(status_code=400, detail="No company context")

    now = datetime.now(timezone.utc)
    existing = session.exec(
        select(ModuleSettings).where(
            ModuleSettings.company_id == context.company_id,
            ModuleSettings.module_key == module_key,
            ModuleSettings.key == "enabled",
        )
    ).first()

    if existing:
        existing.value = "true" if enabled else "false"
        existing.updated_at = now
        session.add(existing)
    else:
        row = ModuleSettings(
            company_id=context.company_id,
            module_key=module_key,
            key="enabled",
            value="true" if enabled else "false",
            created_at=now,
            updated_at=now,
        )
        session.add(row)

    session.commit()

    return ModuleWithStatus(
        id=module.id,
        key=module.key,
        name=module.name,
        description=module.description,
        enabled=module.enabled,
        company_enabled=enabled,
        sort_order=module.sort_order,
    )
