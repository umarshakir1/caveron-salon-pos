"""Local SQLite database: schema, seed, billing, payroll, and reports."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from core.security import hash_password, verify_password
from core.utils import (
    PAY_CARD,
    PAY_CASH,
    PAY_SPLIT,
    PAY_TRANSFER,
    SALARY_FIXED,
    money,
    month_bounds,
    now_str,
    pays_base,
    pays_commission,
    round_money,
    today_str,
)
from database.seed_data import (
    CATEGORIES,
    DEFAULT_SETTINGS,
    DEFAULT_USERS,
    PACKAGES,
    SAMPLE_PRODUCTS,
    SAMPLE_STAFF,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    min_price REAL NOT NULL,
    max_price REAL NOT NULL,
    is_variable INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tier TEXT NOT NULL,
    price REAL NOT NULL,
    description TEXT,
    is_groom INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS package_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(package_id) REFERENCES packages(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    notes TEXT,
    loyalty_points INTEGER NOT NULL DEFAULT 0,
    visits INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    phone TEXT,
    cnic TEXT,
    joining_date TEXT,
    photo_path TEXT,
    salary_type TEXT NOT NULL,
    base_salary REAL NOT NULL DEFAULT 0,
    commission_pct REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    att_date TEXT NOT NULL,
    status TEXT NOT NULL,
    check_in TEXT,
    check_out TEXT,
    hours REAL NOT NULL DEFAULT 0,
    UNIQUE(staff_id, att_date)
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER,
    customer_name TEXT,
    customer_phone TEXT,
    subtotal REAL NOT NULL,
    discount_type TEXT,
    discount_value REAL NOT NULL DEFAULT 0,
    discount_amount REAL NOT NULL DEFAULT 0,
    tax_pct REAL NOT NULL DEFAULT 0,
    tax_amount REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL,
    payment_mode TEXT NOT NULL,
    cash_amount REAL NOT NULL DEFAULT 0,
    card_amount REAL NOT NULL DEFAULT 0,
    transfer_amount REAL NOT NULL DEFAULT 0,
    cash_tendered REAL NOT NULL DEFAULT 0,
    change_due REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'paid',
    origin TEXT NOT NULL DEFAULT 'pos',
    notes TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    voided_at TEXT,
    voided_by TEXT
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    ref_id INTEGER,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL,
    staff_id INTEGER,
    staff_name TEXT,
    detail TEXT,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id)
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT,
    customer_id INTEGER,
    customer_name TEXT NOT NULL,
    phone TEXT,
    staff_id INTEGER,
    staff_name TEXT,
    service_id INTEGER,
    package_id INTEGER,
    service_name TEXT,
    appt_date TEXT NOT NULL,
    appt_time TEXT NOT NULL,
    chair TEXT,
    status TEXT NOT NULL,
    is_walkin INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    invoice_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS groom_contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id INTEGER,
    package_name TEXT NOT NULL,
    customer_id INTEGER,
    customer_name TEXT NOT NULL,
    phone TEXT,
    mayon_date TEXT,
    barat_date TEXT,
    valima_date TEXT,
    total_price REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    source_invoice_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS groom_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    total_qty INTEGER NOT NULL,
    used_qty INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(contract_id) REFERENCES groom_contracts(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS groom_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    payment_mode TEXT NOT NULL,
    invoice_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(contract_id) REFERENCES groom_contracts(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS groom_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    visit_date TEXT NOT NULL,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exp_date TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    payment_mode TEXT NOT NULL DEFAULT 'Cash',
    expense_type TEXT NOT NULL DEFAULT 'daily',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    unit TEXT,
    qty REAL NOT NULL DEFAULT 0,
    reorder_level REAL NOT NULL DEFAULT 0,
    cost_price REAL NOT NULL DEFAULT 0,
    sell_price REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS stock_moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    qty_change REAL NOT NULL,
    reason TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    adj_date TEXT NOT NULL,
    kind TEXT NOT NULL,
    amount REAL NOT NULL,
    notes TEXT,
    payment_mode TEXT NOT NULL DEFAULT 'Cash',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drawer_days (
    business_date TEXT PRIMARY KEY,
    opening_balance REAL NOT NULL DEFAULT 0,
    opened_at TEXT,
    closed_at TEXT,
    actual_cash REAL,
    expected_cash REAL,
    difference REAL,
    note TEXT,
    closed_by TEXT
);
CREATE TABLE IF NOT EXISTS payroll (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    staff_name TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    base_salary REAL NOT NULL,
    commission REAL NOT NULL,
    advances REAL NOT NULL,
    deductions REAL NOT NULL,
    tips REAL NOT NULL,
    bonuses REAL NOT NULL,
    net_payable REAL NOT NULL,
    present_units REAL NOT NULL DEFAULT 0,
    period_days INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'unpaid',
    paid_at TEXT,
    UNIQUE(staff_id, period_start, period_end)
);
CREATE INDEX IF NOT EXISTS idx_inv_created ON invoices(created_at);
CREATE INDEX IF NOT EXISTS idx_inv_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_items_inv ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_items_staff ON invoice_items(staff_id);
CREATE INDEX IF NOT EXISTS idx_appt_date ON appointments(appt_date);
CREATE INDEX IF NOT EXISTS idx_exp_date ON expenses(exp_date);
"""


def _dicts(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


class Database:
    def __init__(self, path: str):
        self.path = path
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def q(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.connect() as conn:
            return _dicts(conn.execute(sql, params))

    def q1(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def initialize(self) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript(SCHEMA)
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
        finally:
            conn.close()
        with self.connect() as conn:
            self._migrate(conn)
            self._seed(conn)
        try:
            self.auto_backup()
        except Exception:
            logging.exception("Automatic backup failed")

    def _migrate(self, conn: sqlite3.Connection) -> None:
        def columns(table: str) -> set[str]:
            return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}

        if "expense_type" not in columns("expenses"):
            conn.execute("ALTER TABLE expenses ADD COLUMN expense_type TEXT NOT NULL DEFAULT 'daily'")
        if "payment_mode" not in columns("adjustments"):
            conn.execute("ALTER TABLE adjustments ADD COLUMN payment_mode TEXT NOT NULL DEFAULT 'Cash'")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS drawer_days (
                business_date TEXT PRIMARY KEY,
                opening_balance REAL NOT NULL DEFAULT 0,
                opened_at TEXT,
                closed_at TEXT,
                actual_cash REAL,
                expected_cash REAL,
                difference REAL,
                note TEXT,
                closed_by TEXT
            )"""
        )

    def _seed(self, conn: sqlite3.Connection) -> None:
        self._ensure_settings(conn)
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if user_count == 0:
            for user in DEFAULT_USERS:
                conn.execute(
                    """INSERT INTO users (username, password_hash, display_name, role, active, created_at)
                       VALUES (?, ?, ?, ?, 1, ?)""",
                    (
                        user["username"],
                        hash_password(user["password"]),
                        user["display_name"],
                        user["role"],
                        now_str(),
                    ),
                )
        category_count = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        if category_count:
            return
        for index, category in enumerate(CATEGORIES):
            cur = conn.execute(
                "INSERT INTO categories (name, sort_order, active) VALUES (?, ?, 1)",
                (category["name"], index),
            )
            category_id = cur.lastrowid
            for order, service in enumerate(category["services"]):
                variable = bool(service.get("variable"))
                min_price = service["min"] if variable else service["price"]
                max_price = service["max"] if variable else service["price"]
                conn.execute(
                    """INSERT INTO services
                       (category_id, name, min_price, max_price, is_variable, active, sort_order)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (category_id, service["name"], min_price, max_price, 1 if variable else 0, order),
                )
        for index, package in enumerate(PACKAGES):
            cur = conn.execute(
                """INSERT INTO packages (name, tier, price, description, is_groom, active, sort_order)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (
                    package["name"],
                    package["tier"],
                    package["price"],
                    package["description"],
                    1 if package["is_groom"] else 0,
                    index,
                ),
            )
            package_id = cur.lastrowid
            for order, (item_name, qty) in enumerate(package["items"]):
                conn.execute(
                    "INSERT INTO package_items (package_id, name, qty, sort_order) VALUES (?, ?, ?, ?)",
                    (package_id, item_name, qty, order),
                )
        for member in SAMPLE_STAFF:
            conn.execute(
                """INSERT INTO staff
                   (name, role, phone, cnic, joining_date, photo_path, salary_type, base_salary, commission_pct, active, created_at)
                   VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, 1, ?)""",
                (
                    member["name"],
                    member["role"],
                    member["phone"],
                    member["cnic"],
                    today_str(),
                    member["salary_type"],
                    member["base_salary"],
                    member["commission_pct"],
                    now_str(),
                ),
            )
        for product in SAMPLE_PRODUCTS:
            conn.execute(
                """INSERT INTO products
                   (name, category, unit, qty, reorder_level, cost_price, sell_price, active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    product["name"],
                    product["category"],
                    product["unit"],
                    product["qty"],
                    product["reorder_level"],
                    product["cost_price"],
                    product["sell_price"],
                ),
            )

    def _ensure_settings(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT value FROM settings WHERE key = 'app'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('app', ?)",
                (json.dumps(DEFAULT_SETTINGS),),
            )

    def checkpoint(self) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        finally:
            conn.close()
        for suffix in ("-wal", "-shm"):
            extra = self.path + suffix
            if os.path.exists(extra):
                try:
                    os.remove(extra)
                except OSError:
                    logging.exception("Could not remove %s", extra)

    def backup_to(self, dest: str) -> str:
        folder = os.path.dirname(dest)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with self.connect() as conn:
            target = sqlite3.connect(dest)
            try:
                conn.backup(target)
            finally:
                target.close()
        return dest

    def auto_backup(self) -> None:
        folder = os.path.join(os.path.dirname(self.path), "backups")
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, f"caveron_{today_str()}.db")
        if not os.path.exists(dest):
            self.backup_to(dest)

    def restore_from(self, src: str) -> None:
        if not os.path.isfile(src):
            raise ValueError("Backup file was not found.")
        probe = sqlite3.connect(src)
        try:
            names = {row[0] for row in probe.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            probe.close()
        if "invoices" not in names or "services" not in names or "users" not in names:
            raise ValueError("That file is not a CAVERON backup.")
        self.checkpoint()
        temporary = self.path + ".restore"
        source = sqlite3.connect(src)
        target = sqlite3.connect(temporary)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        os.replace(temporary, self.path)
        self.checkpoint()

    def factory_reset(self) -> None:
        self.checkpoint()
        for suffix in ("", "-wal", "-shm"):
            target = self.path + suffix if suffix else self.path
            if os.path.exists(target):
                os.remove(target)
        self.initialize()

    # ------------------------------------------------------------------ settings
    def get_settings(self) -> dict:
        row = self.q1("SELECT value FROM settings WHERE key = 'app'")
        stored = json.loads(row["value"]) if row else {}
        merged = dict(DEFAULT_SETTINGS)
        merged.update(stored)
        return merged

    def save_settings(self, updates: dict) -> dict:
        current = self.get_settings()
        current.update(updates)
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('app', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (json.dumps(current),),
            )
        return current

    def list_chairs(self) -> list[str]:
        stored = self.get_settings().get("chairs") or []
        names = []
        for name in stored:
            text = str(name).strip()
            if text and text.lower() != "any" and text not in names:
                names.append(text)
        return ["Any", *names]

    def save_chairs(self, names: list[str]) -> list[str]:
        clean = []
        for name in names:
            text = str(name).strip()
            if text and text.lower() != "any" and text not in clean:
                clean.append(text)
        self.save_settings({"chairs": clean})
        return ["Any", *clean]

    # --------------------------------------------------------------------- users
    def authenticate(self, username: str, password: str) -> dict | None:
        row = self.q1("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),))
        if not row or not row["active"]:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return self._public_user(row)

    def list_users(self) -> list[dict]:
        rows = self.q("SELECT * FROM users ORDER BY role, username")
        return [self._public_user(row) for row in rows]

    def save_user(self, data: dict) -> int:
        username = data["username"].strip()
        display = data["display_name"].strip()
        role = data["role"]
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if not display:
            raise ValueError("Display name is required.")
        if role not in ("admin", "cashier"):
            raise ValueError("Choose a valid role.")
        password = data.get("password") or ""
        with self.connect() as conn:
            if data.get("id"):
                existing = conn.execute("SELECT * FROM users WHERE id = ?", (data["id"],)).fetchone()
                if existing is None:
                    raise ValueError("User was not found.")
                clash = conn.execute(
                    "SELECT id FROM users WHERE username = ? COLLATE NOCASE AND id != ?",
                    (username, data["id"]),
                ).fetchone()
                if clash:
                    raise ValueError("That username is already in use.")
                if existing["role"] == "admin" and role != "admin":
                    self._guard_last_admin(conn, existing["id"])
                conn.execute(
                    "UPDATE users SET username = ?, display_name = ?, role = ? WHERE id = ?",
                    (username, display, role, data["id"]),
                )
                if password:
                    self._check_password(password)
                    conn.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (hash_password(password), data["id"]),
                    )
                return int(data["id"])
            if not password:
                raise ValueError("A password or PIN is required.")
            self._check_password(password)
            clash = conn.execute(
                "SELECT id FROM users WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
            if clash:
                raise ValueError("That username is already in use.")
            cur = conn.execute(
                """INSERT INTO users (username, password_hash, display_name, role, active, created_at)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (username, hash_password(password), display, role, now_str()),
            )
            return int(cur.lastrowid)

    def set_password(self, user_id: int, password: str) -> None:
        self._check_password(password)
        with self.connect() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))

    def set_user_active(self, user_id: int, active: bool, acting_user_id: int) -> None:
        with self.connect() as conn:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:
                raise ValueError("User was not found.")
            if not active and user_id == acting_user_id:
                raise ValueError("You cannot deactivate the account you are signed in with.")
            if not active and user["role"] == "admin":
                self._guard_last_admin(conn, user_id)
            conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))

    def _guard_last_admin(self, conn, user_id: int) -> None:
        others = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND active = 1 AND id != ?",
            (user_id,),
        ).fetchone()["c"]
        if others < 1:
            raise ValueError("The salon needs at least one active Admin / Owner account.")

    @staticmethod
    def _check_password(password: str) -> None:
        if len(password) < 4:
            raise ValueError("Password or PIN must be at least 4 characters.")

    @staticmethod
    def _public_user(row: dict) -> dict:
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role"],
            "active": row["active"],
        }

    # ----------------------------------------------------------------- catalogue
    def list_categories(self, active_only: bool = False) -> list[dict]:
        if active_only:
            return self.q("SELECT * FROM categories WHERE active = 1 ORDER BY sort_order, name")
        return self.q("SELECT * FROM categories ORDER BY sort_order, name")

    def save_category(self, data: dict) -> int:
        name = data["name"].strip()
        if not name:
            raise ValueError("Category name is required.")
        sort_order = int(data.get("sort_order") or 0)
        active = 1 if data.get("active", True) else 0
        with self.connect() as conn:
            if data.get("id"):
                clash = conn.execute(
                    "SELECT id FROM categories WHERE name = ? AND id != ?",
                    (name, data["id"]),
                ).fetchone()
                if clash:
                    raise ValueError("A category with that name already exists.")
                conn.execute(
                    "UPDATE categories SET name = ?, sort_order = ?, active = ? WHERE id = ?",
                    (name, sort_order, active, data["id"]),
                )
                return int(data["id"])
            clash = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
            if clash:
                raise ValueError("A category with that name already exists.")
            cur = conn.execute(
                "INSERT INTO categories (name, sort_order, active) VALUES (?, ?, ?)",
                (name, sort_order, active),
            )
            return int(cur.lastrowid)

    def delete_category(self, category_id: int) -> str:
        with self.connect() as conn:
            used = conn.execute(
                "SELECT COUNT(*) AS c FROM services WHERE category_id = ?",
                (category_id,),
            ).fetchone()["c"]
            if used:
                raise ValueError("Move or delete the services in this category first.")
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        return "deleted"

    def list_services(self, active_only: bool = False, category_id: int | None = None, search: str = "") -> list[dict]:
        sql = """
            SELECT s.*, c.name AS category_name
            FROM services s
            JOIN categories c ON c.id = s.category_id
            WHERE (? = 0 OR s.active = 1)
              AND (? IS NULL OR s.category_id = ?)
              AND (? = '' OR s.name LIKE ?)
            ORDER BY c.sort_order, s.sort_order, s.name
        """
        like = f"%{search.strip()}%"
        return self.q(sql, (1 if active_only else 0, category_id, category_id, search.strip(), like))

    def get_service(self, service_id: int) -> dict | None:
        return self.q1(
            """SELECT s.*, c.name AS category_name
               FROM services s JOIN categories c ON c.id = s.category_id
               WHERE s.id = ?""",
            (service_id,),
        )

    def save_service(self, data: dict) -> int:
        name = data["name"].strip()
        if not name:
            raise ValueError("Service name is required.")
        variable = bool(data.get("is_variable"))
        min_price = round_money(data.get("min_price") or 0)
        max_price = round_money(data.get("max_price") or min_price)
        if min_price < 0 or max_price < 0:
            raise ValueError("Price cannot be negative.")
        if variable and max_price < min_price:
            raise ValueError("The maximum price must be at least the minimum.")
        if not variable:
            max_price = min_price
        active = 1 if data.get("active", True) else 0
        with self.connect() as conn:
            if data.get("id"):
                conn.execute(
                    """UPDATE services
                       SET category_id = ?, name = ?, min_price = ?, max_price = ?, is_variable = ?, active = ?
                       WHERE id = ?""",
                    (data["category_id"], name, min_price, max_price, 1 if variable else 0, active, data["id"]),
                )
                return int(data["id"])
            order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM services WHERE category_id = ?",
                (data["category_id"],),
            ).fetchone()["n"]
            cur = conn.execute(
                """INSERT INTO services
                   (category_id, name, min_price, max_price, is_variable, active, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (data["category_id"], name, min_price, max_price, 1 if variable else 0, active, order),
            )
            return int(cur.lastrowid)

    def delete_service(self, service_id: int) -> str:
        with self.connect() as conn:
            used = conn.execute(
                "SELECT COUNT(*) AS c FROM invoice_items WHERE kind = 'service' AND ref_id = ?",
                (service_id,),
            ).fetchone()["c"]
            if used:
                conn.execute("UPDATE services SET active = 0 WHERE id = ?", (service_id,))
                return "deactivated"
            conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
        return "deleted"

    def list_packages(self, active_only: bool = False, groom_only: bool = False) -> list[dict]:
        rows = self.q(
            """SELECT * FROM packages
               WHERE (? = 0 OR active = 1) AND (? = 0 OR is_groom = 1)
               ORDER BY sort_order, id""",
            (1 if active_only else 0, 1 if groom_only else 0),
        )
        if not rows:
            return rows
        ids = [row["id"] for row in rows]
        marks = ",".join("?" for _ in ids)
        items = self.q(
            f"SELECT * FROM package_items WHERE package_id IN ({marks}) ORDER BY sort_order, id",
            tuple(ids),
        )
        grouped: dict[int, list] = {row["id"]: [] for row in rows}
        for item in items:
            grouped[item["package_id"]].append(item)
        for row in rows:
            row["items"] = grouped.get(row["id"], [])
        return rows

    def get_package(self, package_id: int) -> dict | None:
        row = self.q1("SELECT * FROM packages WHERE id = ?", (package_id,))
        if not row:
            return None
        row["items"] = self.q(
            "SELECT * FROM package_items WHERE package_id = ? ORDER BY sort_order, id",
            (package_id,),
        )
        return row

    def save_package(self, data: dict, items: list[dict]) -> int:
        name = data["name"].strip()
        if not name:
            raise ValueError("Package name is required.")
        price = round_money(data.get("price") or 0)
        if price < 0:
            raise ValueError("Package price cannot be negative.")
        clean_items = []
        for item in items:
            item_name = (item.get("name") or "").strip()
            if not item_name:
                continue
            qty = int(item.get("qty") or 1)
            if qty < 1:
                raise ValueError("Session quantity must be at least 1.")
            clean_items.append((item_name, qty))
        if not clean_items:
            raise ValueError("Add at least one included service.")
        is_groom = 1 if data.get("is_groom") or data.get("tier") == "Signature Groom" else 0
        active = 1 if data.get("active", True) else 0
        with self.connect() as conn:
            if data.get("id"):
                package_id = int(data["id"])
                conn.execute(
                    """UPDATE packages
                       SET name = ?, tier = ?, price = ?, description = ?, is_groom = ?, active = ?
                       WHERE id = ?""",
                    (name, data["tier"], price, data.get("description") or "", is_groom, active, package_id),
                )
                conn.execute("DELETE FROM package_items WHERE package_id = ?", (package_id,))
            else:
                order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM packages").fetchone()["n"]
                cur = conn.execute(
                    """INSERT INTO packages (name, tier, price, description, is_groom, active, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (name, data["tier"], price, data.get("description") or "", is_groom, active, order),
                )
                package_id = int(cur.lastrowid)
            for order, (item_name, qty) in enumerate(clean_items):
                conn.execute(
                    "INSERT INTO package_items (package_id, name, qty, sort_order) VALUES (?, ?, ?, ?)",
                    (package_id, item_name, qty, order),
                )
        return package_id

    def delete_package(self, package_id: int) -> str:
        with self.connect() as conn:
            used_invoice = conn.execute(
                "SELECT COUNT(*) AS c FROM invoice_items WHERE kind = 'package' AND ref_id = ?",
                (package_id,),
            ).fetchone()["c"]
            used_contract = conn.execute(
                "SELECT COUNT(*) AS c FROM groom_contracts WHERE package_id = ?",
                (package_id,),
            ).fetchone()["c"]
            if used_invoice or used_contract:
                conn.execute("UPDATE packages SET active = 0 WHERE id = ?", (package_id,))
                return "deactivated"
            conn.execute("DELETE FROM package_items WHERE package_id = ?", (package_id,))
            conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
        return "deleted"

    # ------------------------------------------------------------------ customers
    def search_customers(self, text: str, limit: int = 30) -> list[dict]:
        like = f"%{text.strip()}%"
        return self.q(
            """SELECT * FROM customers
               WHERE name LIKE ? OR phone LIKE ?
               ORDER BY name LIMIT ?""",
            (like, like, limit),
        )

    def get_customer(self, customer_id: int) -> dict | None:
        return self.q1("SELECT * FROM customers WHERE id = ?", (customer_id,))

    def find_customer_by_phone(self, phone: str) -> dict | None:
        return self.q1("SELECT * FROM customers WHERE phone = ?", (phone.strip(),))

    def upsert_customer(self, name: str, phone: str, notes: str = "") -> dict:
        name = name.strip()
        phone = phone.strip()
        if not name:
            raise ValueError("Client name is required.")
        if len(phone) < 7:
            raise ValueError("Enter a phone number so the client can be found again.")
        with self.connect() as conn:
            existing = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE customers SET name = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END WHERE id = ?",
                    (name, notes.strip(), notes.strip(), existing["id"]),
                )
                customer_id = existing["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO customers (name, phone, notes, created_at) VALUES (?, ?, ?, ?)",
                    (name, phone, notes.strip(), now_str()),
                )
                customer_id = cur.lastrowid
        found = self.get_customer(int(customer_id))
        if found is None:
            raise ValueError("Client could not be saved.")
        return found

    def customer_history(self, customer_id: int, limit: int = 20) -> list[dict]:
        return self.q(
            "SELECT * FROM invoices WHERE customer_id = ? ORDER BY created_at DESC LIMIT ?",
            (customer_id, limit),
        )

    # ---------------------------------------------------------------------- staff
    def list_staff(self, active_only: bool = False) -> list[dict]:
        if active_only:
            return self.q("SELECT * FROM staff WHERE active = 1 ORDER BY name")
        return self.q("SELECT * FROM staff ORDER BY active DESC, name")

    def get_staff(self, staff_id: int) -> dict | None:
        return self.q1("SELECT * FROM staff WHERE id = ?", (staff_id,))

    def save_staff(self, data: dict) -> int:
        name = data["name"].strip()
        if not name:
            raise ValueError("Staff name is required.")
        base_salary = round_money(data.get("base_salary") or 0)
        commission = float(data.get("commission_pct") or 0)
        if base_salary < 0:
            raise ValueError("Salary cannot be negative.")
        if commission < 0 or commission > 100:
            raise ValueError("Commission must be between 0 and 100.")
        active = 1 if data.get("active", True) else 0
        fields = (
            name,
            data["role"],
            (data.get("phone") or "").strip(),
            (data.get("cnic") or "").strip(),
            data.get("joining_date") or today_str(),
            data.get("photo_path") or "",
            data["salary_type"],
            base_salary,
            commission,
            active,
        )
        with self.connect() as conn:
            if data.get("id"):
                conn.execute(
                    """UPDATE staff
                       SET name = ?, role = ?, phone = ?, cnic = ?, joining_date = ?, photo_path = ?,
                           salary_type = ?, base_salary = ?, commission_pct = ?, active = ?
                       WHERE id = ?""",
                    (*fields, data["id"]),
                )
                return int(data["id"])
            cur = conn.execute(
                """INSERT INTO staff
                   (name, role, phone, cnic, joining_date, photo_path, salary_type, base_salary, commission_pct, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*fields, now_str()),
            )
            return int(cur.lastrowid)

    def set_staff_active(self, staff_id: int, active: bool) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE staff SET active = ? WHERE id = ?", (1 if active else 0, staff_id))

    def attendance_day(self, att_date: str) -> list[dict]:
        return self.q(
            """SELECT s.id AS staff_id, s.name, s.role, s.active,
                      a.id AS attendance_id, a.status, a.check_in, a.check_out, a.hours
               FROM staff s
               LEFT JOIN attendance a ON a.staff_id = s.id AND a.att_date = ?
               WHERE s.active = 1
               ORDER BY s.name""",
            (att_date,),
        )

    def save_attendance(self, staff_id: int, att_date: str, status: str, check_in: str, check_out: str) -> None:
        hours = _hours_between(check_in, check_out)
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO attendance (staff_id, att_date, status, check_in, check_out, hours)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(staff_id, att_date) DO UPDATE SET
                     status = excluded.status,
                     check_in = excluded.check_in,
                     check_out = excluded.check_out,
                     hours = excluded.hours""",
                (staff_id, att_date, status, check_in or None, check_out or None, hours),
            )

    def check_in(self, staff_id: int, att_date: str, clock: str) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM attendance WHERE staff_id = ? AND att_date = ?",
                (staff_id, att_date),
            ).fetchone()
            if row and row["check_in"]:
                raise ValueError("Already checked in.")
            status = row["status"] if row and row["status"] in ("Half-Day", "Leave") else "Present"
            if status == "Leave":
                status = "Present"
            conn.execute(
                """INSERT INTO attendance (staff_id, att_date, status, check_in, check_out, hours)
                   VALUES (?, ?, ?, ?, NULL, 0)
                   ON CONFLICT(staff_id, att_date) DO UPDATE SET
                     status = excluded.status,
                     check_in = excluded.check_in""",
                (staff_id, att_date, status, clock),
            )

    def check_out(self, staff_id: int, att_date: str, clock: str) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM attendance WHERE staff_id = ? AND att_date = ?",
                (staff_id, att_date),
            ).fetchone()
            if row is None or not row["check_in"]:
                raise ValueError("Check in before checking out.")
            if row["check_out"]:
                raise ValueError("Already checked out.")
            hours = _hours_between(row["check_in"], clock)
            conn.execute(
                "UPDATE attendance SET check_out = ?, hours = ? WHERE id = ?",
                (clock, hours, row["id"]),
            )

    # -------------------------------------------------------------------- billing
    def checkout(self, payload: dict) -> dict:
        items = payload.get("items") or []
        if not items:
            raise ValueError("Add at least one service or deal.")
        clean_items = []
        for item in items:
            qty = int(item.get("qty") or 0)
            price = round_money(item.get("unit_price") or 0)
            if qty < 1:
                raise ValueError("Quantity must be at least 1.")
            if price < 0:
                raise ValueError("Price cannot be negative.")
            clean_items.append(
                {
                    "kind": item["kind"],
                    "ref_id": item.get("ref_id"),
                    "name": item["name"],
                    "qty": qty,
                    "unit_price": price,
                    "staff_id": item.get("staff_id"),
                    "is_groom": bool(item.get("is_groom")),
                    "detail": item.get("detail") or "",
                }
            )
        subtotal, discount, tax, total = _compute_totals(
            clean_items,
            payload.get("discount_type") or "none",
            float(payload.get("discount_value") or 0),
            float(payload.get("tax_pct") or 0),
        )
        mode = payload["payment_mode"]
        tendered = round_money(payload.get("cash_tendered") or 0)
        split_cash = round_money(payload.get("split_cash") or 0)
        split_card = round_money(payload.get("split_card") or 0)
        split_transfer = round_money(payload.get("split_transfer") or 0)
        cash_amount = card_amount = transfer_amount = 0.0
        change_due = 0.0
        if mode == PAY_CASH:
            if tendered + 0.009 < total:
                raise ValueError("Cash received is less than the bill total.")
            cash_amount = total
            change_due = round_money(tendered - total)
        elif mode == PAY_CARD:
            card_amount = total
            tendered = total
        elif mode == PAY_TRANSFER:
            transfer_amount = total
            tendered = total
        elif mode == PAY_SPLIT:
            if abs((split_cash + split_card + split_transfer) - total) > 0.05:
                raise ValueError("Split amounts must add up to the bill total.")
            cash_amount, card_amount, transfer_amount = split_cash, split_card, split_transfer
            tendered = split_cash
        else:
            raise ValueError("Choose a payment mode.")

        customer_id = payload.get("customer_id")
        appointment_id = payload.get("appointment_id")
        created = now_str()
        with self.connect() as conn:
            customer_name = "Walk-in Client"
            customer_phone = ""
            if customer_id:
                customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
                if customer is None:
                    raise ValueError("Selected client was not found.")
                customer_name = customer["name"]
                customer_phone = customer["phone"]
            for item in clean_items:
                if item["is_groom"] and not customer_id:
                    raise ValueError(
                        "Select or add a client before selling a groom package. Sessions are tracked on their phone number."
                    )
                if item["is_groom"] and item["qty"] != 1:
                    raise ValueError("Sell a groom package one at a time.")
                if item["is_groom"] and customer_id:
                    existing = conn.execute(
                        """SELECT id, package_name FROM groom_contracts
                           WHERE customer_id = ? AND package_id = ? AND status = 'active' LIMIT 1""",
                        (customer_id, item["ref_id"]),
                    ).fetchone()
                    if existing:
                        raise ValueError(
                            f"{customer_name} already has an active {existing['package_name']}. "
                            "Record the next payment in Groom Tracker."
                        )
            invoice_no = self._next_invoice_no(conn, created)
            cur = conn.execute(
                """INSERT INTO invoices (
                       invoice_no, customer_id, customer_name, customer_phone, subtotal, discount_type,
                       discount_value, discount_amount, tax_pct, tax_amount, total, payment_mode,
                       cash_amount, card_amount, transfer_amount, cash_tendered, change_due, status,
                       origin, notes, created_by, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', ?, ?, ?, ?)""",
                (
                    invoice_no,
                    customer_id,
                    customer_name,
                    customer_phone,
                    subtotal,
                    payload.get("discount_type") or "none",
                    float(payload.get("discount_value") or 0),
                    discount,
                    float(payload.get("tax_pct") or 0),
                    tax,
                    total,
                    mode,
                    cash_amount,
                    card_amount,
                    transfer_amount,
                    tendered,
                    change_due,
                    payload.get("origin") or "pos",
                    (payload.get("notes") or "").strip(),
                    payload.get("username") or "",
                    created,
                ),
            )
            invoice_id = int(cur.lastrowid)
            for item in clean_items:
                staff_name = ""
                staff_id = item["staff_id"]
                if staff_id:
                    staff = conn.execute("SELECT id, name FROM staff WHERE id = ?", (staff_id,)).fetchone()
                    if staff:
                        staff_name = staff["name"]
                    else:
                        staff_id = None
                line_total = round_money(item["unit_price"] * item["qty"])
                conn.execute(
                    """INSERT INTO invoice_items
                       (invoice_id, kind, ref_id, name, qty, unit_price, line_total, staff_id, staff_name, detail)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        invoice_id,
                        item["kind"],
                        item["ref_id"],
                        item["name"],
                        item["qty"],
                        item["unit_price"],
                        line_total,
                        staff_id,
                        staff_name,
                        item["detail"],
                    ),
                )
                if item["is_groom"]:
                    package_row = conn.execute(
                        "SELECT price FROM packages WHERE id = ?",
                        (item["ref_id"],),
                    ).fetchone()
                    if package_row is None:
                        raise ValueError("That groom package is no longer on the menu.")
                    ratio = ((subtotal - discount) / subtotal) if subtotal else 1
                    paid_amount = round_money(min(float(package_row["price"]), line_total * ratio))
                    self._create_contract_tx(
                        conn,
                        package_id=item["ref_id"],
                        customer_id=customer_id,
                        customer_name=customer_name,
                        phone=customer_phone,
                        paid_amount=paid_amount,
                        payment_mode=mode,
                        invoice_id=invoice_id,
                        notes="Opened from POS bill " + invoice_no,
                    )
            if customer_id:
                points = int(total // 100)
                conn.execute(
                    "UPDATE customers SET loyalty_points = loyalty_points + ?, visits = visits + 1 WHERE id = ?",
                    (points, customer_id),
                )
            if appointment_id:
                conn.execute(
                    "UPDATE appointments SET status = 'Completed', invoice_id = ? WHERE id = ? AND status != 'Cancelled'",
                    (invoice_id, appointment_id),
                )
        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            raise ValueError("The bill was saved but could not be read back.")
        return invoice

    def _create_contract_tx(
        self,
        conn,
        package_id: int,
        customer_id: int | None,
        customer_name: str,
        phone: str,
        paid_amount: float,
        payment_mode: str,
        invoice_id: int,
        notes: str,
        mayon_date: str = "",
        barat_date: str = "",
        valima_date: str = "",
    ) -> int:
        package = conn.execute("SELECT * FROM packages WHERE id = ?", (package_id,)).fetchone()
        if package is None:
            raise ValueError("That package is no longer on the menu.")
        cur = conn.execute(
            """INSERT INTO groom_contracts
               (package_id, package_name, customer_id, customer_name, phone, mayon_date, barat_date,
                valima_date, total_price, status, notes, source_invoice_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (
                package_id,
                package["name"],
                customer_id,
                customer_name,
                phone,
                mayon_date or None,
                barat_date or None,
                valima_date or None,
                package["price"],
                notes,
                invoice_id,
                now_str(),
            ),
        )
        contract_id = int(cur.lastrowid)
        sessions = conn.execute(
            "SELECT * FROM package_items WHERE package_id = ? ORDER BY sort_order",
            (package_id,),
        ).fetchall()
        for session in sessions:
            conn.execute(
                """INSERT INTO groom_sessions (contract_id, name, total_qty, used_qty, sort_order)
                   VALUES (?, ?, ?, 0, ?)""",
                (contract_id, session["name"], session["qty"], session["sort_order"]),
            )
        if paid_amount > 0:
            conn.execute(
                """INSERT INTO groom_payments (contract_id, amount, payment_mode, invoice_id, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (contract_id, paid_amount, payment_mode, invoice_id, now_str()),
            )
        return contract_id

    def _next_invoice_no(self, conn, created: str) -> str:
        day = created[:10].replace("-", "")
        prefix = f"CV-{day}-"
        row = conn.execute(
            "SELECT invoice_no FROM invoices WHERE invoice_no LIKE ? ORDER BY invoice_no DESC LIMIT 1",
            (prefix + "%",),
        ).fetchone()
        number = 1
        if row:
            try:
                number = int(row["invoice_no"].rsplit("-", 1)[-1]) + 1
            except ValueError:
                number = 1
        return f"{prefix}{number:04d}"

    def get_invoice(self, invoice_id: int) -> dict | None:
        invoice = self.q1("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        if not invoice:
            return None
        invoice["items"] = self.q(
            "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id",
            (invoice_id,),
        )
        return invoice

    def list_invoices(self, start: str, end: str, include_void: bool = True) -> list[dict]:
        if include_void:
            return self.q(
                """SELECT * FROM invoices
                   WHERE date(created_at) BETWEEN ? AND ?
                   ORDER BY created_at DESC, id DESC""",
                (start, end),
            )
        return self.q(
            """SELECT * FROM invoices
               WHERE status != 'void' AND date(created_at) BETWEEN ? AND ?
               ORDER BY created_at DESC, id DESC""",
            (start, end),
        )

    def invoice_groom_links(self, invoice_id: int) -> list[dict]:
        return self.q(
            """SELECT gp.contract_id, gp.amount, c.package_name, c.customer_name
               FROM groom_payments gp
               JOIN groom_contracts c ON c.id = gp.contract_id
               WHERE gp.invoice_id = ?""",
            (invoice_id,),
        )

    def void_invoice(self, invoice_id: int, username: str) -> None:
        with self.connect() as conn:
            invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if invoice is None:
                raise ValueError("Bill was not found.")
            if invoice["status"] == "void":
                raise ValueError("This bill is already void.")
            conn.execute(
                "UPDATE invoices SET status = 'void', voided_at = ?, voided_by = ? WHERE id = ?",
                (now_str(), username, invoice_id),
            )
            if invoice["customer_id"]:
                points = int(float(invoice["total"]) // 100)
                conn.execute(
                    """UPDATE customers
                       SET loyalty_points = MAX(0, loyalty_points - ?),
                           visits = MAX(0, visits - 1)
                       WHERE id = ?""",
                    (points, invoice["customer_id"]),
                )
            conn.execute(
                "UPDATE appointments SET status = 'Waiting', invoice_id = NULL WHERE invoice_id = ?",
                (invoice_id,),
            )

    # --------------------------------------------------------------- appointments
    def list_appointments(self, appt_date: str, search: str = "") -> list[dict]:
        like = f"%{search.strip()}%"
        return self.q(
            """SELECT * FROM appointments
               WHERE appt_date = ? AND (? = '' OR customer_name LIKE ? OR phone LIKE ? OR token LIKE ?)
               ORDER BY is_walkin DESC, appt_time, id""",
            (appt_date, search.strip(), like, like, like),
        )

    def get_appointment(self, appointment_id: int) -> dict | None:
        return self.q1("SELECT * FROM appointments WHERE id = ?", (appointment_id,))

    def save_appointment(self, data: dict) -> int:
        name = data["customer_name"].strip()
        if not name:
            raise ValueError("Client name is required.")
        if not data.get("service_name"):
            raise ValueError("Choose a service or deal.")
        is_walkin = 1 if data.get("is_walkin") else 0
        with self.connect() as conn:
            staff_name = ""
            if data.get("staff_id"):
                staff = conn.execute("SELECT name FROM staff WHERE id = ?", (data["staff_id"],)).fetchone()
                staff_name = staff["name"] if staff else ""
            customer_id = data.get("customer_id")
            if data.get("id"):
                conn.execute(
                    """UPDATE appointments
                       SET customer_id = ?, customer_name = ?, phone = ?, staff_id = ?, staff_name = ?,
                           service_id = ?, package_id = ?, service_name = ?, appt_date = ?, appt_time = ?,
                           chair = ?, notes = ?, is_walkin = ?
                       WHERE id = ?""",
                    (
                        customer_id,
                        name,
                        (data.get("phone") or "").strip(),
                        data.get("staff_id"),
                        staff_name,
                        data.get("service_id"),
                        data.get("package_id"),
                        data["service_name"],
                        data["appt_date"],
                        data["appt_time"],
                        data.get("chair") or "Any",
                        (data.get("notes") or "").strip(),
                        is_walkin,
                        data["id"],
                    ),
                )
                return int(data["id"])
            token = self._next_token(conn, data["appt_date"], bool(is_walkin))
            cur = conn.execute(
                """INSERT INTO appointments
                   (token, customer_id, customer_name, phone, staff_id, staff_name, service_id, package_id,
                    service_name, appt_date, appt_time, chair, status, is_walkin, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Waiting', ?, ?, ?)""",
                (
                    token,
                    customer_id,
                    name,
                    (data.get("phone") or "").strip(),
                    data.get("staff_id"),
                    staff_name,
                    data.get("service_id"),
                    data.get("package_id"),
                    data["service_name"],
                    data["appt_date"],
                    data["appt_time"],
                    data.get("chair") or "Any",
                    is_walkin,
                    (data.get("notes") or "").strip(),
                    now_str(),
                ),
            )
            return int(cur.lastrowid)

    def set_appointment_status(self, appointment_id: int, status: str) -> None:
        if status not in ("Waiting", "In Chair", "Completed", "Cancelled"):
            raise ValueError("Unknown appointment status.")
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
            if row is None:
                raise ValueError("Appointment was not found.")
            if row["status"] == "Cancelled" and status != "Cancelled":
                raise ValueError("This appointment is cancelled.")
            conn.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))

    def _next_token(self, conn, appt_date: str, walkin: bool) -> str:
        prefix = "W" if walkin else "A"
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM appointments WHERE appt_date = ? AND is_walkin = ?",
            (appt_date, 1 if walkin else 0),
        ).fetchone()["c"]
        return f"{prefix}-{count + 1:03d}"

    # ---------------------------------------------------------------------- groom
    def active_groom_contract(self, customer_id: int, package_id: int) -> dict | None:
        return self.q1(
            """SELECT * FROM groom_contracts
               WHERE customer_id = ? AND package_id = ? AND status = 'active' LIMIT 1""",
            (customer_id, package_id),
        )

    def list_contracts(self, status: str = "", search: str = "") -> list[dict]:
        like = f"%{search.strip()}%"
        rows = self.q(
            """SELECT c.*,
                      COALESCE(p.paid, 0) AS paid,
                      COALESCE(s.used_qty, 0) AS used_qty,
                      COALESCE(s.total_qty, 0) AS total_qty
               FROM groom_contracts c
               LEFT JOIN (
                   SELECT gp.contract_id, SUM(gp.amount) AS paid
                   FROM groom_payments gp
                   LEFT JOIN invoices i ON i.id = gp.invoice_id
                   WHERE i.id IS NULL OR i.status != 'void'
                   GROUP BY gp.contract_id
               ) p ON p.contract_id = c.id
               LEFT JOIN (
                   SELECT contract_id, SUM(used_qty) AS used_qty, SUM(total_qty) AS total_qty
                   FROM groom_sessions GROUP BY contract_id
               ) s ON s.contract_id = c.id
               WHERE (? = '' OR c.status = ?)
                 AND (? = '' OR c.customer_name LIKE ? OR c.phone LIKE ? OR c.package_name LIKE ?)
               ORDER BY CASE c.status WHEN 'active' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END, c.id DESC""",
            (status, status, search.strip(), like, like, like),
        )
        for row in rows:
            row["balance"] = round_money(row["total_price"] - row["paid"])
        return rows

    def get_contract(self, contract_id: int) -> dict | None:
        rows = self.list_contracts()
        head = next((row for row in rows if row["id"] == contract_id), None)
        if head is None:
            return None
        head["sessions"] = self.q(
            "SELECT * FROM groom_sessions WHERE contract_id = ? ORDER BY sort_order, id",
            (contract_id,),
        )
        head["payments"] = self.q(
            """SELECT gp.*, i.invoice_no, i.status AS invoice_status
               FROM groom_payments gp
               LEFT JOIN invoices i ON i.id = gp.invoice_id
               WHERE gp.contract_id = ?
               ORDER BY gp.id""",
            (contract_id,),
        )
        head["visits"] = self.q(
            """SELECT v.*, s.name AS session_name
               FROM groom_visits v
               JOIN groom_sessions s ON s.id = v.session_id
               WHERE v.contract_id = ?
               ORDER BY v.id DESC""",
            (contract_id,),
        )
        return head

    def enroll_groom(self, data: dict) -> dict:
        package = self.get_package(int(data["package_id"]))
        if package is None or not package["is_groom"]:
            raise ValueError("Choose a Signature Groom package.")
        name = data["customer_name"].strip()
        phone = data["phone"].strip()
        advance = round_money(data.get("advance") or 0)
        if advance < 0:
            raise ValueError("Advance cannot be negative.")
        if advance - float(package["price"]) > 0.01:
            raise ValueError("Advance is higher than the package price.")
        customer = self.upsert_customer(name, phone, data.get("notes") or "")
        existing = self.active_groom_contract(customer["id"], package["id"])
        if existing:
            raise ValueError(f"{customer['name']} already has an active {package['name']}.")
        mode = data.get("payment_mode") or PAY_CASH
        with self.connect() as conn:
            invoice_id = None
            if advance > 0:
                invoice_id = self._simple_invoice_tx(
                    conn,
                    customer=customer,
                    amount=advance,
                    mode=mode,
                    origin="groom_advance",
                    line_name=f"Advance — {package['name']}",
                    username=data.get("username") or "",
                    ref_id=package["id"],
                )
            contract_id = self._create_contract_tx(
                conn,
                package_id=package["id"],
                customer_id=customer["id"],
                customer_name=customer["name"],
                phone=customer["phone"],
                paid_amount=advance,
                payment_mode=mode,
                invoice_id=invoice_id or 0,
                notes=(data.get("notes") or "").strip(),
                mayon_date=data.get("mayon_date") or "",
                barat_date=data.get("barat_date") or "",
                valima_date=data.get("valima_date") or "",
            )
        contract = self.get_contract(int(contract_id))
        if contract is None:
            raise ValueError("Package was saved but could not be opened.")
        return contract

    def add_groom_payment(self, contract_id: int, amount: float, mode: str, username: str) -> dict:
        amount = round_money(amount)
        if amount <= 0:
            raise ValueError("Enter a payment amount.")
        contract = self.get_contract(contract_id)
        if contract is None:
            raise ValueError("Package was not found.")
        if contract["status"] == "cancelled":
            raise ValueError("This package is cancelled.")
        if amount - float(contract["balance"]) > 0.05:
            raise ValueError(f"Balance remaining is {money(contract['balance'])}.")
        customer = None
        if contract["customer_id"]:
            customer = self.get_customer(contract["customer_id"])
        if customer is None:
            customer = self.upsert_customer(contract["customer_name"], contract["phone"] or "0000000")
        with self.connect() as conn:
            invoice_id = self._simple_invoice_tx(
                conn,
                customer=customer,
                amount=amount,
                mode=mode,
                origin="groom_payment",
                line_name=f"Payment — {contract['package_name']}",
                username=username,
                ref_id=contract["package_id"],
            )
            conn.execute(
                """INSERT INTO groom_payments (contract_id, amount, payment_mode, invoice_id, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (contract_id, amount, mode, invoice_id, now_str()),
            )
        updated = self.get_contract(contract_id)
        if updated is None:
            raise ValueError("Payment was saved but the package could not be read back.")
        return updated

    def _simple_invoice_tx(self, conn, customer, amount, mode, origin, line_name, username, ref_id) -> int:
        if mode == PAY_SPLIT:
            raise ValueError("Record a single payment mode for package collections.")
        cash = amount if mode == PAY_CASH else 0
        card = amount if mode == PAY_CARD else 0
        transfer = amount if mode == PAY_TRANSFER else 0
        created = now_str()
        invoice_no = self._next_invoice_no(conn, created)
        cur = conn.execute(
            """INSERT INTO invoices (
                   invoice_no, customer_id, customer_name, customer_phone, subtotal, discount_type,
                   discount_value, discount_amount, tax_pct, tax_amount, total, payment_mode,
                   cash_amount, card_amount, transfer_amount, cash_tendered, change_due, status,
                   origin, notes, created_by, created_at
               ) VALUES (?, ?, ?, ?, ?, 'none', 0, 0, 0, 0, ?, ?, ?, ?, ?, ?, 0, 'paid', ?, '', ?, ?)""",
            (
                invoice_no,
                customer["id"],
                customer["name"],
                customer["phone"],
                amount,
                amount,
                mode,
                cash,
                card,
                transfer,
                amount if mode == PAY_CASH else amount,
                origin,
                username,
                created,
            ),
        )
        invoice_id = int(cur.lastrowid)
        conn.execute(
            """INSERT INTO invoice_items
               (invoice_id, kind, ref_id, name, qty, unit_price, line_total, staff_id, staff_name, detail)
               VALUES (?, 'payment', ?, ?, 1, ?, ?, NULL, '', '')""",
            (invoice_id, ref_id, line_name, amount, amount),
        )
        points = int(amount // 100)
        conn.execute(
            "UPDATE customers SET loyalty_points = loyalty_points + ?, visits = visits + 1 WHERE id = ?",
            (points, customer["id"]),
        )
        return invoice_id

    def use_groom_session(self, session_id: int, notes: str = "") -> dict:
        with self.connect() as conn:
            session = conn.execute("SELECT * FROM groom_sessions WHERE id = ?", (session_id,)).fetchone()
            if session is None:
                raise ValueError("Session was not found.")
            if session["used_qty"] >= session["total_qty"]:
                raise ValueError(f"{session['name']} is already fully used.")
            contract = conn.execute(
                "SELECT * FROM groom_contracts WHERE id = ?",
                (session["contract_id"],),
            ).fetchone()
            if contract["status"] == "cancelled":
                raise ValueError("This package is cancelled.")
            conn.execute("UPDATE groom_sessions SET used_qty = used_qty + 1 WHERE id = ?", (session_id,))
            conn.execute(
                "INSERT INTO groom_visits (contract_id, session_id, visit_date, notes) VALUES (?, ?, ?, ?)",
                (session["contract_id"], session_id, now_str(), notes.strip()),
            )
            totals = conn.execute(
                "SELECT SUM(used_qty) AS used, SUM(total_qty) AS total FROM groom_sessions WHERE contract_id = ?",
                (session["contract_id"],),
            ).fetchone()
            if totals["used"] >= totals["total"]:
                conn.execute(
                    "UPDATE groom_contracts SET status = 'completed' WHERE id = ?",
                    (session["contract_id"],),
                )
            elif contract["status"] == "completed":
                conn.execute(
                    "UPDATE groom_contracts SET status = 'active' WHERE id = ?",
                    (session["contract_id"],),
                )
            contract_id = session["contract_id"]
        updated = self.get_contract(contract_id)
        if updated is None:
            raise ValueError("Visit was saved but the package could not be read back.")
        return updated

    def undo_groom_session(self, session_id: int) -> dict:
        with self.connect() as conn:
            session = conn.execute("SELECT * FROM groom_sessions WHERE id = ?", (session_id,)).fetchone()
            if session is None:
                raise ValueError("Session was not found.")
            if session["used_qty"] <= 0:
                raise ValueError("Nothing to undo on this session.")
            conn.execute("UPDATE groom_sessions SET used_qty = used_qty - 1 WHERE id = ?", (session_id,))
            last = conn.execute(
                "SELECT id FROM groom_visits WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if last:
                conn.execute("DELETE FROM groom_visits WHERE id = ?", (last["id"],))
            conn.execute(
                "UPDATE groom_contracts SET status = 'active' WHERE id = ? AND status = 'completed'",
                (session["contract_id"],),
            )
            contract_id = session["contract_id"]
        updated = self.get_contract(contract_id)
        if updated is None:
            raise ValueError("Undo failed to reload the package.")
        return updated

    def update_contract_meta(self, contract_id: int, mayon: str, barat: str, valima: str, notes: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE groom_contracts
                   SET mayon_date = ?, barat_date = ?, valima_date = ?, notes = ?
                   WHERE id = ?""",
                (mayon or None, barat or None, valima or None, notes.strip(), contract_id),
            )

    def set_contract_status(self, contract_id: int, status: str) -> None:
        if status not in ("active", "completed", "cancelled"):
            raise ValueError("Unknown package status.")
        with self.connect() as conn:
            conn.execute("UPDATE groom_contracts SET status = ? WHERE id = ?", (status, contract_id))

    # ------------------------------------------------------------------- expenses
    def list_expenses(self, start: str, end: str) -> list[dict]:
        return self.q(
            "SELECT * FROM expenses WHERE exp_date BETWEEN ? AND ? ORDER BY exp_date DESC, id DESC",
            (start, end),
        )

    def save_expense(self, data: dict) -> int:
        category = (data.get("category") or "").strip()
        if not category:
            raise ValueError("Choose an expense category.")
        amount = round_money(data.get("amount") or 0)
        if amount <= 0:
            raise ValueError("Enter an amount greater than zero.")
        with self.connect() as conn:
            if data.get("id"):
                conn.execute(
                    """UPDATE expenses
                       SET exp_date = ?, category = ?, description = ?, amount = ?, payment_mode = ?, expense_type = ?
                       WHERE id = ?""",
                    (
                        data["exp_date"],
                        category,
                        (data.get("description") or "").strip(),
                        amount,
                        data.get("payment_mode") or PAY_CASH,
                        self._expense_type(data),
                        data["id"],
                    ),
                )
                return int(data["id"])
            cur = conn.execute(
                """INSERT INTO expenses (exp_date, category, description, amount, payment_mode, expense_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["exp_date"],
                    category,
                    (data.get("description") or "").strip(),
                    amount,
                    data.get("payment_mode") or PAY_CASH,
                    self._expense_type(data),
                    now_str(),
                ),
            )
            return int(cur.lastrowid)

    def _expense_type(self, data: dict) -> str:
        kind = (data.get("expense_type") or "daily").strip().lower()
        if kind not in ("daily", "monthly"):
            raise ValueError("Choose Daily Expense or Monthly Expense.")
        return kind

    def delete_expense(self, expense_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    def list_products(self, active_only: bool = False) -> list[dict]:
        if active_only:
            return self.q("SELECT * FROM products WHERE active = 1 ORDER BY name")
        return self.q("SELECT * FROM products ORDER BY active DESC, name")

    def save_product(self, data: dict) -> int:
        name = data["name"].strip()
        if not name:
            raise ValueError("Product name is required.")
        qty = float(data.get("qty") or 0)
        reorder = float(data.get("reorder_level") or 0)
        if qty < 0 or reorder < 0:
            raise ValueError("Quantity cannot be negative.")
        with self.connect() as conn:
            if data.get("id"):
                current = conn.execute("SELECT qty FROM products WHERE id = ?", (data["id"],)).fetchone()
                if current is None:
                    raise ValueError("Product was not found.")
                conn.execute(
                    """UPDATE products
                       SET name = ?, category = ?, unit = ?, reorder_level = ?, cost_price = ?, sell_price = ?, active = ?
                       WHERE id = ?""",
                    (
                        name,
                        (data.get("category") or "").strip(),
                        (data.get("unit") or "piece").strip(),
                        reorder,
                        round_money(data.get("cost_price") or 0),
                        round_money(data.get("sell_price") or 0),
                        1 if data.get("active", True) else 0,
                        data["id"],
                    ),
                )
                return int(data["id"])
            cur = conn.execute(
                """INSERT INTO products
                   (name, category, unit, qty, reorder_level, cost_price, sell_price, active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    (data.get("category") or "").strip(),
                    (data.get("unit") or "piece").strip(),
                    qty,
                    reorder,
                    round_money(data.get("cost_price") or 0),
                    round_money(data.get("sell_price") or 0),
                    1 if data.get("active", True) else 0,
                ),
            )
            product_id = int(cur.lastrowid)
            if qty:
                conn.execute(
                    """INSERT INTO stock_moves (product_id, qty_change, reason, notes, created_at)
                       VALUES (?, ?, 'Purchase', 'Opening quantity', ?)""",
                    (product_id, qty, now_str()),
                )
            return product_id

    def set_product_qty(self, product_id: int, new_qty: float, reason: str, notes: str = "") -> None:
        new_qty = float(new_qty)
        if new_qty < 0:
            raise ValueError("Stock cannot go below zero.")
        with self.connect() as conn:
            row = conn.execute("SELECT qty FROM products WHERE id = ?", (product_id,)).fetchone()
            if row is None:
                raise ValueError("Product was not found.")
            delta = new_qty - float(row["qty"])
            conn.execute("UPDATE products SET qty = ? WHERE id = ?", (new_qty, product_id))
            if abs(delta) > 1e-9:
                conn.execute(
                    """INSERT INTO stock_moves (product_id, qty_change, reason, notes, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (product_id, delta, reason, notes.strip(), now_str()),
                )

    def set_product_active(self, product_id: int, active: bool) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE products SET active = ? WHERE id = ?", (1 if active else 0, product_id))

    def low_stock(self) -> list[dict]:
        return self.q(
            "SELECT * FROM products WHERE active = 1 AND qty <= reorder_level ORDER BY qty, name"
        )

    # -------------------------------------------------------------------- payroll
    def list_adjustments(self, start: str, end: str, staff_id: int | None = None) -> list[dict]:
        return self.q(
            """SELECT a.*, s.name AS staff_name
               FROM adjustments a
               JOIN staff s ON s.id = a.staff_id
               WHERE a.adj_date BETWEEN ? AND ?
                 AND (? IS NULL OR a.staff_id = ?)
               ORDER BY a.adj_date DESC, a.id DESC""",
            (start, end, staff_id, staff_id),
        )

    def save_adjustment(self, data: dict) -> int:
        amount = round_money(data.get("amount") or 0)
        if amount <= 0:
            raise ValueError("Enter an amount greater than zero.")
        if data.get("kind") not in ("Advance", "Deduction", "Tip", "Bonus"):
            raise ValueError("Choose an adjustment type.")
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO adjustments (staff_id, adj_date, kind, amount, notes, payment_mode, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["staff_id"],
                    data["adj_date"],
                    data["kind"],
                    amount,
                    (data.get("notes") or "").strip(),
                    data.get("payment_mode") or PAY_CASH,
                    now_str(),
                ),
            )
            return int(cur.lastrowid)

    def delete_adjustment(self, adjustment_id: int) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM adjustments WHERE id = ?", (adjustment_id,)).fetchone()
            if row is None:
                return
            paid = conn.execute(
                """SELECT id FROM payroll
                   WHERE staff_id = ? AND status = 'paid' AND period_start <= ? AND period_end >= ?""",
                (row["staff_id"], row["adj_date"], row["adj_date"]),
            ).fetchone()
            if paid:
                raise ValueError("This adjustment is already inside a paid salary slip.")
            conn.execute("DELETE FROM adjustments WHERE id = ?", (adjustment_id,))

    def build_payroll(self, start: str, end: str) -> list[dict]:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
        if end_d < start_d:
            raise ValueError("The end date is before the start date.")
        period_days = (end_d - start_d).days + 1
        staff_rows = self.list_staff(active_only=False)
        sales = self._commission_bases(start, end)
        attendance = self.q(
            "SELECT * FROM attendance WHERE att_date BETWEEN ? AND ?",
            (start, end),
        )
        adjustments = self.list_adjustments(start, end)
        att_by_staff: dict[int, list] = {}
        for row in attendance:
            att_by_staff.setdefault(row["staff_id"], []).append(row)
        adj_by_staff: dict[int, list] = {}
        for row in adjustments:
            adj_by_staff.setdefault(row["staff_id"], []).append(row)
        with self.connect() as conn:
            existing = {
                row["staff_id"]: row
                for row in conn.execute(
                    "SELECT * FROM payroll WHERE period_start = ? AND period_end = ?",
                    (start, end),
                )
            }
            for member in staff_rows:
                paid_row = existing.get(member["id"])
                if paid_row and paid_row["status"] == "paid":
                    continue
                relevant = member["active"] or member["id"] in sales or member["id"] in att_by_staff or member["id"] in adj_by_staff
                if not relevant:
                    conn.execute(
                        "DELETE FROM payroll WHERE staff_id = ? AND period_start = ? AND period_end = ? AND status != 'paid'",
                        (member["id"], start, end),
                    )
                    continue
                present_units = 0.0
                rows = att_by_staff.get(member["id"], [])
                for row in rows:
                    if row["status"] in ("Present", "Leave"):
                        present_units += 1
                    elif row["status"] == "Half-Day":
                        present_units += 0.5
                if pays_base(member["salary_type"]):
                    if rows:
                        ratio = present_units / period_days if period_days else 0
                        base = round_money(member["base_salary"] * ratio)
                        note = f"Base pro-rated {present_units:g}/{period_days} days"
                    else:
                        base = round_money(member["base_salary"])
                        note = "No attendance logged; full base applied"
                else:
                    base = 0.0
                    note = "Commission only"
                commission = 0.0
                if pays_commission(member["salary_type"]):
                    commission = round_money(sales.get(member["id"], 0) * float(member["commission_pct"]) / 100.0)
                advances = deductions = tips = bonuses = 0.0
                for adj in adj_by_staff.get(member["id"], []):
                    if adj["kind"] == "Advance":
                        advances += adj["amount"]
                    elif adj["kind"] == "Deduction":
                        deductions += adj["amount"]
                    elif adj["kind"] == "Tip":
                        tips += adj["amount"]
                    elif adj["kind"] == "Bonus":
                        bonuses += adj["amount"]
                net = round_money(base + commission + tips + bonuses - advances - deductions)
                conn.execute(
                    "DELETE FROM payroll WHERE staff_id = ? AND period_start = ? AND period_end = ? AND status != 'paid'",
                    (member["id"], start, end),
                )
                conn.execute(
                    """INSERT INTO payroll
                       (staff_id, staff_name, period_start, period_end, base_salary, commission, advances,
                        deductions, tips, bonuses, net_payable, present_units, period_days, note, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid')""",
                    (
                        member["id"],
                        member["name"],
                        start,
                        end,
                        base,
                        commission,
                        round_money(advances),
                        round_money(deductions),
                        round_money(tips),
                        round_money(bonuses),
                        net,
                        present_units,
                        period_days,
                        note,
                    ),
                )
        return self.list_payroll(start, end)

    def _commission_bases(self, start: str, end: str) -> dict[int, float]:
        rows = self.q(
            """SELECT i.id, i.subtotal, i.discount_amount, ii.staff_id, ii.line_total
               FROM invoice_items ii
               JOIN invoices i ON i.id = ii.invoice_id
               WHERE i.status != 'void'
                 AND ii.staff_id IS NOT NULL
                 AND date(i.created_at) BETWEEN ? AND ?""",
            (start, end),
        )
        totals: dict[int, float] = {}
        for row in rows:
            subtotal = float(row["subtotal"] or 0)
            ratio = 1.0
            if subtotal > 0:
                ratio = max(0.0, (subtotal - float(row["discount_amount"] or 0)) / subtotal)
            totals[row["staff_id"]] = totals.get(row["staff_id"], 0) + float(row["line_total"]) * ratio
        return totals

    def list_payroll_history(self) -> list[dict]:
        return self.q(
            """SELECT p.*, s.role
               FROM payroll p
               JOIN staff s ON s.id = p.staff_id
               ORDER BY p.period_end DESC, p.period_start DESC, p.staff_name"""
        )

    def list_all_adjustments(self) -> list[dict]:
        return self.q(
            """SELECT a.*, s.name AS staff_name
               FROM adjustments a
               JOIN staff s ON s.id = a.staff_id
               ORDER BY a.adj_date DESC, a.id DESC"""
        )

    def list_payroll(self, start: str, end: str) -> list[dict]:
        return self.q(
            """SELECT p.*, s.role, s.salary_type, s.commission_pct
               FROM payroll p
               JOIN staff s ON s.id = p.staff_id
               WHERE p.period_start = ? AND p.period_end = ?
               ORDER BY p.staff_name""",
            (start, end),
        )

    def get_payroll(self, payroll_id: int) -> dict | None:
        return self.q1(
            """SELECT p.*, s.role, s.salary_type, s.commission_pct, s.phone
               FROM payroll p JOIN staff s ON s.id = p.staff_id
               WHERE p.id = ?""",
            (payroll_id,),
        )

    def mark_payroll_paid(self, payroll_id: int) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM payroll WHERE id = ?", (payroll_id,)).fetchone()
            if row is None:
                raise ValueError("Salary row was not found. Calculate the period first.")
            if row["status"] == "paid":
                raise ValueError("This salary is already marked paid.")
            conn.execute(
                "UPDATE payroll SET status = 'paid', paid_at = ? WHERE id = ?",
                (now_str(), payroll_id),
            )

    # -------------------------------------------------------------------- drawer
    def drawer_snapshot(self, day: str) -> dict:
        stored = self.q1("SELECT * FROM drawer_days WHERE business_date = ?", (day,))
        opening = float(stored["opening_balance"] or 0) if stored else 0.0
        sales = self.q1(
            """SELECT COALESCE(SUM(cash_amount), 0) AS cash,
                      COALESCE(SUM(card_amount), 0) AS card,
                      COALESCE(SUM(transfer_amount), 0) AS transfer
               FROM invoices
               WHERE status != 'void' AND date(created_at) = ?""",
            (day,),
        ) or {"cash": 0, "card": 0, "transfer": 0}
        cash_sales = float(sales["cash"] or 0)
        online_sales = float(sales["card"] or 0) + float(sales["transfer"] or 0)
        daily_cash = monthly_cash = daily_other = monthly_other = 0.0
        for row in self.q("SELECT * FROM expenses WHERE exp_date = ?", (day,)):
            amount = float(row["amount"] or 0)
            cash = (row["payment_mode"] or "") == PAY_CASH
            monthly = (row["expense_type"] or "daily") == "monthly"
            if monthly and cash:
                monthly_cash += amount
            elif monthly:
                monthly_other += amount
            elif cash:
                daily_cash += amount
            else:
                daily_other += amount
        advances = self.q(
            """SELECT a.*, s.name AS staff_name
               FROM adjustments a
               JOIN staff s ON s.id = a.staff_id
               WHERE a.adj_date = ? AND a.kind = 'Advance'
               ORDER BY a.id""",
            (day,),
        )
        cash_advances = 0.0
        advance_rows = []
        for row in advances:
            amount = float(row["amount"] or 0)
            cash = (row["payment_mode"] or PAY_CASH) == PAY_CASH
            if cash:
                cash_advances += amount
            advance_rows.append(
                {
                    "staff_name": row["staff_name"],
                    "amount": amount,
                    "payment_mode": row["payment_mode"] or PAY_CASH,
                    "cash": cash,
                    "notes": row["notes"] or "",
                }
            )
        cash_expenses = round_money(daily_cash + monthly_cash)
        cash_out = round_money(cash_expenses + cash_advances)
        expected = round_money(opening + cash_sales - cash_expenses - cash_advances)
        actual = None if not stored or stored["actual_cash"] is None else float(stored["actual_cash"])
        difference = None if actual is None else round_money(actual - expected)
        return {
            "date": day,
            "opening": round_money(opening),
            "opened": bool(stored and stored["opened_at"]),
            "closed": bool(stored and stored["closed_at"]),
            "closed_at": stored["closed_at"] if stored else "",
            "closed_by": stored["closed_by"] if stored else "",
            "note": stored["note"] if stored else "",
            "cash_sales": round_money(cash_sales),
            "online_sales": round_money(online_sales),
            "daily_cash_expenses": round_money(daily_cash),
            "monthly_cash_expenses": round_money(monthly_cash),
            "daily_other_expenses": round_money(daily_other),
            "monthly_other_expenses": round_money(monthly_other),
            "cash_expenses": cash_expenses,
            "cash_advances": round_money(cash_advances),
            "cash_payments": cash_out,
            "advances": advance_rows,
            "staff": self.staff_day(day),
            "expected": expected,
            "actual": actual,
            "difference": difference,
            "variance": self._variance(difference),
        }

    def staff_day(self, day: str) -> list[dict]:
        bases = self._commission_bases(day, day)
        advance_by_staff: dict[int, float] = {}
        for row in self.q(
            "SELECT staff_id, amount, payment_mode FROM adjustments WHERE adj_date = ? AND kind = 'Advance'",
            (day,),
        ):
            advance_by_staff[row["staff_id"]] = advance_by_staff.get(row["staff_id"], 0) + float(row["amount"] or 0)
        rows = []
        for member in self.list_staff(active_only=False):
            work = round_money(bases.get(member["id"], 0))
            taken = round_money(advance_by_staff.get(member["id"], 0))
            if work <= 0 and taken <= 0:
                continue
            percent = float(member["commission_pct"] or 0) if pays_commission(member["salary_type"]) else 0.0
            commission = round_money(work * percent / 100.0) if percent else 0.0
            rows.append(
                {
                    "name": member["name"],
                    "work": work,
                    "percent": percent,
                    "commission": commission,
                    "advance": taken,
                    "salary_type": member["salary_type"],
                }
            )
        rows.sort(key=lambda item: item["work"], reverse=True)
        return rows

    def _variance(self, difference) -> str:
        if difference is None:
            return "open"
        if abs(difference) < 0.5:
            return "match"
        return "over" if difference > 0 else "short"

    def previous_drawer(self, day: str) -> dict:
        previous = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        snap = self.drawer_snapshot(previous)
        counted = snap["actual"]
        carried = counted if counted is not None else snap["expected"]
        return {
            "date": previous,
            "amount": round_money(carried),
            "counted": counted,
            "expected": snap["expected"],
            "closed": snap["closed"],
        }

    def set_opening_balance(self, day: str, amount: float, username: str = "") -> dict:
        amount = round_money(amount)
        if amount < 0:
            raise ValueError("Opening balance cannot be negative.")
        current = self.q1("SELECT * FROM drawer_days WHERE business_date = ?", (day,))
        if current and current["closed_at"]:
            raise ValueError("This day is already closed. The opening balance is locked.")
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO drawer_days (business_date, opening_balance, opened_at, closed_by)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(business_date) DO UPDATE SET
                       opening_balance = excluded.opening_balance,
                       opened_at = COALESCE(drawer_days.opened_at, excluded.opened_at)""",
                (day, amount, now_str(), username),
            )
        return self.drawer_snapshot(day)

    def close_drawer(self, day: str, actual: float, username: str = "", note: str = "") -> dict:
        actual = round_money(actual)
        if actual < 0:
            raise ValueError("Counted cash cannot be negative.")
        current = self.q1("SELECT * FROM drawer_days WHERE business_date = ?", (day,))
        if current is None or not current["opened_at"]:
            raise ValueError("Enter the opening cash balance before closing the drawer.")
        if current["closed_at"]:
            raise ValueError("This day is already closed.")
        snap = self.drawer_snapshot(day)
        difference = round_money(actual - snap["expected"])
        with self.connect() as conn:
            conn.execute(
                """UPDATE drawer_days
                   SET closed_at = ?, actual_cash = ?, expected_cash = ?, difference = ?, note = ?, closed_by = ?
                   WHERE business_date = ?""",
                (now_str(), actual, snap["expected"], difference, note.strip(), username, day),
            )
        return self.drawer_snapshot(day)

    # -------------------------------------------------------------------- reports
    def dashboard(self, days: int = 7) -> dict:
        today = date.today()
        start = today - timedelta(days=days - 1)
        start_s, today_s = start.isoformat(), today.isoformat()
        kpis = self._day_kpis(today_s)
        grouped = {
            row["d"]: row["total"]
            for row in self.q(
                """SELECT date(created_at) AS d, COALESCE(SUM(total), 0) AS total
                   FROM invoices
                   WHERE status != 'void' AND date(created_at) BETWEEN ? AND ?
                   GROUP BY date(created_at)""",
                (start_s, today_s),
            )
        }
        series = []
        cursor = start
        while cursor <= today:
            key = cursor.isoformat()
            series.append({"date": key, "total": float(grouped.get(key, 0) or 0)})
            cursor += timedelta(days=1)
        top_services = self._top_items(start_s, today_s, "service")
        top_deals = self._top_items(start_s, today_s, "package")
        recent = self.q(
            "SELECT * FROM invoices ORDER BY created_at DESC, id DESC LIMIT 8"
        )
        return {
            "kpis": kpis,
            "series": series,
            "top_services": top_services,
            "top_deals": top_deals,
            "recent": recent,
            "low_stock": self.low_stock(),
        }

    def _day_kpis(self, day: str) -> dict:
        sales = self.q1(
            """SELECT COUNT(*) AS bills,
                      COALESCE(SUM(total), 0) AS revenue,
                      COALESCE(SUM(cash_amount), 0) AS cash_in,
                      COUNT(DISTINCT customer_id) AS named
               FROM invoices
               WHERE status != 'void' AND date(created_at) = ?""",
            (day,),
        ) or {"bills": 0, "revenue": 0, "cash_in": 0, "named": 0}
        walkins = self.q1(
            """SELECT COUNT(*) AS c FROM invoices
               WHERE status != 'void' AND customer_id IS NULL AND date(created_at) = ?""",
            (day,),
        )["c"]
        expenses = self.q1(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE exp_date = ?",
            (day,),
        )["total"]
        drawer = self.drawer_snapshot(day)
        active = self.q1("SELECT COUNT(*) AS c FROM staff WHERE active = 1")["c"]
        online_expenses = round_money(drawer["daily_other_expenses"] + drawer["monthly_other_expenses"])
        return {
            "revenue": float(sales["revenue"] or 0),
            "bills": int(sales["bills"] or 0),
            "clients": int(sales["named"] or 0) + int(walkins or 0),
            "active_staff": int(active or 0),
            "expenses": float(expenses or 0),
            "cash_out": drawer["cash_payments"],
            "online_expenses": online_expenses,
            "drawer": drawer["expected"],
            "drawer_opened": drawer["opened"],
            "drawer_closed": drawer["closed"],
            "drawer_actual": drawer["actual"],
            "drawer_state": drawer["variance"],
        }

    def _top_items(self, start: str, end: str, kind: str, limit: int = 5) -> list[dict]:
        return self.q(
            """SELECT ii.name, SUM(ii.qty) AS qty, SUM(ii.line_total) AS revenue
               FROM invoice_items ii
               JOIN invoices i ON i.id = ii.invoice_id
               WHERE i.status != 'void' AND ii.kind = ?
                 AND date(i.created_at) BETWEEN ? AND ?
               GROUP BY ii.name
               ORDER BY revenue DESC
               LIMIT ?""",
            (kind, start, end, limit),
        )

    def run_report(self, kind: str, start: str, end: str) -> dict:
        if kind == "sales":
            return self._report_sales(start, end)
        if kind == "staff":
            return self._report_staff(start, end)
        if kind == "popularity":
            return self._report_popularity(start, end)
        if kind == "pnl":
            return self._report_pnl(start, end)
        raise ValueError("Unknown report.")

    def _sales_totals(self, start: str, end: str) -> dict:
        row = self.q1(
            """SELECT COUNT(*) AS bills,
                      COALESCE(SUM(subtotal), 0) AS gross,
                      COALESCE(SUM(discount_amount), 0) AS discounts,
                      COALESCE(SUM(tax_amount), 0) AS tax,
                      COALESCE(SUM(total), 0) AS net,
                      COALESCE(SUM(cash_amount), 0) AS cash,
                      COALESCE(SUM(card_amount), 0) AS card,
                      COALESCE(SUM(transfer_amount), 0) AS transfer
               FROM invoices
               WHERE status != 'void' AND date(created_at) BETWEEN ? AND ?""",
            (start, end),
        )
        voided = self.q1(
            """SELECT COUNT(*) AS c FROM invoices
               WHERE status = 'void' AND date(created_at) BETWEEN ? AND ?""",
            (start, end),
        )["c"]
        expenses = self.q1(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE exp_date BETWEEN ? AND ?",
            (start, end),
        )["total"]
        daily_cash = self.q1(
            """SELECT COALESCE(SUM(amount), 0) AS total FROM expenses
               WHERE exp_date BETWEEN ? AND ? AND payment_mode = ? AND COALESCE(expense_type, 'daily') != 'monthly'""",
            (start, end, PAY_CASH),
        )["total"]
        monthly_cash = self.q1(
            """SELECT COALESCE(SUM(amount), 0) AS total FROM expenses
               WHERE exp_date BETWEEN ? AND ? AND payment_mode = ? AND expense_type = 'monthly'""",
            (start, end, PAY_CASH),
        )["total"]
        data = dict(row or {})
        data["voided"] = voided
        data["expenses"] = float(expenses or 0)
        data["daily_cash_expenses"] = float(daily_cash or 0)
        data["monthly_cash_expenses"] = float(monthly_cash or 0)
        data["profit"] = round_money(float(data.get("net") or 0) - float(expenses or 0))
        return data

    def _report_sales(self, start: str, end: str) -> dict:
        totals = self._sales_totals(start, end)
        commission = sum(self._commission_bases(start, end).values())
        bills = self.list_invoices(start, end, include_void=True)
        rows = []
        for bill in bills:
            rows.append(
                [
                    bill["invoice_no"],
                    format_time_only(bill["created_at"]),
                    bill["customer_name"] or "Walk-in Client",
                    bill["payment_mode"],
                    money(bill["discount_amount"]),
                    money(bill["total"]),
                    "Void" if bill["status"] == "void" else "Paid",
                ]
            )
        return {
            "title": "Daily Sales & Z-Report",
            "metrics": [
                {"label": "Net sales", "raw": totals["net"]},
                {"label": "Cash", "raw": totals["cash"]},
                {"label": "Card / POS", "raw": totals["card"]},
                {"label": "JazzCash / Bank", "raw": totals["transfer"]},
                {"label": "Discounts", "raw": totals["discounts"]},
                {"label": "Expenses", "raw": totals["expenses"]},
                {"label": "Daily cash expenses", "raw": totals["daily_cash_expenses"]},
                {"label": "Monthly cash expenses", "raw": totals["monthly_cash_expenses"]},
                {"label": "Net after expenses", "raw": totals["profit"]},
            ],
            "notes": [
                f"Bills: {int(totals['bills'])} paid, {int(totals['voided'])} void",
                f"Service charge collected: {money(totals['tax'])}",
                f"Staff commission base (before %): {money(commission)}",
                "Only cash expenses leave the drawer. Online expenses stay on the books and out of the till.",
            ],
            "headers": ["Invoice", "Time", "Client", "Payment", "Discount", "Total", "Status"],
            "rows": rows,
        }

    def _report_staff(self, start: str, end: str) -> dict:
        rows_raw = self.q(
            """SELECT ii.staff_id, COALESCE(ii.staff_name, 'Unassigned') AS staff_name,
                      COUNT(DISTINCT i.id) AS bills, SUM(ii.qty) AS qty, SUM(ii.line_total) AS revenue
               FROM invoice_items ii
               JOIN invoices i ON i.id = ii.invoice_id
               WHERE i.status != 'void' AND date(i.created_at) BETWEEN ? AND ?
               GROUP BY ii.staff_id, ii.staff_name
               ORDER BY revenue DESC""",
            (start, end),
        )
        bases = self._commission_bases(start, end)
        staff = {row["id"]: row for row in self.list_staff()}
        table = []
        for row in rows_raw:
            member = staff.get(row["staff_id"])
            pct = float(member["commission_pct"]) if member and pays_commission(member["salary_type"]) else 0
            base = bases.get(row["staff_id"], 0) if row["staff_id"] else 0
            commission = round_money(base * pct / 100.0) if row["staff_id"] else 0
            table.append(
                [
                    row["staff_name"] or "Unassigned",
                    member["role"] if member else "",
                    int(row["bills"]),
                    int(row["qty"]),
                    money(row["revenue"]),
                    f"{pct:g}%",
                    money(commission),
                ]
            )
        return {
            "title": "Staff Performance & Commission",
            "metrics": [
                {"label": "Team members", "raw": len(table), "plain": True},
                {"label": "Service revenue", "raw": sum(float(r["revenue"] or 0) for r in rows_raw)},
            ],
            "notes": ["Commission uses each person's salary setup and is calculated after invoice discounts."],
            "headers": ["Staff", "Role", "Bills", "Services", "Revenue", "Commission %", "Commission"],
            "rows": table,
        }

    def _report_popularity(self, start: str, end: str) -> dict:
        rows_raw = self.q(
            """SELECT ii.name, ii.kind, SUM(ii.qty) AS qty, SUM(ii.line_total) AS revenue
               FROM invoice_items ii
               JOIN invoices i ON i.id = ii.invoice_id
               WHERE i.status != 'void' AND ii.kind IN ('service', 'package')
                 AND date(i.created_at) BETWEEN ? AND ?
               GROUP BY ii.name, ii.kind
               ORDER BY revenue DESC""",
            (start, end),
        )
        total = sum(float(row["revenue"] or 0) for row in rows_raw) or 1
        table = []
        for row in rows_raw:
            share = float(row["revenue"] or 0) / total * 100
            table.append(
                [
                    row["name"],
                    "Deal" if row["kind"] == "package" else "Service",
                    int(row["qty"]),
                    money(row["revenue"]),
                    f"{share:.1f}%",
                ]
            )
        return {
            "title": "Service & Deal Popularity",
            "metrics": [
                {"label": "Menu lines sold", "raw": len(table), "plain": True},
                {"label": "Revenue", "raw": sum(float(r["revenue"] or 0) for r in rows_raw)},
            ],
            "notes": [],
            "headers": ["Name", "Type", "Qty", "Revenue", "Share"],
            "rows": table,
        }

    def _report_pnl(self, start: str, end: str) -> dict:
        totals = self._sales_totals(start, end)
        commission_paid_base = self._commission_bases(start, end)
        staff = {row["id"]: row for row in self.list_staff()}
        commission = 0.0
        for staff_id, base in commission_paid_base.items():
            member = staff.get(staff_id)
            if member and pays_commission(member["salary_type"]):
                commission += base * float(member["commission_pct"]) / 100.0
        by_category = self.q(
            """SELECT category, SUM(amount) AS total
               FROM expenses WHERE exp_date BETWEEN ? AND ?
               GROUP BY category ORDER BY total DESC""",
            (start, end),
        )
        rows = [
            ["Gross sales", money(totals["gross"])],
            ["Less: Discounts", money(totals["discounts"])],
            ["Net sales", money(totals["net"])],
            ["Less: Expenses", money(totals["expenses"])],
            ["Net profit after expenses", money(totals["profit"])],
            ["Staff commission accrued", money(commission)],
            ["Profit after commission", money(round_money(totals["profit"] - commission))],
            ["", ""],
        ]
        for row in by_category:
            rows.append([f"Expense · {row['category']}", money(row["total"])])
        return {
            "title": "Expense & Profit / Loss",
            "metrics": [
                {"label": "Net sales", "raw": totals["net"]},
                {"label": "Expenses", "raw": totals["expenses"]},
                {"label": "Net after expenses", "raw": totals["profit"]},
                {"label": "After commission", "raw": round_money(totals["profit"] - commission)},
            ],
            "notes": ["Commission is shown as a memo. Salary marked paid is tracked in Payroll."],
            "headers": ["Line", "Amount"],
            "rows": rows,
        }


def _compute_totals(items: list[dict], discount_type: str, discount_value: float, tax_pct: float):
    subtotal = round_money(sum(item["unit_price"] * item["qty"] for item in items))
    if discount_type == "percent":
        if discount_value < 0 or discount_value > 100:
            raise ValueError("Percent discount must be between 0 and 100.")
        discount = round_money(subtotal * discount_value / 100.0)
    elif discount_type == "flat":
        if discount_value < 0:
            raise ValueError("Discount cannot be negative.")
        discount = round_money(min(discount_value, subtotal))
    else:
        discount = 0.0
    taxable = round_money(subtotal - discount)
    if tax_pct < 0:
        raise ValueError("Service charge cannot be negative.")
    tax = round_money(taxable * tax_pct / 100.0)
    total = round_money(taxable + tax)
    return subtotal, discount, tax, total


def _hours_between(check_in: str | None, check_out: str | None) -> float:
    if not check_in or not check_out:
        return 0.0
    try:
        start = datetime.strptime(check_in, "%H:%M")
        end = datetime.strptime(check_out, "%H:%M")
    except ValueError:
        return 0.0
    if end <= start:
        end = end + timedelta(days=1)
    return round((end - start).total_seconds() / 3600.0, 2)


def format_time_only(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return value


def month_period(year: int, month: int) -> tuple[str, str]:
    return month_bounds(year, month)


def copy_backup_file(src: str, dest: str) -> None:
    shutil.copy2(src, dest)
