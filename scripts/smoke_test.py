"""Headless check of the database, a bill, and every screen."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication

from database.db_manager import Database
from services.printer_service import build_receipt, sample_invoice
from ui.branding import ensure_brand_assets
from ui.main_window import MainWindow
from ui.theme import apply_theme, load_fonts


def main() -> None:
    app = QApplication([])
    load_fonts()
    apply_theme(app)
    ensure_brand_assets()
    folder = tempfile.mkdtemp(prefix="caveron-smoke-")
    try:
        db = Database(os.path.join(folder, "caveron_salon.db"))
        db.initialize()
        services = db.list_services()
        assert len(services) == 42, len(services)
        assert sum(1 for row in services if row["is_variable"]) == 16
        packages = db.list_packages()
        assert len(packages) == 9
        prices = {row["name"]: row["price"] for row in packages}
        assert prices["Deal 4"] == 800
        assert prices["Deal 5"] == 1600
        assert prices["Deal 6"] == 2200
        assert prices["Premium Deal 1"] == 4500
        assert prices["Premium Deal 3"] == 8000
        assert prices["Premium Deal 4"] == 4000
        assert prices["The Royal Package — Standard"] == 16000
        assert prices["The Royal Package — With Hydra"] == 19000
        assert prices["Essential Package"] == 13000
        keratin = next(row for row in services if row["name"] == "Keratin Straightening")
        assert keratin["is_variable"] and keratin["min_price"] == 2500 and keratin["max_price"] == 6000
        royal = next(row for row in packages if row["name"] == "The Royal Package — Standard")
        assert sum(item["qty"] for item in royal["items"]) == 16
        user = db.authenticate("admin", "caveron1987")
        assert user and user["role"] == "admin"
        assert db.authenticate("cashier", "cashier123")["role"] == "cashier"
        assert db.authenticate("admin", "wrong") is None
        customer = db.upsert_customer("Ali Hassan", "03001112233")
        staff = db.list_staff(active_only=True)[0]
        hair = next(row for row in services if row["name"] == "Hair Cut")
        beard = next(row for row in services if row["name"] == "Beard")
        invoice = db.checkout(
            {
                "items": [
                    {"kind": "service", "ref_id": hair["id"], "name": "Hair Cut", "qty": 1, "unit_price": 500, "staff_id": staff["id"], "is_groom": False, "detail": ""},
                    {"kind": "service", "ref_id": beard["id"], "name": "Beard", "qty": 1, "unit_price": 300, "staff_id": staff["id"], "is_groom": False, "detail": ""},
                ],
                "customer_id": customer["id"],
                "discount_type": "flat",
                "discount_value": 50,
                "tax_pct": 0,
                "payment_mode": "Cash",
                "cash_tendered": 1000,
                "username": "admin",
                "origin": "pos",
            }
        )
        assert invoice["total"] == 750
        assert invoice["change_due"] == 250
        assert invoice["invoice_no"].startswith("CV-")
        assert db.get_customer(customer["id"])["loyalty_points"] == 7
        lines = build_receipt(invoice, db.get_settings())
        text = " ".join(line.get("text") or line.get("left") or "" for line in lines)
        assert "CAVERON" in text
        assert "Hair Cut" in text
        deal = next(row for row in packages if row["name"] == "Essential Package")
        contract = db.enroll_groom(
            {
                "package_id": deal["id"],
                "customer_name": "Ali Hassan",
                "phone": "03001112233",
                "advance": 3000,
                "payment_mode": "Cash",
                "username": "admin",
            }
        )
        assert contract["balance"] == 10000
        session_id = contract["sessions"][0]["id"]
        contract = db.use_groom_session(session_id)
        assert contract["sessions"][0]["used_qty"] == 1
        from datetime import date

        start = date.today().replace(day=1).isoformat()
        end = date.today().isoformat()
        payroll = db.build_payroll(start, end)
        assert any(row["staff_name"] == staff["name"] and row["commission"] > 0 for row in payroll)
        report = db.run_report("sales", end, end)
        assert report["rows"]
        backup = os.path.join(folder, "backup.db")
        db.backup_to(backup)
        assert os.path.exists(backup)
        window = MainWindow(db, user)
        for view in window.views.values():
            view.refresh()
        window.views["pos"].new_bill()
        sample = build_receipt(sample_invoice(), db.get_settings())
        assert any(line.get("t") == "barcode" for line in sample)
        window.close()
        print("SMOKE OK", invoice["invoice_no"], "services", len(services), "views", len(window.views))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
