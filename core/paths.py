"""Writable app paths and bundled resource lookup."""

from __future__ import annotations

import os
import sys


def project_root() -> str:
    """Folder that holds the database, backups, and uploaded logo.

    In a PyInstaller build this is the folder of the .exe, so data survives
    updates of the bundled files.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundle_root() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", project_root())
    return project_root()


def user_path(*parts: str) -> str:
    return os.path.join(project_root(), *parts)


def resource(*parts: str) -> str:
    """Prefer a user-replaced file, then the bundled copy."""
    user = user_path(*parts)
    if os.path.exists(user):
        return user
    bundled = os.path.join(bundle_root(), *parts)
    if os.path.exists(bundled):
        return bundled
    return user


def db_path() -> str:
    return user_path("caveron_salon.db")


def ensure_dirs() -> None:
    for folder in ("assets", os.path.join("assets", "staff"), "backups", "logs", "fonts"):
        os.makedirs(user_path(folder), exist_ok=True)
