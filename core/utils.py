"""Formatting, constants, and date ranges used across the app."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

APP_NAME = "CAVERON"
APP_VERSION = "1.0.0"
WINDOW_TITLE = "CAVERON — Salon & Barber"

PAY_CASH = "Cash"
PAY_CARD = "Card / POS Machine"
PAY_TRANSFER = "JazzCash / EasyPaisa / Bank Transfer"
PAY_SPLIT = "Split Payment"
PAYMENT_MODES = [PAY_CASH, PAY_CARD, PAY_TRANSFER, PAY_SPLIT]

EXPENSE_CATEGORIES = [
    "Rent",
    "Electricity",
    "Generator Fuel",
    "Tea & Refreshments",
    "Blade & Towel Supplies",
    "Cosmetics Purchase",
    "Maintenance",
    "Miscellaneous",
]
EXPENSE_PAY_MODES = [PAY_CASH, PAY_CARD, PAY_TRANSFER]

STAFF_ROLES = ["Senior Stylist", "Barber", "Facial Specialist", "Manager", "Helper"]
SALARY_FIXED = "Fixed Monthly Salary"
SALARY_COMMISSION = "Commission Only (%)"
SALARY_HYBRID = "Hybrid (Base Salary + Service Commission %)"
SALARY_TYPES = [SALARY_FIXED, SALARY_COMMISSION, SALARY_HYBRID]

ATT_PRESENT = "Present"
ATT_ABSENT = "Absent"
ATT_HALF = "Half-Day"
ATT_LEAVE = "Leave"
ATTENDANCE_STATUSES = [ATT_PRESENT, ATT_ABSENT, ATT_HALF, ATT_LEAVE]

TIER_STANDARD = "Standard"
TIER_PREMIUM = "Premium"
TIER_GROOM = "Signature Groom"
PACKAGE_TIERS = [TIER_STANDARD, TIER_PREMIUM, TIER_GROOM]

ROLE_ADMIN = "admin"
ROLE_CASHIER = "cashier"
ROLE_LABELS = {
    ROLE_ADMIN: "Admin / Owner",
    ROLE_CASHIER: "Receptionist / Cashier",
}

ADJUSTMENT_KINDS = ["Advance", "Deduction", "Tip", "Bonus"]
STOCK_REASONS = ["Purchase", "Usage", "Damage", "Count Correction"]
CHAIRS = ["Any", "Chair 1", "Chair 2", "Chair 3", "Chair 4", "Chair 5", "Chair 6"]
APPT_STATUSES = ["Waiting", "In Chair", "Completed", "Cancelled"]


def money(value) -> str:
    amount = float(value or 0)
    if abs(amount - round(amount)) < 0.001:
        return f"Rs. {amount:,.0f}"
    return f"Rs. {amount:,.2f}"


def price_label(min_price, max_price, variable: bool) -> str:
    if variable and max_price and float(max_price) != float(min_price):
        return f"{money(min_price)} – {money(max_price)}"
    return money(min_price)


def round_money(value) -> float:
    return round(float(value or 0) + 1e-9, 2)


def today_str() -> str:
    return date.today().isoformat()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def format_dt(value: str) -> str:
    if not value:
        return ""
    try:
        dt = parse_dt(value)
    except ValueError:
        return value
    return dt.strftime("%d %b %Y, %I:%M %p").replace(" 0", " ")


def format_time(value: str) -> str:
    if not value:
        return ""
    try:
        dt = parse_dt(value)
    except ValueError:
        return value
    return dt.strftime("%I:%M %p").lstrip("0")


def format_date(value: str) -> str:
    if not value:
        return ""
    try:
        dt = date.fromisoformat(value[:10])
    except ValueError:
        return value
    return dt.strftime("%d %b %Y")


def month_bounds(year: int, month: int) -> tuple[str, str]:
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"


def preset_range(preset: str) -> tuple[date, date]:
    today = date.today()
    if preset == "today":
        return today, today
    if preset == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if preset == "week":
        start = today - timedelta(days=today.weekday())
        return start, today
    if preset == "month":
        return today.replace(day=1), today
    raise ValueError("Unknown date range.")


def pays_base(salary_type: str) -> bool:
    return salary_type != SALARY_COMMISSION


def pays_commission(salary_type: str) -> bool:
    return salary_type != SALARY_FIXED


def slip_text(value: str) -> str:
    return (
        (value or "")
        .replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("×", "x")
    )


def wrap_text(text: str, width: int) -> list[str]:
    text = slip_text(text).strip()
    if not text:
        return []
    if width < 8:
        width = 8
    lines: list[str] = []
    for paragraph in text.splitlines():
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            while len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:width])
                word = word[width:]
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def pair_line(left: str, right: str, width: int) -> str:
    left = slip_text(left)
    right = slip_text(right)
    if len(left) + len(right) + 1 > width:
        left = left[: max(0, width - len(right) - 1)]
    gap = width - len(left) - len(right)
    return left + (" " * max(1, gap)) + right
