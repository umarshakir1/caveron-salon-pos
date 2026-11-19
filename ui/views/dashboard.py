"""Executive home: today's money, the week, and shortcuts."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget

from core.utils import format_dt, money
from ui.dialogs import ReceiptDialog
from ui.theme import theme_colors
from ui.widgets import KpiCard, button, fill_table, page_header, page_layout, style_table

try:
    from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis

    HAS_CHARTS = True
except Exception:
    HAS_CHARTS = False


class DashboardView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.days = 7
        self.recent_rows = []
        layout = page_layout(self)
        layout.addWidget(page_header("Today", "Executive Dashboard", "Revenue, staff, and the cash drawer."))
        self.kpis = [
            KpiCard("Today's revenue"),
            KpiCard("Bills / clients"),
            KpiCard("Active staff"),
            KpiCard("Today's expenses"),
            KpiCard("Net cash in drawer"),
        ]
        kpi_row = QHBoxLayout()
        for card in self.kpis:
            kpi_row.addWidget(card)
        layout.addLayout(kpi_row)

        actions = QHBoxLayout()
        for text, slot in (
            ("+ New POS Bill", self.host.new_bill),
            ("+ Book Appointment", self.host.book_appointment),
            ("+ Record Expense", self.host.record_expense),
            ("End-of-Day Z-Report", self.host.open_z_report),
            ("Cash Drawer", self.host.go_drawer),
        ):
            widget = button(text, "gold" if text.startswith("End") or text.startswith("Close") else "primary")
            widget.clicked.connect(slot)
            actions.addWidget(widget)
        layout.addLayout(actions)

        self.low_stock = QLabel("")
        self.low_stock.setWordWrap(True)
        self.low_stock.setStyleSheet("color: #E74C3C;")
        layout.addWidget(self.low_stock)

        body = QHBoxLayout()
        chart_card = QFrame()
        chart_card.setObjectName("card")
        chart_layout = QVBoxLayout(chart_card)
        head = QHBoxLayout()
        head.addWidget(QLabel("Revenue"))
        head.addStretch()
        self.week_btn = QPushButton("7 days")
        self.month_btn = QPushButton("30 days")
        for widget, days in ((self.week_btn, 7), (self.month_btn, 30)):
            widget.setCheckable(True)
            widget.setObjectName("pill")
            widget.clicked.connect(lambda _checked=False, count=days: self._set_days(count))
            head.addWidget(widget)
        self.week_btn.setChecked(True)
        chart_layout.addLayout(head)
        self.chart = RevenueChart()
        self.chart.setMinimumHeight(280)
        chart_layout.addWidget(self.chart)
        body.addWidget(chart_card, 3)

        side = QVBoxLayout()
        self.services = RankList("Top services")
        self.deals = RankList("Top deals")
        side.addWidget(self.services)
        side.addWidget(self.deals)
        body.addLayout(side, 2)
        layout.addLayout(body, 1)

        self.table = QTableWidget()
        style_table(self.table)
        self.table.doubleClicked.connect(self._open_bill)
        layout.addWidget(QLabel("Recent bills"))
        layout.addWidget(self.table)

    def _set_days(self, days: int) -> None:
        self.days = days
        self.week_btn.setChecked(days == 7)
        self.month_btn.setChecked(days == 30)
        self.refresh()

    def refresh(self) -> None:
        data = self.host.db.dashboard(self.days)
        kpis = data["kpis"]
        self.kpis[0].set_value(money(kpis["revenue"]), "Paid bills today")
        self.kpis[1].set_value(str(kpis["bills"]), f"{kpis['clients']} clients")
        self.kpis[2].set_value(str(kpis["active_staff"]), "On the roster")
        self.kpis[3].set_value(
            money(kpis["expenses"]),
            f"Cash out {money(kpis['cash_out'])} · Online {money(kpis['online_expenses'])}",
        )
        if kpis["drawer_closed"] and kpis["drawer_actual"] is not None:
            self.kpis[4].set_value(money(kpis["drawer_actual"]), "Counted when the register closed")
        elif not kpis["drawer_opened"]:
            self.kpis[4].set_value("Not opened", f"Cash already out {money(kpis['cash_out'])}")
        else:
            self.kpis[4].set_value(money(kpis["drawer"]), "Opening + cash sales − cash out")
        self.chart.set_series(data["series"])
        self.services.set_rows(data["top_services"])
        self.deals.set_rows(data["top_deals"])
        names = [row["name"] for row in data["low_stock"][:4]]
        self.low_stock.setText("Low stock: " + ", ".join(names) if names else "")
        self.recent_rows = data["recent"]
        fill_table(
            self.table,
            ["Invoice", "When", "Client", "Payment", "Total", "Status"],
            [
                [
                    row["invoice_no"],
                    format_dt(row["created_at"]),
                    row["customer_name"],
                    row["payment_mode"],
                    money(row["total"]),
                    "Void" if row["status"] == "void" else "Paid",
                ]
                for row in self.recent_rows
            ],
        )

    def _open_bill(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.recent_rows):
            return
        invoice = self.host.db.get_invoice(self.recent_rows[row]["id"])
        if invoice:
            ReceiptDialog(invoice, self.host.db.get_settings(), self).exec()


class RevenueChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.series = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.bars = _Bars()
        layout.addWidget(self.bars)
        self._chart_view = None

    def _theme(self) -> str:
        from PySide6.QtWidgets import QApplication

        return QApplication.instance().property("caveronTheme") or "dark"

    def set_series(self, series: list[dict]) -> None:
        self.series = series
        self.bars.series = series
        self.bars.update()
        if self._chart_view is not None:
            self._chart_view.setParent(None)
            self._chart_view.deleteLater()
            self._chart_view = None
        if HAS_CHARTS and series:
            labels = [_label(row["date"], len(series)) for row in series]
            bar = QBarSet("Revenue")
            bar.setColor(QColor("#C9A96E"))
            for row in series:
                bar.append(float(row["total"]))
            chart_series = QBarSeries()
            chart_series.append(bar)
            chart = QChart()
            chart.addSeries(chart_series)
            colors = theme_colors(self._theme())
            chart.setBackgroundBrush(QColor(colors["card"]))
            chart.setTitle("")
            chart.legend().hide()
            axis_x = QBarCategoryAxis()
            axis_x.append(labels)
            axis_x.setLabelsColor(QColor(colors["muted"]))
            if len(labels) > 10:
                axis_x.setLabelsAngle(-60)
            axis_y = QValueAxis()
            peak = max((float(row["total"]) for row in series), default=0)
            axis_y.setRange(0, max(1, peak * 1.15))
            axis_y.setLabelsColor(QColor(colors["muted"]))
            axis_y.setGridLineColor(QColor(colors["line"]))
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            chart_series.attachAxis(axis_x)
            chart_series.attachAxis(axis_y)
            chart.setBackgroundRoundness(0)
            view = QChartView(chart)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setStyleSheet("background: transparent; border: none;")
            self.layout().addWidget(view)
            self._chart_view = view
            self.bars.hide()
        else:
            self.bars.show()


class _Bars(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.series = []

    def paintEvent(self, _event):
        if not self.series:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(12, 12, -12, -28)
        peak = max((float(row["total"]) for row in self.series), default=1) or 1
        gap = 8
        bar_width = max(6, (rect.width() - gap * len(self.series)) / max(1, len(self.series)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#C9A96E"))
        for index, row in enumerate(self.series):
            height = rect.height() * float(row["total"]) / peak
            painter.drawRoundedRect(int(rect.x() + index * (bar_width + gap)), int(rect.bottom() - height), int(bar_width), int(height), 3, 3)
        painter.end()


def _label(iso: str, count: int) -> str:
    from datetime import date

    value = date.fromisoformat(iso)
    if count > 10:
        return value.strftime("%d %b")
    return value.strftime("%a %d")


class RankList(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        heading = QLabel(title)
        heading.setObjectName("eyebrow")
        self.layout.addWidget(heading)
        self.body = QVBoxLayout()
        self.layout.addLayout(self.body)
        self.layout.addStretch()

    def set_rows(self, rows: list[dict]) -> None:
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not rows:
            empty = QLabel("No sales in this range yet.")
            empty.setObjectName("muted")
            self.body.addWidget(empty)
            return
        peak = max(float(row["revenue"] or 0) for row in rows) or 1
        for row in rows:
            name = QLabel(f"{row['name']}   ·   {int(row['qty'])}   ·   {money(row['revenue'])}")
            name.setWordWrap(True)
            bar = QFrame()
            bar.setFixedHeight(4)
            width = max(8, int(220 * float(row["revenue"] or 0) / peak))
            bar.setFixedWidth(width)
            bar.setStyleSheet("background: #C9A96E; border-radius: 2px;")
            self.body.addWidget(name)
            self.body.addWidget(bar)
