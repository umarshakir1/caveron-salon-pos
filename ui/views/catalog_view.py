"""Categories, services, and package prices."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.utils import PACKAGE_TIERS, TIER_GROOM, money, price_label
from ui.widgets import button, confirm, fill_table, page_header, page_layout, run_action, style_table, warn


class CatalogView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        layout = page_layout(self)
        layout.addWidget(page_header("Menu", "Services & Deals", "Categories, fixed prices, ranges, and package bundles."))
        self.tabs = QTabWidget()
        self.category_table = QTableWidget()
        self.service_table = QTableWidget()
        self.package_table = QTableWidget()
        for table in (self.category_table, self.service_table, self.package_table):
            style_table(table)
        self.tabs.addTab(self._pane(self.category_table, "Add category", self._add_category, self._edit_category, self._delete_category), "Categories")
        self.tabs.addTab(self._pane(self.service_table, "Add service", self._add_service, self._edit_service, self._delete_service), "Services")
        self.tabs.addTab(self._pane(self.package_table, "Add deal", self._add_package, self._edit_package, self._delete_package), "Deals & packages")
        layout.addWidget(self.tabs, 1)
        self.categories = []
        self.services = []
        self.packages = []

    def _pane(self, table, add_label, on_add, on_edit, on_delete) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        add = button(add_label, "primary", tiny=True)
        edit = button("Edit", "ghost", tiny=True)
        delete = button("Delete", "danger", tiny=True)
        add.clicked.connect(on_add)
        edit.clicked.connect(on_edit)
        delete.clicked.connect(on_delete)
        row.addWidget(add)
        row.addWidget(edit)
        row.addWidget(delete)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(table)
        return page

    def refresh(self) -> None:
        self.categories = self.host.db.list_categories()
        self.services = self.host.db.list_services()
        self.packages = self.host.db.list_packages()
        fill_table(
            self.category_table,
            ["Category", "Order", "Status"],
            [[row["name"], row["sort_order"], "Active" if row["active"] else "Hidden"] for row in self.categories],
        )
        fill_table(
            self.service_table,
            ["Service", "Category", "Price", "Status"],
            [
                [
                    row["name"],
                    row["category_name"],
                    price_label(row["min_price"], row["max_price"], row["is_variable"]),
                    "Active" if row["active"] else "Hidden",
                ]
                for row in self.services
            ],
        )
        fill_table(
            self.package_table,
            ["Deal", "Tier", "Price", "Sessions / items", "Status"],
            [
                [
                    row["name"],
                    row["tier"],
                    money(row["price"]),
                    len(row["items"]),
                    "Active" if row["active"] else "Hidden",
                ]
                for row in self.packages
            ],
        )
        self._fit(self.category_table, stretch=(0,), center=(2,))
        self._fit(self.service_table, stretch=(0,), center=(3,))
        self._fit(self.package_table, stretch=(0,), center=(4,))

    def _fit(self, table, stretch, center) -> None:
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(88)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for column in stretch:
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        alignment = Qt.AlignmentFlag.AlignCenter
        for column in center:
            label = table.horizontalHeaderItem(column)
            if label:
                label.setTextAlignment(alignment)
            for row in range(table.rowCount()):
                cell = table.item(row, column)
                if cell:
                    cell.setTextAlignment(alignment)

    def _selected(self, table, rows):
        index = table.currentRow()
        if index < 0 or index >= len(rows):
            warn(self, "Select a row first.")
            return None
        return rows[index]

    def _add_category(self):
        self._category_dialog(None)

    def _edit_category(self):
        row = self._selected(self.category_table, self.categories)
        if row:
            self._category_dialog(row)

    def _category_dialog(self, row):
        dialog = QDialog(self)
        dialog.setWindowTitle("Category")
        layout = QFormLayout(dialog)
        name = QLineEdit(row["name"] if row else "")
        order = QSpinBox()
        order.setRange(0, 999)
        order.setValue(int(row["sort_order"]) if row else 0)
        active = QCheckBox("Active on the POS")
        active.setChecked(True if row is None else bool(row["active"]))
        layout.addRow("Name", name)
        layout.addRow("Sort order", order)
        layout.addRow("", active)
        if self._dialog_buttons(dialog, layout):
            saved = run_action(
                self,
                lambda: self.host.db.save_category(
                    {"id": row["id"] if row else None, "name": name.text(), "sort_order": order.value(), "active": active.isChecked()}
                ),
            )
            if saved:
                self.refresh()

    def _delete_category(self):
        row = self._selected(self.category_table, self.categories)
        if row and confirm(self, f"Delete {row['name']}?"):
            if run_action(self, lambda: self.host.db.delete_category(row["id"])):
                self.refresh()

    def _add_service(self):
        self._service_dialog(None)

    def _edit_service(self):
        row = self._selected(self.service_table, self.services)
        if row:
            self._service_dialog(row)

    def _service_dialog(self, row):
        dialog = QDialog(self)
        dialog.setWindowTitle("Service")
        dialog.resize(460, 320)
        layout = QFormLayout(dialog)
        category = QComboBox()
        for item in self.host.db.list_categories():
            category.addItem(item["name"], item["id"])
        name = QLineEdit(row["name"] if row else "")
        variable = QCheckBox("Price range (cashier enters the agreed price)")
        minimum = QDoubleSpinBox()
        maximum = QDoubleSpinBox()
        for spin in (minimum, maximum):
            spin.setRange(0, 1_000_000)
            spin.setDecimals(0)
            spin.setPrefix("Rs. ")
        active = QCheckBox("Active on the POS")
        active.setChecked(True if row is None else bool(row["active"]))
        if row:
            index = category.findData(row["category_id"])
            if index >= 0:
                category.setCurrentIndex(index)
            variable.setChecked(bool(row["is_variable"]))
            minimum.setValue(float(row["min_price"]))
            maximum.setValue(float(row["max_price"]))
        layout.addRow("Category", category)
        layout.addRow("Name", name)
        layout.addRow("", variable)
        layout.addRow("Price / minimum", minimum)
        layout.addRow("Maximum", maximum)
        layout.addRow("", active)

        def toggle():
            maximum.setEnabled(variable.isChecked())

        variable.toggled.connect(toggle)
        toggle()
        if self._dialog_buttons(dialog, layout):
            saved = run_action(
                self,
                lambda: self.host.db.save_service(
                    {
                        "id": row["id"] if row else None,
                        "category_id": category.currentData(),
                        "name": name.text(),
                        "is_variable": variable.isChecked(),
                        "min_price": minimum.value(),
                        "max_price": maximum.value() if variable.isChecked() else minimum.value(),
                        "active": active.isChecked(),
                    }
                ),
            )
            if saved:
                self.refresh()

    def _delete_service(self):
        row = self._selected(self.service_table, self.services)
        if not row:
            return
        if not confirm(self, f"Delete {row['name']}? If it is already on a bill, it will be hidden instead."):
            return
        result = run_action(self, lambda: self.host.db.delete_service(row["id"]))
        if result == "deactivated":
            warn(self, "This service is on past bills, so it was hidden instead of deleted.")
        if result:
            self.refresh()

    def _add_package(self):
        self._package_dialog(None)

    def _edit_package(self):
        row = self._selected(self.package_table, self.packages)
        if row:
            self._package_dialog(self.host.db.get_package(row["id"]))

    def _package_dialog(self, row):
        dialog = QDialog(self)
        dialog.setWindowTitle("Deal")
        dialog.setMinimumSize(760, 680)
        dialog.resize(820, 740)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        form = QFormLayout()
        name = QLineEdit(row["name"] if row else "")
        tier = QComboBox()
        tier.addItems(PACKAGE_TIERS)
        price = QDoubleSpinBox()
        price.setRange(0, 1_000_000)
        price.setDecimals(0)
        price.setPrefix("Rs. ")
        description = QTextEdit(row["description"] if row else "")
        description.setFixedHeight(70)
        groom = QCheckBox("Signature groom package (multi-session tracker)")
        active = QCheckBox("Active on the POS")
        active.setChecked(True if row is None else bool(row["active"]))
        if row:
            tier.setCurrentText(row["tier"])
            price.setValue(float(row["price"]))
            groom.setChecked(bool(row["is_groom"]))
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("Name", name)
        form.addRow("Tier", tier)
        form.addRow("Deal price", price)
        form.addRow("Description", description)
        form.addRow("", groom)
        form.addRow("", active)
        layout.addLayout(form)
        items = QTableWidget(0, 2)
        items.setHorizontalHeaderLabels(["Included service", "Qty / sessions"])
        style_table(items)
        items.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        items.setMinimumHeight(240)
        items.horizontalHeader().setStretchLastSection(False)
        items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        items.setColumnWidth(1, 150)
        if row:
            for item in row["items"]:
                self._append_item(items, item["name"], item["qty"])
        else:
            self._append_item(items, "", 1)
        layout.addWidget(items)
        row_buttons = QHBoxLayout()
        add_line = button("Add line", "ghost", tiny=True)
        remove_line = button("Remove line", "danger", tiny=True)
        add_line.clicked.connect(lambda: self._append_item(items, "", 1))
        remove_line.clicked.connect(lambda: items.removeRow(items.currentRow()) if items.currentRow() >= 0 else None)
        row_buttons.addWidget(add_line)
        row_buttons.addWidget(remove_line)
        row_buttons.addStretch()
        layout.addLayout(row_buttons)
        tier.currentTextChanged.connect(lambda text: groom.setChecked(text == TIER_GROOM))

        def collect():
            lines = []
            for index in range(items.rowCount()):
                name_item = items.item(index, 0)
                qty_item = items.item(index, 1)
                lines.append({"name": name_item.text() if name_item else "", "qty": int(qty_item.text() or "1") if qty_item else 1})
            return lines

        actions = QHBoxLayout()
        cancel = button("Cancel", "ghost")
        save = button("Save", "primary")
        cancel.clicked.connect(dialog.reject)
        save.clicked.connect(dialog.accept)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            lines = collect()
        except ValueError:
            warn(self, "Session quantity must be a number.")
            return
        saved = run_action(
            self,
            lambda: self.host.db.save_package(
                {
                    "id": row["id"] if row else None,
                    "name": name.text(),
                    "tier": tier.currentText(),
                    "price": price.value(),
                    "description": description.toPlainText(),
                    "is_groom": groom.isChecked(),
                    "active": active.isChecked(),
                },
                lines,
            ),
        )
        if saved:
            self.refresh()

    def _append_item(self, table, name, qty):
        from PySide6.QtWidgets import QTableWidgetItem

        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(name))
        table.setItem(row, 1, QTableWidgetItem(str(qty)))

    def _delete_package(self):
        row = self._selected(self.package_table, self.packages)
        if not row:
            return
        if not confirm(self, f"Delete {row['name']}? If it has been sold, it will be hidden instead."):
            return
        result = run_action(self, lambda: self.host.db.delete_package(row["id"]))
        if result == "deactivated":
            warn(self, "This deal is already on bills or groom cards, so it was hidden instead of deleted.")
        if result:
            self.refresh()

    def _dialog_buttons(self, dialog: QDialog, layout) -> bool:
        dialog.setMinimumWidth(480)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)
        actions = QHBoxLayout()
        cancel = button("Cancel", "ghost")
        save = button("Save", "primary")
        cancel.clicked.connect(dialog.reject)
        save.clicked.connect(dialog.accept)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(save)
        if isinstance(layout, QFormLayout):
            layout.addRow(actions)
        else:
            layout.addLayout(actions)
        return dialog.exec() == QDialog.DialogCode.Accepted
