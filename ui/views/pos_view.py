"""Touch-friendly billing screen."""

from __future__ import annotations

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.utils import PAY_CARD, PAY_CASH, PAY_SPLIT, PAY_TRANSFER, PAYMENT_MODES, money, price_label, today_str
from services.printer_service import PrinterService
from ui.dialogs import CustomerDialog, HistoryDialog, PriceDialog, ReceiptDialog
from ui.widgets import ServiceCard, button, confirm, fill_table, page_header, page_layout, run_action, style_table, vscroll, warn
from PySide6.QtWidgets import QTableWidget


class PosView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.cart: list[dict] = []
        self.customer = None
        self.staff = []
        self.payloads = []
        self.visible_cards: list[ServiceCard] = []
        self.cat_key = "all"
        self.pending_appointment_id = None
        self._cols = 0
        self.printer = PrinterService()

        layout = page_layout(self)
        layout.addWidget(page_header("Front Desk", "Point of Sale", "Services, deals, and a slip that prints with the bill."))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_bill(), "New bill")
        self.tabs.addTab(self._build_history(), "Bill history")
        self.tabs.currentChanged.connect(lambda _index: self.reload_bills())
        layout.addWidget(self.tabs, 1)

    def _build_bill(self) -> QWidget:
        page = QWidget()
        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search services or deals")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _text: self.apply_filter())
        left_layout.addWidget(self.search)
        self.pill_host = QWidget()
        self.pill_host.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.pill_host.setMinimumHeight(42)
        self.pills = QHBoxLayout(self.pill_host)
        self.pills.setContentsMargins(0, 2, 0, 2)
        self.pills.setSpacing(8)
        self.pill_scroll = QScrollArea()
        pill_scroll = self.pill_scroll
        pill_scroll.setWidgetResizable(True)
        pill_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pill_scroll.setFixedHeight(72)
        pill_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pill_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pill_scroll.setWidget(self.pill_host)
        left_layout.addWidget(pill_scroll)
        self.grid_host = QWidget()
        self.grid_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(12)
        self.menu_scroll = vscroll(self.grid_host)
        self.menu_scroll.viewport().installEventFilter(self)
        left_layout.addWidget(self.menu_scroll, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        client = QFrame()
        client.setObjectName("card")
        client_layout = QVBoxLayout(client)
        self.client_search = QLineEdit()
        self.client_search.setPlaceholderText("Search client by name or phone")
        self.client_search.textChanged.connect(self._search_clients)
        self.results = QListWidget()
        self.results.setMaximumHeight(130)
        self.results.hide()
        self.results.itemClicked.connect(self._pick_client)
        client_actions = QHBoxLayout()
        walkin = button("Walk-in", "ghost", tiny=True)
        add_client = button("+ Client", "gold", tiny=True)
        history = button("History", "ghost", tiny=True)
        walkin.clicked.connect(self._walk_in)
        add_client.clicked.connect(self._add_client)
        history.clicked.connect(self._history)
        client_actions.addWidget(walkin)
        client_actions.addWidget(add_client)
        client_actions.addWidget(history)
        self.client_label = QLabel("Billing  ·  Walk-in Client")
        self.client_label.setWordWrap(True)
        client_layout.addWidget(self.client_search)
        client_layout.addWidget(self.results)
        client_layout.addLayout(client_actions)
        client_layout.addWidget(self.client_label)
        right_layout.addWidget(client)

        self.cart_host = QWidget()
        self.cart_layout = QVBoxLayout(self.cart_host)
        self.cart_layout.setContentsMargins(0, 0, 0, 0)
        self.cart_layout.addStretch()
        right_layout.addWidget(vscroll(self.cart_host), 1)

        totals = QFrame()
        totals.setObjectName("card")
        totals_layout = QVBoxLayout(totals)
        discount_row = QHBoxLayout()
        self.discount_type = QComboBox()
        self.discount_type.addItem("No discount", "none")
        self.discount_type.addItem("Flat Rs.", "flat")
        self.discount_type.addItem("Percent", "percent")
        self.discount_value = QSpinBox()
        self.discount_value.setRange(0, 1000000)
        self.tax = QSpinBox()
        self.tax.setRange(0, 50)
        self.tax.setSuffix(" %")
        discount_row.addWidget(self.discount_type, 2)
        discount_row.addWidget(self.discount_value, 1)
        discount_row.addWidget(QLabel("Service"))
        discount_row.addWidget(self.tax)
        self.pay_mode = QComboBox()
        for mode in PAYMENT_MODES:
            self.pay_mode.addItem(mode, mode)
        self.tendered = QSpinBox()
        self.tendered.setRange(0, 5_000_000)
        self.tendered.setPrefix("Received ")
        quick = QHBoxLayout()
        for label, amount in (("Exact", None), ("1,000", 1000), ("2,000", 2000), ("5,000", 5000)):
            chip = button(label, "ghost", tiny=True)
            chip.clicked.connect(lambda _checked=False, value=amount: self._quick_cash(value))
            quick.addWidget(chip)
        self.change_label = QLabel("Change  Rs. 0")
        split = QHBoxLayout()
        self.split_cash = self._money_spin("Cash")
        self.split_card = self._money_spin("Card")
        self.split_transfer = self._money_spin("Transfer")
        split.addWidget(self.split_cash)
        split.addWidget(self.split_card)
        split.addWidget(self.split_transfer)
        self.total_label = QLabel(money(0))
        self.total_label.setStyleSheet("font-size: 22px; color: #C9A96E;")
        self.pay_button = button("Save & Print", "primary")
        self.pay_button.setMinimumHeight(52)
        self.pay_button.clicked.connect(self.save_bill)
        clear = button("Clear bill", "ghost")
        clear.clicked.connect(self.new_bill)
        for widget in (self.discount_type, self.discount_value, self.tax, self.pay_mode, self.tendered, self.split_cash, self.split_card, self.split_transfer):
            signal = widget.currentIndexChanged if isinstance(widget, QComboBox) else widget.valueChanged
            signal.connect(lambda *_args: self.update_totals())
        self.pay_mode.currentIndexChanged.connect(self._toggle_payment)
        totals_layout.addLayout(discount_row)
        totals_layout.addWidget(self.pay_mode)
        totals_layout.addWidget(self.tendered)
        totals_layout.addLayout(quick)
        totals_layout.addWidget(self.change_label)
        totals_layout.addLayout(split)
        totals_layout.addWidget(self.total_label)
        totals_layout.addWidget(self.pay_button)
        totals_layout.addWidget(clear)
        right_layout.addWidget(totals)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([760, 460])
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)
        self._toggle_payment()
        return page

    def _build_history(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self.history_date = QDateEdit()
        self.history_date.setCalendarPopup(True)
        self.history_date.setDisplayFormat("dd MMM yyyy")
        self.history_date.setDate(QDate.currentDate())
        self.history_date.dateChanged.connect(lambda _value: self.reload_bills())
        reprint = button("Reprint", "primary", tiny=True)
        void = button("Void bill", "danger", tiny=True)
        reprint.clicked.connect(self._reprint)
        void.clicked.connect(self._void)
        row.addWidget(QLabel("Date"))
        row.addWidget(self.history_date)
        row.addStretch()
        row.addWidget(reprint)
        if self.host.is_admin:
            row.addWidget(void)
        self.bills = QTableWidget()
        style_table(self.bills)
        layout.addLayout(row)
        layout.addWidget(self.bills)
        self.bill_rows = []
        return page

    def _money_spin(self, prefix: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 5_000_000)
        spin.setPrefix(prefix + " ")
        return spin

    def refresh(self) -> None:
        self.reload_catalog()
        self.reload_staff()
        self.reload_bills()
        if self.tax.value() == 0 and not self.cart:
            self.tax.setValue(int(self.host.db.get_settings().get("service_charge_pct") or 0))

    def eventFilter(self, obj, event):
        if obj is self.menu_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._reflow()
        return super().eventFilter(obj, event)

    def reload_catalog(self) -> None:
        self.payloads = []
        for service in self.host.db.list_services(active_only=True):
            variable = bool(service["is_variable"])
            self.payloads.append(
                {
                    "kind": "service",
                    "id": service["id"],
                    "name": service["name"],
                    "cat": service["category_name"],
                    "variable": variable,
                    "min": service["min_price"],
                    "max": service["max_price"],
                    "price_text": price_label(service["min_price"], service["max_price"], variable),
                    "meta": service["category_name"].title(),
                    "is_groom": False,
                }
            )
        for package in self.host.db.list_packages(active_only=True):
            self.payloads.append(
                {
                    "kind": "package",
                    "id": package["id"],
                    "name": package["name"],
                    "cat": "deals",
                    "variable": False,
                    "price": package["price"],
                    "price_text": money(package["price"]),
                    "meta": package["tier"],
                    "is_groom": bool(package["is_groom"]),
                    "items": package["items"],
                }
            )
        self._build_pills()
        self.apply_filter()

    def _build_pills(self) -> None:
        while self.pills.count():
            item = self.pills.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        keys = [("All", "all"), ("Deals & Packages", "deals")]
        seen = []
        for payload in self.payloads:
            if payload["kind"] == "service" and payload["cat"] not in seen:
                seen.append(payload["cat"])
        for name in seen:
            keys.append((name.title(), name))
        if self.cat_key not in [key for _label, key in keys]:
            self.cat_key = "all"
        for label, key in keys:
            pill = button(label, "pill", tiny=True)
            pill.setCheckable(True)
            pill.setChecked(key == self.cat_key)
            pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            pill.setMinimumWidth(pill.fontMetrics().horizontalAdvance(label) + 36)
            pill.clicked.connect(lambda _checked=False, name=key: self._set_cat(name))
            self.pills.addWidget(pill)
        self.pills.addStretch()
        width = 8
        for index in range(self.pills.count()):
            widget = self.pills.itemAt(index).widget()
            if widget is not None:
                width += widget.minimumWidth() + 8
        self.pill_host.setMinimumWidth(width)

    def _set_cat(self, key: str) -> None:
        self.cat_key = key
        labels = {"all": "All", "deals": "Deals & Packages"}
        target = labels.get(key, key.title())
        for index in range(self.pills.count()):
            widget = self.pills.itemAt(index).widget()
            if widget is not None and hasattr(widget, "setChecked"):
                widget.setChecked(widget.text() == target)
        self.apply_filter()

    def apply_filter(self) -> None:
        text = self.search.text().strip().lower()
        visible = []
        for payload in self.payloads:
            if self.cat_key != "all" and payload["cat"] != self.cat_key:
                continue
            if text and text not in payload["name"].lower():
                continue
            visible.append(payload)
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.visible_cards = []
        for payload in visible:
            card = ServiceCard(payload)
            card.chosen.connect(self.add_payload)
            self.visible_cards.append(card)
        self._cols = 0
        self._reflow()

    def _reflow(self) -> None:
        width = max(self.menu_scroll.viewport().width(), 460)
        cols = max(2, width // 230)
        if cols == self._cols and self.grid.count() == len(self.visible_cards):
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        for index, card in enumerate(self.visible_cards):
            self.grid.addWidget(card, index // cols, index % cols)
        rows = (len(self.visible_cards) + cols - 1) // cols if self.visible_cards else 0
        self.grid_host.setMinimumHeight(self.grid.sizeHint().height() if rows else 0)
        self.grid_host.updateGeometry()

    def add_payload(self, payload: dict) -> None:
        if payload["kind"] == "service":
            self._add_service(payload)
        else:
            self._add_package(payload)

    def _add_service(self, payload: dict, staff_id=None) -> None:
        price = float(payload["min"])
        if payload.get("variable"):
            dialog = PriceDialog(payload["name"], payload["min"], payload["max"], self)
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            price = dialog.price
        self._add_line(
            {
                "kind": "service",
                "ref_id": payload["id"],
                "name": payload["name"],
                "qty": 1,
                "unit_price": price,
                "staff_id": staff_id,
                "is_groom": False,
                "detail": "",
            }
        )

    def _add_package(self, payload: dict, staff_id=None) -> None:
        if payload.get("is_groom") and self.customer:
            existing = self.host.db.active_groom_contract(self.customer["id"], payload["id"])
            if existing:
                warn(self, f"{self.customer['name']} already has an active {payload['name']}. Record the payment in Groom Tracker.")
                return
        if payload.get("is_groom"):
            detail = "Multi-session package. Sessions are tracked on the groom card."
        else:
            detail = "\n".join(item["name"] for item in payload.get("items") or [])
        self._add_line(
            {
                "kind": "package",
                "ref_id": payload["id"],
                "name": payload["name"],
                "qty": 1,
                "unit_price": float(payload["price"]),
                "staff_id": staff_id,
                "is_groom": bool(payload.get("is_groom")),
                "detail": detail,
            },
            merge=not payload.get("is_groom"),
        )

    def _add_line(self, line: dict, merge: bool = True) -> None:
        if merge and not line.get("staff_id"):
            for existing in self.cart:
                if (
                    existing["kind"] == line["kind"]
                    and existing["ref_id"] == line["ref_id"]
                    and existing["unit_price"] == line["unit_price"]
                    and not existing.get("staff_id")
                    and not existing.get("is_groom")
                ):
                    existing["qty"] += 1
                    self.render_cart()
                    return
        self.cart.append(line)
        self.render_cart()

    def render_cart(self) -> None:
        while self.cart_layout.count():
            item = self.cart_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.cart:
            empty = QLabel("The bill is empty. Tap a service to begin.")
            empty.setObjectName("muted")
            self.cart_layout.addWidget(empty)
        for index, line in enumerate(self.cart):
            self.cart_layout.addWidget(self._cart_row(index, line))
        self.cart_layout.addStretch()
        self.update_totals()

    def _cart_row(self, index: int, line: dict) -> QFrame:
        frame = QFrame()
        frame.setObjectName("cartLine")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        name = QLabel(line["name"])
        price = QLabel(money(line["unit_price"] * line["qty"]))
        minus = button("−", "ghost", tiny=True)
        qty = QLabel(str(line["qty"]))
        qty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qty.setMinimumWidth(18)
        plus = button("+", "ghost", tiny=True)
        remove = button("×", "danger", tiny=True)
        minus.setFixedWidth(32)
        plus.setFixedWidth(32)
        remove.setFixedWidth(32)
        minus.clicked.connect(lambda _checked=False, row=index: self._change_qty(row, -1))
        plus.clicked.connect(lambda _checked=False, row=index: self._change_qty(row, 1))
        remove.clicked.connect(lambda _checked=False, row=index: self._remove(row))
        staff = QComboBox()
        staff.addItem("Unassigned", None)
        for member in self.staff:
            staff.addItem(member["name"], member["id"])
        if line.get("staff_id") is not None:
            found = staff.findData(line["staff_id"])
            if found >= 0:
                staff.setCurrentIndex(found)
        staff.currentIndexChanged.connect(lambda _value, row=index, box=staff: self._set_staff(row, box))
        if line.get("is_groom"):
            plus.setEnabled(False)
            minus.setEnabled(False)
        staff.setMinimumWidth(110)
        layout.addWidget(name, 2)
        layout.addWidget(minus)
        layout.addWidget(qty)
        layout.addWidget(plus)
        layout.addWidget(staff, 2)
        layout.addWidget(price)
        layout.addWidget(remove)
        return frame

    def _set_staff(self, index: int, combo: QComboBox) -> None:
        if 0 <= index < len(self.cart):
            self.cart[index]["staff_id"] = combo.currentData()

    def _change_qty(self, index: int, delta: int) -> None:
        if not (0 <= index < len(self.cart)):
            return
        if self.cart[index].get("is_groom"):
            return
        self.cart[index]["qty"] = max(1, self.cart[index]["qty"] + delta)
        self.render_cart()

    def _remove(self, index: int) -> None:
        if 0 <= index < len(self.cart):
            del self.cart[index]
            self.render_cart()

    def reload_staff(self) -> None:
        self.staff = self.host.db.list_staff(active_only=True)
        self.render_cart()

    def update_totals(self) -> None:
        subtotal = sum(line["unit_price"] * line["qty"] for line in self.cart)
        kind = self.discount_type.currentData()
        value = self.discount_value.value()
        if kind == "percent":
            discount = subtotal * min(value, 100) / 100
        elif kind == "flat":
            discount = min(value, subtotal)
        else:
            discount = 0
        taxable = subtotal - discount
        tax = taxable * self.tax.value() / 100
        total = taxable + tax
        self._total = total
        self.total_label.setText(money(total))
        self.pay_button.setText(f"Save & Print   ·   {money(total)}")
        change = self.tendered.value() - total
        self.change_label.setText("Change  " + money(change if change > 0 else 0))

    def _toggle_payment(self) -> None:
        mode = self.pay_mode.currentData()
        cash = mode == PAY_CASH
        split = mode == PAY_SPLIT
        self.tendered.setVisible(cash)
        self.change_label.setVisible(cash)
        for widget in (self.split_cash, self.split_card, self.split_transfer):
            widget.setVisible(split)
        self.update_totals()

    def _quick_cash(self, amount) -> None:
        if amount is None:
            self.tendered.setValue(int(round(getattr(self, "_total", 0))))
        else:
            self.tendered.setValue(int(amount))

    def _search_clients(self, text: str) -> None:
        self.results.clear()
        if len(text.strip()) < 1:
            self.results.hide()
            return
        rows = self.host.db.search_customers(text.strip())
        for row in rows:
            item = QListWidgetItem(f"{row['name']}   {row['phone']}")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.results.addItem(item)
        self.results.setVisible(bool(rows))

    def _pick_client(self, item: QListWidgetItem) -> None:
        customer = self.host.db.get_customer(item.data(Qt.ItemDataRole.UserRole))
        if customer:
            self._set_customer(customer)
        self.results.hide()
        self.client_search.clear()

    def _set_customer(self, customer: dict) -> None:
        self.customer = customer
        self.client_label.setText(
            f"Billing  ·  {customer['name']}   {customer['phone']}\n{customer['loyalty_points']} loyalty points  ·  {customer['visits']} visits"
        )

    def _walk_in(self) -> None:
        self.customer = None
        self.client_label.setText("Billing  ·  Walk-in Client")
        self.client_search.clear()
        self.results.hide()

    def _add_client(self) -> None:
        dialog = CustomerDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        name, phone, notes = dialog.values()
        customer = run_action(self, lambda: self.host.db.upsert_customer(name, phone, notes))
        if customer:
            self._set_customer(customer)

    def _history(self) -> None:
        if not self.customer:
            warn(self, "Select a client to see visit history.")
            return
        HistoryDialog(self.host.db, self.customer, self.host.db.get_settings(), self).exec()

    def new_bill(self) -> None:
        self.cart = []
        self.pending_appointment_id = None
        self._walk_in()
        self.discount_type.setCurrentIndex(0)
        self.discount_value.setValue(0)
        self.tax.setValue(int(self.host.db.get_settings().get("service_charge_pct") or 0))
        self.pay_mode.setCurrentIndex(0)
        self.tendered.setValue(0)
        for spin in (self.split_cash, self.split_card, self.split_transfer):
            spin.setValue(0)
        self.render_cart()

    def load_appointment(self, appointment_id: int) -> None:
        appointment = self.host.db.get_appointment(appointment_id)
        if not appointment or appointment["status"] == "Cancelled":
            warn(self, "That appointment cannot be billed.")
            return
        self.new_bill()
        self.pending_appointment_id = appointment_id
        customer = None
        if appointment.get("customer_id"):
            customer = self.host.db.get_customer(appointment["customer_id"])
        elif len(appointment.get("phone") or "") >= 7:
            customer = self.host.db.upsert_customer(appointment["customer_name"], appointment["phone"])
        if customer:
            self._set_customer(customer)
        staff_id = appointment.get("staff_id")
        if appointment.get("service_id"):
            service = self.host.db.get_service(appointment["service_id"])
            if service:
                payload = next((item for item in self.payloads if item["kind"] == "service" and item["id"] == service["id"]), None)
                if payload:
                    self._add_service(payload, staff_id=staff_id)
        elif appointment.get("package_id"):
            payload = next((item for item in self.payloads if item["kind"] == "package" and item["id"] == appointment["package_id"]), None)
            if payload:
                self._add_package(payload, staff_id=staff_id)

    def save_bill(self) -> None:
        if not self.cart:
            warn(self, "Add a service or deal first.")
            return
        if any(not line.get("staff_id") for line in self.cart):
            if not confirm(self, "Some lines have no stylist, so commission will not be tracked for them. Save the bill anyway?"):
                return
        payload = {
            "items": self.cart,
            "customer_id": self.customer["id"] if self.customer else None,
            "discount_type": self.discount_type.currentData(),
            "discount_value": min(self.discount_value.value(), 100) if self.discount_type.currentData() == "percent" else (0 if self.discount_type.currentData() == "none" else self.discount_value.value()),
            "tax_pct": self.tax.value(),
            "payment_mode": self.pay_mode.currentData(),
            "cash_tendered": self.tendered.value(),
            "split_cash": self.split_cash.value(),
            "split_card": self.split_card.value(),
            "split_transfer": self.split_transfer.value(),
            "appointment_id": self.pending_appointment_id,
            "username": self.host.user["username"],
            "origin": "pos",
        }
        invoice = run_action(self, lambda: self.host.db.checkout(payload))
        if not invoice:
            return
        self.new_bill()
        self.reload_bills()
        settings = self.host.db.get_settings()
        ok, message = self.printer.print_invoice(invoice, settings)
        text = f"Saved {invoice['invoice_no']}."
        text += "\n" + message if ok else "\nThe printer did not print. Retry, or save a PDF.\n" + message
        ReceiptDialog(invoice, settings, self, text).exec()

    def reload_bills(self) -> None:
        if not hasattr(self, "history_date"):
            return
        day = self.history_date.date()
        iso = f"{day.year():04d}-{day.month():02d}-{day.day():02d}"
        self.bill_rows = self.host.db.list_invoices(iso, iso, include_void=True)
        fill_table(
            self.bills,
            ["Invoice", "Time", "Client", "Payment", "Total", "Status"],
            [
                [
                    row["invoice_no"],
                    row["created_at"][11:16],
                    row["customer_name"],
                    row["payment_mode"],
                    money(row["total"]),
                    "Void" if row["status"] == "void" else "Paid",
                ]
                for row in self.bill_rows
            ],
        )

    def _selected_bill(self):
        row = self.bills.currentRow()
        if row < 0 or row >= len(self.bill_rows):
            warn(self, "Select a bill first.")
            return None
        return self.bill_rows[row]

    def _reprint(self) -> None:
        row = self._selected_bill()
        if not row:
            return
        invoice = self.host.db.get_invoice(row["id"])
        if invoice:
            ReceiptDialog(invoice, self.host.db.get_settings(), self, "Reprint").exec()

    def _void(self) -> None:
        row = self._selected_bill()
        if not row:
            return
        links = self.host.db.invoice_groom_links(row["id"])
        extra = ""
        if links:
            extra = "\n\nThis bill is linked to a groom package. Voiding it puts that payment back on the package balance."
        if not confirm(self, f"Void {row['invoice_no']}? This removes it from revenue.{extra}"):
            return
        done = run_action(self, lambda: self.host.db.void_invoice(row["id"], self.host.user["username"]))
        if done is None and row["status"] != "void":
            # void_invoice returns None. run_action returns None both on success and failure.
            pass
        self.reload_bills()
