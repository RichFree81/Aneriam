"""
Settings Storage API — C-1.

Endpoints to read and write per-company, per-module configuration.
The application reads the company override first, falls back to defaults in code.

See docs/specs/module-settings.md for full specification.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_request_context, require_company_admin
from app.core.database import get_session
from app.models.module_settings import ModuleSettings
from app.schemas import RequestContext, SettingsRead, SettingsWrite

router = APIRouter()

# ── Application-level defaults ────────────────────────────────────────────────
# These are returned for any key that a company has not overridden.

_DEFAULTS: Dict[str, Dict[str, str]] = {
    "projects": {
        "display_name": "Projects",
        "id_prefix": "PRJ",
        "default_view": "list",
    },
    "portfolios": {
        "display_name": "Portfolios",
        "code_prefix": "PF",
    },
    "contracts": {
        "display_name": "Contracts",
        "id_prefix": "CTR",
    },
    "documents": {
        "display_name": "Documents",
    },
}


def _merge_settings(module_key: str, overrides: Dict[str, str]) -> Dict[str, str]:
    """Return application defaults for the module, updated with company overrides."""
    merged = dict(_DEFAULTS.get(module_key, {}))
    merged.update(overrides)
    return merged


@router.get("/{module_key}", response_model=SettingsRead)
def get_settings(
    module_key: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    Return resolved settings for the given module.
    Company overrides are merged over application defaults.
    """
    if not context.company_id:
        raise HTTPException(status_code=400, detail="No company context")

    rows = session.exec(
        select(ModuleSettings).where(
            ModuleSettings.company_id == context.company_id,
            ModuleSettings.module_key == module_key,
        )
    ).all()

    overrides = {row.key: row.value for row in rows}
    merged = _merge_settings(module_key, overrides)

    return SettingsRead(module_key=module_key, settings=merged)


@router.put("/{module_key}", response_model=SettingsRead)
def write_settings(
    module_key: str,
    body: SettingsWrite,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Write one or more key-value pairs for the current company's module.
    Existing keys are updated; new keys are inserted (upsert).
    Company admin only.
    """
    if not context.company_id:
        raise HTTPException(status_code=400, detail="No company context")

    now = datetime.now(timezone.utc)

    for key, value in body.settings.items():
        existing = session.exec(
            select(ModuleSettings).where(
                ModuleSettings.company_id == context.company_id,
                ModuleSettings.module_key == module_key,
                ModuleSettings.key == key,
            )
        ).first()

        if existing:
            existing.value = value
            existing.updated_at = now
            session.add(existing)
        else:
            row = ModuleSettings(
                company_id=context.company_id,
                module_key=module_key,
                key=key,
                value=value,
                created_at=now,
                updated_at=now,
            )
            session.add(row)

    session.commit()

    # Return updated state
    rows = session.exec(
        select(ModuleSettings).where(
            ModuleSettings.company_id == context.company_id,
            ModuleSettings.module_key == module_key,
        )
    ).all()
    overrides = {row.key: row.value for row in rows}
    merged = _merge_settings(module_key, overrides)

    return SettingsRead(module_key=module_key, settings=merged)


@router.delete("/{module_key}/{key}", status_code=status.HTTP_204_NO_CONTENT)
def reset_setting(
    module_key: str,
    key: str,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """
    Reset a setting to the application default by deleting the company override.
    Company admin only.
    """
    if not context.company_id:
        raise HTTPException(status_code=400, detail="No company context")

    row = session.exec(
        select(ModuleSettings).where(
            ModuleSettings.company_id == context.company_id,
            ModuleSettings.module_key == module_key,
            ModuleSettings.key == key,
        )
    ).first()

    if row:
        session.delete(row)
        session.commit()
