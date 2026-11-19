"""Daily spend and consumable stock."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor

from core.utils import EXPENSE_CATEGORIES, EXPENSE_PAY_MODES, STOCK_REASONS, money
from ui.widgets import DateRangeBar, button, confirm, fill_table, page_header, page_layout, run_action, style_table, warn


class ExpensesView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.expense_id = None
        self.product_id = None
        self.expenses = []
        self.products = []
        layout = page_layout(self)
        layout.addWidget(page_header("Stockroom", "Expenses & Stock", "Rent, fuel, supplies, and the products that run low."))
        tabs = QTabWidget()
        tabs.addTab(self._expenses_tab(), "Daily expenses")
        tabs.addTab(self._stock_tab(), "Product stock")
        layout.addWidget(tabs, 1)
        self.tabs = tabs

    def focus_expense(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.description.setFocus()

    def _expenses_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.range = DateRangeBar()
        self.range.changed.connect(self._load_expenses)
        layout.addWidget(self.range)
        form = QHBoxLayout()
        self.exp_date = QDateEdit()
        self.exp_date.setCalendarPopup(True)
        self.exp_date.setDisplayFormat("dd MMM yyyy")
        self.exp_date.setDate(QDate.currentDate())
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(EXPENSE_CATEGORIES)
        self.description = QLineEdit()
        self.description.setPlaceholderText("Description")
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 5_000_000)
        self.amount.setDecimals(0)
        self.amount.setPrefix("Rs. ")
        self.expense_type = QComboBox()
        self.expense_type.addItem("Daily Expense", "daily")
        self.expense_type.addItem("Monthly Expense", "monthly")
        self.pay_mode = QComboBox()
        self.pay_mode.addItems(EXPENSE_PAY_MODES)
        save = button("Save expense", "primary", tiny=True)
        clear = button("New", "ghost", tiny=True)
        delete = button("Delete", "danger", tiny=True)
        save.clicked.connect(self._save_expense)
        clear.clicked.connect(self._new_expense)
        delete.clicked.connect(self._delete_expense)
        for widget in (self.exp_date, self.expense_type, self.category, self.description, self.amount, self.pay_mode, save, clear, delete):
            form.addWidget(widget)
        layout.addLayout(form)
        hint = QLabel("Cash expenses, daily or monthly, leave the drawer. Card and transfer expenses are recorded and do not touch the till.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.expense_table = QTableWidget()
        style_table(self.expense_table)
        self.expense_table.itemSelectionChanged.connect(self._edit_expense)
        layout.addWidget(self.expense_table)
        self.expense_total = QLabelTotal()
        layout.addWidget(self.expense_total)
        return page

    def _stock_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.stock_alert = self._alert_label()
        layout.addWidget(self.stock_alert)
        form = QHBoxLayout()
        self.product_name = QLineEdit()
        self.product_name.setPlaceholderText("Product")
        self.product_category = QLineEdit()
        self.product_category.setPlaceholderText("Category")
        self.unit = QLineEdit("piece")
        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 100000)
        self.reorder = QDoubleSpinBox()
        self.reorder.setRange(0, 100000)
        self.cost = QDoubleSpinBox()
        self.cost.setRange(0, 1_000_000)
        self.cost.setPrefix("Rs. ")
        self.cost.setDecimals(0)
        self.product_active = QCheckBox("Active")
        self.product_active.setChecked(True)
        save = button("Save product", "primary", tiny=True)
        adjust = button("Adjust stock", "gold", tiny=True)
        save.clicked.connect(self._save_product)
        adjust.clicked.connect(self._adjust)
        for widget in (self.product_name, self.product_category, self.unit, self.qty, self.reorder, self.cost, self.product_active, save, adjust):
            form.addWidget(widget)
        layout.addLayout(form)
        self.product_table = QTableWidget()
        style_table(self.product_table)
        self.product_table.itemSelectionChanged.connect(self._edit_product)
        layout.addWidget(self.product_table)
        return page

    def _alert_label(self):
        from PySide6.QtWidgets import QLabel

        label = QLabel("")
        label.setWordWrap(True)
        label.setStyleSheet("color: #E74C3C;")
        self._alert = label
        return label

    def refresh(self) -> None:
        self._load_expenses()
        self._load_products()

    def _load_expenses(self) -> None:
        start, end = self.range.range_strings()
        self.expenses = self.host.db.list_expenses(start, end)
        fill_table(
            self.expense_table,
            ["Date", "Type", "Category", "Description", "Payment", "Drawer", "Amount"],
            [
                [
                    row["exp_date"],
                    "Monthly" if (row.get("expense_type") or "daily") == "monthly" else "Daily",
                    row["category"],
                    row["description"] or "",
                    row["payment_mode"],
                    "Deducted" if row["payment_mode"] == "Cash" else "Not in drawer",
                    money(row["amount"]),
                ]
                for row in self.expenses
            ],
        )
        daily_cash = monthly_cash = online = 0.0
        for row in self.expenses:
            amount = float(row["amount"])
            monthly = (row.get("expense_type") or "daily") == "monthly"
            if row["payment_mode"] == "Cash" and monthly:
                monthly_cash += amount
            elif row["payment_mode"] == "Cash":
                daily_cash += amount
            else:
                online += amount
        self.expense_total.setText(
            f"Daily cash {money(daily_cash)}    Monthly cash {money(monthly_cash)}    Online excluded {money(online)}"
        )

    def _new_expense(self) -> None:
        self.expense_id = None
        self.description.clear()
        self.amount.setValue(0)
        self.exp_date.setDate(QDate.currentDate())

    def _edit_expense(self) -> None:
        index = self.expense_table.currentRow()
        if index < 0 or index >= len(self.expenses):
            return
        row = self.expenses[index]
        self.expense_id = row["id"]
        year, month, day = [int(part) for part in row["exp_date"].split("-")]
        self.exp_date.setDate(QDate(year, month, day))
        self.category.setCurrentText(row["category"])
        self.description.setText(row["description"] or "")
        self.amount.setValue(float(row["amount"]))
        self.pay_mode.setCurrentText(row["payment_mode"])
        kind = row.get("expense_type") or "daily"
        index = self.expense_type.findData(kind)
        if index >= 0:
            self.expense_type.setCurrentIndex(index)

    def _save_expense(self) -> None:
        value = self.exp_date.date()
        saved = run_action(
            self,
            lambda: self.host.db.save_expense(
                {
                    "id": self.expense_id,
                    "exp_date": f"{value.year():04d}-{value.month():02d}-{value.day():02d}",
                    "category": self.category.currentText(),
                    "description": self.description.text(),
                    "amount": self.amount.value(),
                    "payment_mode": self.pay_mode.currentText(),
                    "expense_type": self.expense_type.currentData(),
                }
            ),
        )
        if saved:
            self._new_expense()
            self._load_expenses()

    def _delete_expense(self) -> None:
        index = self.expense_table.currentRow()
        if index < 0 or index >= len(self.expenses):
            warn(self, "Select an expense.")
            return
        row = self.expenses[index]
        if confirm(self, f"Delete this {row['category']} expense of {money(row['amount'])}?"):
            run_action(self, lambda: self.host.db.delete_expense(row["id"]) or True)
            self._new_expense()
            self._load_expenses()

    def _load_products(self) -> None:
        self.products = self.host.db.list_products()
        fill_table(
            self.product_table,
            ["Product", "Category", "On hand", "Reorder", "Cost", "Status"],
            [
                [
                    row["name"],
                    row["category"] or "",
                    f"{float(row['qty']):g} {row['unit'] or ''}".strip(),
                    f"{float(row['reorder_level']):g}",
                    money(row["cost_price"]),
                    "Low" if row["active"] and float(row["qty"]) <= float(row["reorder_level"]) else ("Active" if row["active"] else "Hidden"),
                ]
                for row in self.products
            ],
        )
        for index, row in enumerate(self.products):
            if row["active"] and float(row["qty"]) <= float(row["reorder_level"]):
                for column in range(self.product_table.columnCount()):
                    item = self.product_table.item(index, column)
                    if item:
                        item.setForeground(QColor("#E74C3C"))
        low = [row["name"] for row in self.products if row["active"] and float(row["qty"]) <= float(row["reorder_level"])]
        self._alert.setText("Low stock: " + ", ".join(low) if low else "Stock levels are above the reorder lines.")
        if not low:
            self._alert.setStyleSheet("color: #2ECC71;")
        else:
            self._alert.setStyleSheet("color: #E74C3C;")

    def _edit_product(self) -> None:
        index = self.product_table.currentRow()
        if index < 0 or index >= len(self.products):
            return
        row = self.products[index]
        self.product_id = row["id"]
        self.product_name.setText(row["name"])
        self.product_category.setText(row["category"] or "")
        self.unit.setText(row["unit"] or "piece")
        self.qty.setValue(float(row["qty"]))
        self.reorder.setValue(float(row["reorder_level"]))
        self.cost.setValue(float(row["cost_price"]))
        self.product_active.setChecked(bool(row["active"]))

    def _save_product(self) -> None:
        editing = self.product_id
        new_qty = self.qty.value()
        saved = run_action(
            self,
            lambda: self.host.db.save_product(
                {
                    "id": self.product_id,
                    "name": self.product_name.text(),
                    "category": self.product_category.text(),
                    "unit": self.unit.text() or "piece",
                    "qty": new_qty,
                    "reorder_level": self.reorder.value(),
                    "cost_price": self.cost.value(),
                    "active": self.product_active.isChecked(),
                }
            ),
        )
        if saved and editing:
            run_action(self, lambda: self.host.db.set_product_qty(editing, new_qty, "Count Correction", "Quantity edited on the product form") or True)
        if saved:
            self.product_id = None
            self.product_name.clear()
            self._load_products()

    def _adjust(self) -> None:
        if not self.product_id:
            warn(self, "Select a product first.")
            return
        product = next(row for row in self.products if row["id"] == self.product_id)
        dialog = QDialog(self)
        dialog.setWindowTitle("Adjust stock")
        layout = QFormLayout(dialog)
        qty = QDoubleSpinBox()
        qty.setRange(0, 100000)
        qty.setValue(float(product["qty"]))
        reason = QComboBox()
        reason.addItems(STOCK_REASONS)
        note = QLineEdit()
        layout.addRow("New quantity", qty)
        layout.addRow("Reason", reason)
        layout.addRow("Note", note)
        actions = QHBoxLayout()
        cancel = button("Cancel", "ghost")
        save = button("Update", "primary")
        cancel.clicked.connect(dialog.reject)
        save.clicked.connect(dialog.accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addRow(actions)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if run_action(self, lambda: self.host.db.set_product_qty(self.product_id, qty.value(), reason.currentText(), note.text()) or True):
            self._load_products()


class QLabelTotal(QWidget):
    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QLabel

        self.label = QLabel("Total in range  Rs. 0")
        self.label.setObjectName("eyebrow")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def setText(self, text: str) -> None:
        self.label.setText(text)
