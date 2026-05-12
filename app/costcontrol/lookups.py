"""Common database lookup helpers used by route handlers."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Package, Project


def get_project_or_404(db: Session, project_number: str) -> Project:
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_package_or_404(db: Session, project_number: str, package_number: str) -> Package:
    package = (
        db.query(Package)
        .filter_by(package_number=package_number, project_number=project_number)
        .first()
    )
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return package
