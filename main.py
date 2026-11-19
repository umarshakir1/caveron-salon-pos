"""CAVERON — Salon & Barber. Offline desktop entry point."""

from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from core.paths import db_path, ensure_dirs, user_path
from database.db_manager import Database
from ui.branding import ensure_brand_assets, window_icon
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from ui.theme import apply_theme, load_fonts


def _configure_logging() -> None:
    ensure_dirs()
    logging.basicConfig(
        filename=user_path("logs", "caveron.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    def handle(exc_type, exc, tb):
        if exc_type is KeyboardInterrupt:
            return
        logging.error("".join(traceback.format_exception(exc_type, exc, tb)))
        QMessageBox.critical(None, "CAVERON", f"Something went wrong.\n\n{exc}\n\nDetails were saved in the logs folder.")

    sys.excepthook = handle


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("CAVERON")
    app.setOrganizationName("CAVERON")
    _configure_logging()
    load_fonts()
    apply_theme(app, "dark")
    ensure_brand_assets()
    app.setWindowIcon(window_icon())
    database = Database(db_path())
    try:
        database.initialize()
    except Exception as exc:
        logging.exception("Database failed")
        QMessageBox.critical(None, "CAVERON", f"Could not open the salon database.\n{exc}")
        return 1

    apply_theme(app, database.get_settings().get("theme") or "dark")
    app.setQuitOnLastWindowClosed(True)
    while True:
        login = LoginDialog(database)
        login.setWindowIcon(window_icon())
        if login.exec() != QDialog.DialogCode.Accepted or not login.user:
            break
        window = MainWindow(database, login.user)
        window.show()
        app.exec()
        if not window.logged_out:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
