"""Sales, staff, popularity, and profit for any date range."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QTableWidget, QVBoxLayout, QWidget

from services.report_service import choose_save_path, print_html, report_html, write_csv, write_pdf, write_xlsx
from ui.widgets import DateRangeBar, KpiCard, button, fill_table, info, page_header, page_layout, style_table, warn


class ReportsView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.report = None
        layout = page_layout(self)
        layout.addWidget(page_header("Insights", "Reports", "Sales, staff, services, and profit for any range."))
        tools = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItem("Daily Sales & Z-Report", "sales")
        self.kind.addItem("Staff Performance & Commission", "staff")
        self.kind.addItem("Service & Deal Popularity", "popularity")
        self.kind.addItem("Expense & Profit / Loss", "pnl")
        self.range = DateRangeBar()
        run = button("Run report", "primary")
        run.clicked.connect(self.refresh)
        self.kind.currentIndexChanged.connect(lambda _index: self.refresh())
        self.range.changed.connect(self.refresh)
        tools.addWidget(self.kind)
        tools.addWidget(self.range, 1)
        tools.addWidget(run)
        layout.addLayout(tools)
        self.metrics = QGridLayout()
        self.metrics.setHorizontalSpacing(10)
        self.metrics.setVerticalSpacing(10)
        self.metric_cards = []
        layout.addLayout(self.metrics)
        self.notes = QLabel("")
        self.notes.setWordWrap(True)
        self.notes.setObjectName("muted")
        layout.addWidget(self.notes)
        self.table = QTableWidget()
        style_table(self.table)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        pdf = button("Export PDF", "primary")
        excel = button("Export Excel", "gold")
        csv_button = button("Export CSV", "ghost")
        print_button = button("Print", "ghost")
        pdf.clicked.connect(self._pdf)
        excel.clicked.connect(self._excel)
        csv_button.clicked.connect(self._csv)
        print_button.clicked.connect(self._print)
        for widget in (pdf, excel, csv_button, print_button):
            actions.addWidget(widget)
        actions.addStretch()
        layout.addLayout(actions)

    def open_preset(self, kind: str, preset: str) -> None:
        index = self.kind.findData(kind)
        if index >= 0:
            self.kind.blockSignals(True)
            self.kind.setCurrentIndex(index)
            self.kind.blockSignals(False)
        self.range.set_preset(preset)

    def refresh(self) -> None:
        start, end = self.range.range_strings()
        try:
            self.report = self.host.db.run_report(self.kind.currentData(), start, end)
        except Exception as exc:
            warn(self, str(exc))
            return
        while self.metrics.count():
            item = self.metrics.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.metric_cards = []
        columns = 4
        for index, metric in enumerate(self.report.get("metrics") or []):
            card = KpiCard(metric["label"])
            card.setMinimumWidth(210)
            if metric.get("plain"):
                card.set_value(str(int(metric["raw"])))
            else:
                from core.utils import money

                card.set_value(money(metric["raw"]))
            self.metrics.addWidget(card, index // columns, index % columns)
        self.notes.setText("  ".join(self.report.get("notes") or []))
        fill_table(self.table, self.report.get("headers") or [], self.report.get("rows") or [])

    def _html(self) -> str | None:
        if not self.report:
            warn(self, "Run a report first.")
            return None
        start, end = self.range.range_strings()
        return report_html(self.report, self.host.db.get_settings(), start, end)

    def _pdf(self) -> None:
        html_text = self._html()
        if not html_text:
            return
        path = choose_save_path(self, "Export PDF", "caveron-report.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            write_pdf(html_text, path)
            info(self, "Report saved.")
        except Exception as exc:
            warn(self, f"Could not save the PDF.\n{exc}")

    def _excel(self) -> None:
        if not self.report:
            warn(self, "Run a report first.")
            return
        path = choose_save_path(self, "Export Excel", "caveron-report.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        start, end = self.range.range_strings()
        try:
            write_xlsx(self.report, self.host.db.get_settings(), start, end, path)
            info(self, "Workbook saved.")
        except Exception as exc:
            warn(self, "Excel export needs openpyxl. A CSV was not written automatically.\n" + str(exc))

    def _csv(self) -> None:
        if not self.report:
            warn(self, "Run a report first.")
            return
        path = choose_save_path(self, "Export CSV", "caveron-report.csv", "CSV (*.csv)")
        if not path:
            return
        write_csv(self.report, path)
        info(self, "CSV saved.")

    def _print(self) -> None:
        html_text = self._html()
        if html_text:
            print_html(html_text, self)
