#!/usr/bin/env python3
"""
Midaxas Finance - single-file polished app with custom title bar (frameless)

This single-file app includes:
 - Custom frameless TitleBar (removes native white title bar)
 - theme (QSS) applied at startup
 - non-blocking Toast notifications
 - fade-in animations on page switches
 - TransactionModel (QAbstractTableModel) + QTableView for history
 - optional interactive chart on the Dashboard (pyqtgraph if installed)
 - optional qtawesome icons (if installed)

Requirements:
 - Python 3.9+ (works with modern 3.x, tested with PySide6)
 - PySide6

Optional:
 - pyqtgraph (pip install pyqtgraph) for charts
 - qtawesome (pip install qtawesome) for icons

Run:
    pip install PySide6
    python Tracker.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPropertyAnimation,
    QPoint,
    QEasingCurve,
    Qt,
    QTimer,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QTableView,
    QHeaderView,
    QGraphicsOpacityEffect,
    QInputDialog,
)

# Optional imports
try:
    import qtawesome as qta  # type: ignore
except Exception:
    qta = None

try:
    import pyqtgraph as pg  # type: ignore
    from pyqtgraph import PlotWidget  # type: ignore
except Exception:
    pg = None
    PlotWidget = None

# ------------------------------
# Config / Data file locations
# ------------------------------
DATA_FILE = "transactions.json"
SETTINGS_FILE = "settings.json"

# ------------------------------
# Theme (QSS) (embedded)
# ------------------------------
THEME_QSS = r"""
/* Minimal dark theme */
QWidget {
    background-color: #0f1724;
    color: #e6eef3;
    font-family: "Segoe UI", "Helvetica Neue", "Arial";
    font-size: 13px;
}
QLabel#title {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}
QGroupBox, QFrame {
    background-color: #0b1220;
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 8px;
    padding: 8px;
}
QPushButton {
    background-color: #16222b;
    color: #e6eef3;
    border: 1px solid rgba(255,255,255,0.04);
    padding: 6px 10px;
    border-radius: 8px;
}
QPushButton#primary {
    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #3ddc84, stop:1 #2cc67a);
    color: #062017;
    font-weight: 600;
    border: none;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    background-color: #07121a;
    border: 1px solid rgba(255,255,255,0.04);
    padding: 6px;
    border-radius: 6px;
    color: #e6eef3;
}
QTableView, QHeaderView {
    background-color: #07121a;
    border: none;
    gridline-color: rgba(255,255,255,0.03);
}
QHeaderView::section {
    background-color: transparent;
    color: #9aa7b2;
    padding: 6px;
}
#toast {
    background-color: rgba(20, 30, 40, 0.95);
    color: #e6eef3;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.04);
}
.titlebar-btn {
    background: transparent;
    color: #e6eef3;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
}
.titlebar-btn:hover { background: rgba(255,255,255,0.04); }
.titlebar-btn#close:hover { background: #ff6b6b; color: #fff; }
"""

# ------------------------------
# Small utilities
# ------------------------------
def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        # If corrupted, return default; caller may want to alert user.
        return default


def save_json_atomic(path: str, data) -> None:
    """
    Write JSON atomically to avoid partial file writes that may corrupt the file.
    """
    dirpath = os.path.dirname(path) or "."
    os.makedirs(dirpath, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def save_json(path: str, data) -> None:
    save_json_atomic(path, data)


def hash_pin(pin: str) -> str:
    # Note: This uses plain SHA-256 for compatibility with v1. Consider PBKDF2/Argon2 for improved security.
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


# ------------------------------
# Core logic (unchanged)
# ------------------------------
def load_transactions() -> List[Dict[str, Any]]:
    return load_json(DATA_FILE, [])


def save_transactions(txs: List[Dict[str, Any]]) -> None:
    save_json(DATA_FILE, txs)


def load_settings() -> Dict[str, Any]:
    return load_json(SETTINGS_FILE, {"pin_hash": None, "budgets": {}})


def save_settings(settings: Dict[str, Any]) -> None:
    save_json(SETTINGS_FILE, settings)


def totals(txs: List[Dict[str, Any]]) -> Dict[str, float]:
    income = sum(float(t.get("amount", 0.0)) for t in txs if t.get("type") == "income")
    expenses = sum(float(t.get("amount", 0.0)) for t in txs if t.get("type") == "expense")
    return {"income": income, "expenses": expenses, "net": income - expenses}


def totals_by_category(txs: List[Dict[str, Any]], ttype: Optional[str] = None) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for t in txs:
        if ttype and t.get("type") != ttype:
            continue
        cat = t.get("category", "Uncategorized")
        try:
            amt = float(t.get("amount", 0.0))
        except Exception:
            amt = 0.0
        out[cat] = out.get(cat, 0.0) + amt
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0].lower())))


def filter_month(txs: List[Dict[str, Any]], year: int, month: int) -> List[Dict[str, Any]]:
    prefix = f"{year:04d}-{month:02d}-"
    return [t for t in txs if str(t.get("date", "")).startswith(prefix)]


def rating_from_net(net_savings: float) -> Dict[str, Any]:
    points = 0
    if net_savings > 0:
        points += 1
    if net_savings > 100:
        points += 1
    if net_savings > 500:
        points += 1
    if net_savings > 1000:
        points += 1
    if net_savings > 10000:
        points += 6

    if points == 10:
        return {"points": points, "label": "Perfect", "message": "This means your savings are perfect."}
    elif points >= 5:
        return {"points": points, "label": "Average", "message": "This means your savings are average."}
    else:
        return {"points": points, "label": "Poor", "message": "Your savings are in poor condition."}


# ------------------------------
# UI Helpers (Toast, fade)
# ------------------------------
class Toast(QWidget):
    """Non-blocking toast message."""

    def __init__(self, parent: QWidget, message: str, duration: int = 1800):
        super().__init__(parent, flags=Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.duration = duration
        self._build_ui(message)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)

    def _build_ui(self, message: str):
        self.setObjectName("toast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        self.adjustSize()

    def show_(self):
        parent = self.parentWidget()
        if parent is None:
            screen_geo = QApplication.primaryScreen().availableGeometry()
            x = screen_geo.right() - self.width() - 24
            y = screen_geo.bottom() - self.height() - 24
            self.move(x, y)
        else:
            rect = parent.geometry()
            x = rect.right() - self.width() - 24
            y = rect.bottom() - self.height() - 24
            self.move(x, y)
        self.setWindowOpacity(0.0)
        super().show()
        self._fade.setDirection(QPropertyAnimation.Forward)
        self._fade.start()
        QTimer.singleShot(self.duration, self.close_with_fade)

    def close_with_fade(self):
        self._fade.setDirection(QPropertyAnimation.Backward)
        self._fade.finished.connect(self.close)
        self._fade.start()


def fade_in_widget(widget: QWidget, duration: int = 300):
    """
    Apply a simple opacity fade-in to a widget. Useful for page transitions.
    """
    try:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
    except Exception:
        pass


def load_stylesheet_from_string(app: QApplication, qss: str):
    try:
        app.setStyleSheet(qss)
    except Exception:
        pass


# ------------------------------
# Custom Title Bar (frameless window)
# ------------------------------
class TitleBar(QWidget):
    """
    Custom title bar with drag-to-move and control buttons.
    """

    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self._parent = parent
        self._drag_pos: Optional[QPoint] = None
        self._is_maximized = False

        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(6)

        # Title
        self.lbl_title = QLabel(self._parent.windowTitle(), self)
        self.lbl_title.setObjectName("title")
        self.lbl_title.setMinimumWidth(120)
        lay.addWidget(self.lbl_title)
        lay.addStretch(1)

        # optional refresh button
        self.btn_refresh = QPushButton("⟳", self)
        self.btn_refresh.setObjectName("refresh")
        self.btn_refresh.setFixedSize(30, 26)
        self.btn_refresh.clicked.connect(lambda: getattr(self._parent, "refresh_all", lambda: None)())
        lay.addWidget(self.btn_refresh)

        # Minimize, Maximize/Restore, Close
        self.btn_min = QPushButton("▁", self)
        self.btn_min.setObjectName("min")
        self.btn_min.setFixedSize(36, 26)
        self.btn_min.clicked.connect(self._parent.showMinimized)
        lay.addWidget(self.btn_min)

        self.btn_max = QPushButton("▢", self)
        self.btn_max.setObjectName("max")
        self.btn_max.setFixedSize(36, 26)
        self.btn_max.clicked.connect(self.toggle_max_restore)
        lay.addWidget(self.btn_max)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setObjectName("close")
        self.btn_close.setFixedSize(36, 26)
        self.btn_close.clicked.connect(self._parent.close)
        lay.addWidget(self.btn_close)

        self.setStyleSheet("")  # global QSS handles styling

    def update_title(self, text: str):
        self.lbl_title.setText(text)

    def toggle_max_restore(self):
        if self._is_maximized:
            self._parent.showNormal()
            self._is_maximized = False
            self.btn_max.setText("▢")
        else:
            self._parent.showMaximized()
            self._is_maximized = True
            self.btn_max.setText("❐")

    # Helper to get a QPoint from the event in a version-safe way
    @staticmethod
    def _global_point_from_event(event):
        try:
            # Qt 6.5+: globalPosition returns QPointF
            return event.globalPosition().toPoint()
        except Exception:
            try:
                # older API
                return event.globalPos()
            except Exception:
                return QPoint()

    # Mouse handling for dragging the window
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = self._global_point_from_event(event) - self._parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self._parent.move(self._global_point_from_event(event) - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_max_restore()
            event.accept()


# ------------------------------
# TransactionModel for History
# ------------------------------
class TransactionModel(QAbstractTableModel):
    HEADERS = ["Date", "Type", "Amount", "Category", "Note", "Created", "ID"]

    def __init__(self, txs: Optional[List[Dict[str, Any]]] = None):
        super().__init__()
        self.txs: List[Dict[str, Any]] = txs or []

    def rowCount(self, parent=QModelIndex()):
        return len(self.txs)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        t = self.txs[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return str(t.get("date", ""))
            if col == 1:
                return str(t.get("type", ""))
            if col == 2:
                try:
                    return f"{float(t.get('amount', 0.0)):.2f}"
                except Exception:
                    return "0.00"
            if col == 3:
                return str(t.get("category", ""))
            if col == 4:
                return str(t.get("note", ""))
            if col == 5:
                return str(t.get("created_at", ""))
            if col == 6:
                return str(t.get("id", ""))
        if role == Qt.TextAlignmentRole:
            if col == 2:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def sort(self, column, order):
        key_map = {
            0: lambda t: t.get("date", ""),
            1: lambda t: t.get("type", ""),
            2: lambda t: float(t.get("amount", 0.0)),
            3: lambda t: t.get("category", ""),
            4: lambda t: t.get("note", ""),
            5: lambda t: t.get("created_at", ""),
            6: lambda t: t.get("id", ""),
        }
        key = key_map.get(column, lambda t: "")
        self.layoutAboutToBeChanged.emit()
        self.txs.sort(key=key, reverse=(order == Qt.DescendingOrder))
        self.layoutChanged.emit()

    def update(self, txs: List[Dict[str, Any]]):
        self.beginResetModel()
        self.txs = txs
        self.endResetModel()


# ------------------------------
# Chart Widget (optional)
# ------------------------------
class ChartWidget(QWidget):
    """
    Small chart for dashboard. If pyqtgraph is installed it will show an interactive
    line chart; otherwise it falls back to a simple textual summary.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if PlotWidget and pg:
            self.plot = PlotWidget(background="transparent")
            self.plot.setBackground(None)
            try:
                self.plot.showGrid(x=True, y=True, alpha=0.2)
                self.plot.getPlotItem().getAxis("left").setPen(pg.mkPen("#9aa7b2"))
                self.plot.getPlotItem().getAxis("bottom").setPen(pg.mkPen("#9aa7b2"))
            except Exception:
                pass
            self.plot.setTitle("Net Savings Over Time", color="#e6eef3", size="12pt")
            self.net_curve = self.plot.plot([], [], pen=pg.mkPen("#3ddc84", width=2), name="Net")
            self.income_curve = self.plot.plot([], [], pen=pg.mkPen("#6eb0ff", width=2), name="Income")
            self.expense_curve = self.plot.plot([], [], pen=pg.mkPen("#ff6b6b", width=2), name="Expenses")
            layout.addWidget(self.plot)
        else:
            self.label = QLabel("Install 'pyqtgraph' for an interactive chart.")
            layout.addWidget(self.label)

    def update_data(self, points: List[Tuple[str, float, float, float]]):
        if not pg or not PlotWidget:
            return
        xs = list(range(len(points)))
        nets = [p[1] for p in points]
        incs = [p[2] for p in points]
        exps = [p[3] for p in points]
        self.net_curve.setData(xs, nets)
        self.income_curve.setData(xs, incs)
        self.expense_curve.setData(xs, exps)
        # show last 12
        rng = max(0, len(points) - 12)
        self.plot.getPlotItem().setXRange(rng, len(points))


# ------------------------------
# Main Application Window
# ------------------------------
class FinanceTrackerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midaxas Finance")
        self.resize(980, 640)

        # Remove native title bar (frameless)
        self.setWindowFlag(Qt.FramelessWindowHint)

        # Data
        self.settings = load_settings()
        if self.settings.get("pin_hash"):
            if not self.prompt_pin():
                QMessageBox.critical(self, "Locked", "Too many attempts. Exiting.")
                raise SystemExit

        self.txs: List[Dict[str, Any]] = load_transactions()

        # Central widget with stacked pages
        container = QWidget()
        self.setCentralWidget(container)
        self.stack = QStackedWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar (keeps the single refresh icon)
        self.titlebar = TitleBar(self)
        main_layout.addWidget(self.titlebar)

        # small spacing between titlebar and UI content (no duplicate title / refresh)
        main_layout.addSpacing(6)

        main_layout.addWidget(self.stack)

        # Pages
        self.page_dashboard = QWidget()
        self.page_add = QWidget()
        self.page_history = QWidget()
        self.page_summary = QWidget()
        self.page_month = QWidget()
        self.page_budgets = QWidget()
        self.page_export = QWidget()
        self.page_settings = QWidget()

        for p in (
            self.page_dashboard,
            self.page_add,
            self.page_history,
            self.page_summary,
            self.page_month,
            self.page_budgets,
            self.page_export,
            self.page_settings,
        ):
            self.stack.addWidget(p)

        # Navigation row
        nav = QHBoxLayout()
        nav.setContentsMargins(12, 8, 12, 8)
        names = [
            ("Dashboard", 0),
            ("Add", 1),
            ("History", 2),
            ("Summary", 3),
            ("Monthly", 4),
            ("Budgets", 5),
            ("Export", 6),
            ("Settings", 7),
        ]
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        for title, idx in names:
            b = QPushButton(title)
            b.clicked.connect(lambda checked, i=idx: self.switch_page(i))
            nav_layout.addWidget(b)
        nav_layout.addStretch(1)
        main_layout.addWidget(nav_widget)

        # Build pages
        self.build_dashboard()
        self.build_add()
        self.build_history()
        self.build_summary()
        self.build_monthly()
        self.build_budgets()
        self.build_export()
        self.build_settings()

        # Start on dashboard
        self.switch_page(0, animate=False)
        self.refresh_all()

        # Menubar actions (kept for keyboard/menu use)
        self._add_menu()

    def _add_menu(self):
        menu = self.menuBar()
        filemenu = menu.addMenu("&File")
        act_export = QAction("Export CSV…", self)
        act_export.triggered.connect(self.export_csv)
        filemenu.addAction(act_export)
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        filemenu.addAction(act_quit)

    # ---------- PIN ----------
    def prompt_pin(self) -> bool:
        for _ in range(3):
            pin, ok = QInputDialog.getText(self, "PIN Required", "Enter PIN:", QLineEdit.Password)
            if not ok:
                return False
            if hash_pin(pin) == self.settings.get("pin_hash"):
                return True
            QMessageBox.warning(self, "Wrong PIN", "Wrong PIN.")
        return False

    # ---------- helpers ----------
    def save(self):
        save_transactions(self.txs)
        save_settings(self.settings)

    def refresh_all(self):
        self.refresh_dashboard()
        self.refresh_history()
        self.refresh_summary()
        self.refresh_budget_view()
        self.refresh_monthly_report()

    def show_error(self, msg: str):
        Toast(self, msg, duration=2200).show_()

    def show_info(self, msg: str):
        Toast(self, msg, duration=1400).show_()

    def switch_page(self, index: int, animate: bool = True):
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
            if animate:
                fade_in_widget(self.stack.currentWidget(), duration=320)

    # ---------- Dashboard ----------
    def build_dashboard(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_dashboard.setLayout(layout)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>Dashboard</h2>"))
        header.addStretch(1)
        layout.addLayout(header)

        stats_box = QGroupBox()
        sb_layout = QVBoxLayout()
        stats_box.setLayout(sb_layout)

        self.lbl_totals = QLabel("")
        self.lbl_totals.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_rating = QLabel("")
        self.lbl_rating.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_budget_warnings = QLabel("")
        self.lbl_budget_warnings.setWordWrap(True)
        self.lbl_budget_warnings.setTextInteractionFlags(Qt.TextSelectableByMouse)

        sb_layout.addWidget(self.lbl_totals)
        sb_layout.addWidget(self.lbl_rating)
        sb_layout.addWidget(QLabel("<b>Budget warnings (this month):</b>"))
        sb_layout.addWidget(self.lbl_budget_warnings)
        layout.addWidget(stats_box)

        # Chart
        self.chart = ChartWidget()
        layout.addWidget(self.chart)

    def refresh_dashboard(self):
        t = totals(self.txs)
        self.lbl_totals.setText(
            f"<b>Total Income:</b> {t['income']:.2f}<br>"
            f"<b>Total Expenses:</b> {t['expenses']:.2f}<br>"
            f"<b>Net (Savings):</b> {t['net']:.2f}"
        )
        r = rating_from_net(t["net"])
        self.lbl_rating.setText(f"<b>Rating:</b> {r['label']} (points: {r['points']}) — {r['message']}")

        # Budget warnings for current month
        y, m = date.today().year, date.today().month
        month_txs = filter_month(self.txs, y, m)
        budgets = self.settings.get("budgets", {}) or {}
        if not budgets:
            self.lbl_budget_warnings.setText("No budgets set.")
        else:
            spent = totals_by_category(month_txs, ttype="expense")
            lines = []
            for cat, limit in budgets.items():
                try:
                    limit_val = float(limit)
                except Exception:
                    limit_val = 0.0
                if limit_val <= 0:
                    continue
                used = spent.get(cat, 0.0)
                pct = (used / limit_val) * 100.0 if limit_val else 0.0
                if pct >= 100:
                    lines.append(f"OVER: {cat} — {used:.2f}/{limit_val:.2f} ({pct:.0f}%)")
                elif pct >= 80:
                    lines.append(f"Near: {cat} — {used:.2f}/{limit_val:.2f} ({pct:.0f}%)")
            self.lbl_budget_warnings.setText("\n".join(lines) if lines else "All budgets look OK.")

        # Update chart - produce last 12 months aggregates
        points = []
        today = date.today()
        for i in range(11, -1, -1):
            month_index = (today.month - i - 1)
            year = today.year + (month_index // 12)
            mth = (month_index % 12) + 1
            subset = filter_month(self.txs, year, mth)
            tsub = totals(subset)
            points.append((f"{year:04d}-{mth:02d}", tsub["net"], tsub["income"], tsub["expenses"]))
        self.chart.update_data(points)

    # ---------- Add ----------
    def build_add(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_add.setLayout(layout)
        layout.addWidget(QLabel("<h2>Add Transaction</h2>"))

        form = QFormLayout()
        self.cmb_type = QLineEdit()
        self.cmb_type.setPlaceholderText("income or expense (default: expense)")
        self.txt_date = QLineEdit()
        self.txt_date.setPlaceholderText("YYYY-MM-DD (leave empty for today)")
        self.spn_amount = QDoubleSpinBox()
        self.spn_amount.setRange(0.01, 1e12)
        self.spn_amount.setDecimals(2)
        self.spn_amount.setSingleStep(10.0)
        self.txt_category = QLineEdit()
        self.txt_category.setPlaceholderText("e.g. Food, Rent, Salary")
        self.txt_note = QLineEdit()
        self.txt_note.setPlaceholderText("optional")

        form.addRow("Type:", self.cmb_type)
        form.addRow("Date:", self.txt_date)
        form.addRow("Amount:", self.spn_amount)
        form.addRow("Category:", self.txt_category)
        form.addRow("Note:", self.txt_note)

        btns = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.add_tx)
        btn_clear = QPushButton("Clear Fields")
        btn_clear.clicked.connect(self.clear_add_fields)
        btns.addWidget(btn_add)
        btns.addWidget(btn_clear)
        btns.addStretch(1)

        layout.addLayout(form)
        layout.addLayout(btns)

    def clear_add_fields(self):
        self.txt_date.clear()
        self.spn_amount.setValue(10.0)
        self.txt_category.clear()
        self.txt_note.clear()
        self.cmb_type.clear()

    def add_tx(self):
        ttype = self.cmb_type.text().strip().lower() or "expense"
        if ttype not in ("income", "expense"):
            self.show_error("Type must be 'income' or 'expense'.")
            return

        d = self.txt_date.text().strip()
        if not d:
            d = date.today().isoformat()
        else:
            try:
                d = datetime.strptime(d, "%Y-%m-%d").date().isoformat()
            except ValueError:
                self.show_error("Invalid date. Use YYYY-MM-DD.")
                return

        amount = float(self.spn_amount.value())
        if amount <= 0:
            self.show_error("Amount must be > 0.")
            return

        category = self.txt_category.text().strip() or "Uncategorized"
        note = self.txt_note.text().strip()

        tx = {
            "id": int(time.time() * 1000),
            "date": d,
            "type": ttype,
            "amount": amount,
            "category": category,
            "note": note,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.txs.append(tx)
        self.save()
        self.refresh_all()
        self.show_info("Saved ✅")
        self.clear_add_fields()
        self.switch_page(0)

    # ---------- History ----------
    def build_history(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_history.setLayout(layout)
        layout.addWidget(QLabel("<h2>History</h2>"))

        row = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_history)
        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(self.delete_selected)
        row.addWidget(btn_refresh)
        row.addWidget(btn_delete)
        row.addStretch(1)
        layout.addLayout(row)

        self.table = QTableView()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        # Use QAbstractItemView enum for selection behavior and mode:
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        self.model = TransactionModel([])
        self.table.setModel(self.model)
        # hide the ID column visually (but keep it in model)
        self.table.setColumnHidden(6, True)

    def refresh_history(self):
        data = sorted(self.txs, key=lambda x: (x.get("date", ""), x.get("created_at", "")), reverse=True)
        self.model.update(data)

    def selected_tx_id(self) -> Optional[int]:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        index = sel[0]
        model_index = index.siblingAtColumn(6)
        txid = self.model.data(model_index, Qt.DisplayRole)
        try:
            return int(txid)
        except Exception:
            return None

    def delete_selected(self):
        tx_id = self.selected_tx_id()
        if tx_id is None:
            self.show_info("Select a row first.")
            return
        if QMessageBox.question(self, "Confirm", "Delete selected transaction?") != QMessageBox.Yes:
            return
        self.txs = [t for t in self.txs if int(t.get("id", -1)) != tx_id]
        self.save()
        self.refresh_all()
        self.show_info("Deleted ✅")

    # ---------- Summary ----------
    def build_summary(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_summary.setLayout(layout)
        layout.addWidget(QLabel("<h2>Summary</h2>"))

        self.lbl_summary = QLabel("")
        self.lbl_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.txt_exp_cat = QTextEdit()
        self.txt_exp_cat.setReadOnly(True)

        self.txt_inc_cat = QTextEdit()
        self.txt_inc_cat.setReadOnly(True)

        layout.addWidget(self.lbl_summary)
        layout.addWidget(QLabel("<b>Expenses by category</b>"))
        layout.addWidget(self.txt_exp_cat)
        layout.addWidget(QLabel("<b>Income by category</b>"))
        layout.addWidget(self.txt_inc_cat)

    def refresh_summary(self):
        t = totals(self.txs)
        self.lbl_summary.setText(
            f"<b>Total Income:</b> {t['income']:.2f} &nbsp;&nbsp; "
            f"<b>Total Expenses:</b> {t['expenses']:.2f} &nbsp;&nbsp; "
            f"<b>Net:</b> {t['net']:.2f}"
        )
        exp = totals_by_category(self.txs, "expense")
        inc = totals_by_category(self.txs, "income")

        self.txt_exp_cat.setPlainText("\n".join([f"{k}: {v:.2f}" for k, v in exp.items()]) or "(none)")
        self.txt_inc_cat.setPlainText("\n".join([f"{k}: {v:.2f}" for k, v in inc.items()]) or "(none)")

    # ---------- Monthly ----------
    def build_monthly(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_month.setLayout(layout)
        layout.addWidget(QLabel("<h2>Monthly Report</h2>"))

        row = QHBoxLayout()
        self.spn_year = QSpinBox()
        self.spn_year.setRange(2000, 2100)
        self.spn_year.setValue(date.today().year)
        self.spn_month = QSpinBox()
        self.spn_month.setRange(1, 12)
        self.spn_month.setValue(date.today().month)

        btn = QPushButton("Generate")
        btn.clicked.connect(self.refresh_monthly_report)

        row.addWidget(QLabel("Year:"))
        row.addWidget(self.spn_year)
        row.addWidget(QLabel("Month:"))
        row.addWidget(self.spn_month)
        row.addWidget(btn)
        row.addStretch(1)

        self.txt_month = QTextEdit()
        self.txt_month.setReadOnly(True)

        layout.addLayout(row)
        layout.addWidget(self.txt_month)

    def refresh_monthly_report(self):
        y = int(self.spn_year.value())
        m = int(self.spn_month.value())
        subset = filter_month(self.txs, y, m)
        if not subset:
            self.txt_month.setPlainText("No transactions for that month.")
            return
        t = totals(subset)
        top = list(totals_by_category(subset, "expense").items())[:10]
        lines = [
            f"Report for {y:04d}-{m:02d}",
            f"Income : {t['income']:.2f}",
            f"Expense: {t['expenses']:.2f}",
            f"Net    : {t['net']:.2f}",
            "",
            "Top expense categories:",
        ]
        for cat, amt in top:
            lines.append(f"  {cat}: {amt:.2f}")
        self.txt_month.setPlainText("\n".join(lines))

    # ---------- Budgets ----------
    def build_budgets(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_budgets.setLayout(layout)
        layout.addWidget(QLabel("<h2>Budgets</h2>"))

        form = QFormLayout()
        self.txt_budget_cat = QLineEdit()
        self.spn_budget_amt = QDoubleSpinBox()
        self.spn_budget_amt.setRange(0.01, 1e12)
        self.spn_budget_amt.setDecimals(2)
        self.spn_budget_amt.setSingleStep(10.0)

        form.addRow("Category:", self.txt_budget_cat)
        form.addRow("Monthly budget:", self.spn_budget_amt)

        btn_row = QHBoxLayout()
        btn_set = QPushButton("Set / Update Budget")
        btn_set.clicked.connect(self.set_budget)
        btn_remove = QPushButton("Remove Budget")
        btn_remove.clicked.connect(self.remove_budget)
        btn_row.addWidget(btn_set)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch(1)

        self.txt_budgets = QTextEdit()
        self.txt_budgets.setReadOnly(True)

        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addWidget(QLabel("<b>Current budgets</b>"))
        layout.addWidget(self.txt_budgets)

    def refresh_budget_view(self):
        budgets = self.settings.get("budgets", {}) or {}
        if not budgets:
            self.txt_budgets.setPlainText("(none)")
            return
        lines = [f"{k}: {float(v):.2f}" for k, v in sorted(budgets.items(), key=lambda kv: kv[0].lower())]
        self.txt_budgets.setPlainText("\n".join(lines))

    def set_budget(self):
        cat = self.txt_budget_cat.text().strip()
        if not cat:
            self.show_error("Category is required.")
            return
        amt = float(self.spn_budget_amt.value())
        if amt <= 0:
            self.show_error("Budget must be > 0.")
            return
        budgets = self.settings.get("budgets", {}) or {}
        budgets[cat] = amt
        self.settings["budgets"] = budgets
        self.save()
        self.refresh_all()
        self.show_info("Budget saved ✅")

    def remove_budget(self):
        cat = self.txt_budget_cat.text().strip()
        budgets = self.settings.get("budgets", {}) or {}
        if cat in budgets:
            budgets.pop(cat)
            self.settings["budgets"] = budgets
            self.save()
            self.refresh_all()
            self.show_info("Removed ✅")
        else:
            self.show_info("Category not found in budgets.")

    # ---------- Export ----------
    def build_export(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_export.setLayout(layout)
        layout.addWidget(QLabel("<h2>Export</h2>"))
        btn = QPushButton("Export CSV…")
        btn.clicked.connect(self.export_csv)
        layout.addWidget(btn)

    def export_csv(self):
        if not self.txs:
            self.show_info("No transactions to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "export.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "date", "type", "amount", "category", "note", "created_at"])
                for t in sorted(self.txs, key=lambda x: (x.get("date", ""), x.get("created_at", ""))):
                    w.writerow(
                        [
                            t.get("id"),
                            t.get("date"),
                            t.get("type"),
                            t.get("amount"),
                            t.get("category"),
                            t.get("note", ""),
                            t.get("created_at", ""),
                        ]
                    )
            self.show_info("Exported ✅")
        except Exception as exc:
            self.show_error(f"Export failed: {exc}")

    # ---------- Settings ----------
    def build_settings(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        self.page_settings.setLayout(layout)
        layout.addWidget(QLabel("<h2>Settings</h2>"))

        btn_set_pin = QPushButton("Set / Change PIN")
        btn_set_pin.clicked.connect(self.set_pin)
        btn_clear_pin = QPushButton("Remove PIN")
        btn_clear_pin.clicked.connect(self.remove_pin)

        layout.addWidget(btn_set_pin)
        layout.addWidget(btn_clear_pin)

    def set_pin(self):
        if self.settings.get("pin_hash"):
            old, ok = QInputDialog.getText(self, "Current PIN", "Enter current PIN:", QLineEdit.Password)
            if not ok:
                return
            if hash_pin(old) != self.settings["pin_hash"]:
                self.show_error("Wrong PIN.")
                return

        new1, ok = QInputDialog.getText(self, "New PIN", "Enter new PIN:", QLineEdit.Password)
        if not ok or not new1:
            return
        new2, ok = QInputDialog.getText(self, "Confirm PIN", "Confirm new PIN:", QLineEdit.Password)
        if not ok:
            return
        if new1 != new2:
            self.show_error("PINs do not match.")
            return

        self.settings["pin_hash"] = hash_pin(new1)
        self.save()
        self.show_info("PIN updated ✅")

    def remove_pin(self):
        if not self.settings.get("pin_hash"):
            self.show_info("No PIN is set.")
            return
        old, ok = QInputDialog.getText(self, "Remove PIN", "Enter current PIN:", QLineEdit.Password)
        if not ok:
            return
        if hash_pin(old) != self.settings["pin_hash"]:
            self.show_error("Wrong PIN.")
            return
        self.settings["pin_hash"] = None
        self.save()
        self.show_info("PIN removed ✅")

    # ---------- actions ----------
    def undo_last(self):
        if not self.txs:
            self.show_info("Nothing to undo.")
            return
        last = sorted(self.txs, key=lambda x: x.get("created_at", ""), reverse=True)[0]
        if QMessageBox.question(self, "Confirm", f"Undo last transaction?\n\n{last}") != QMessageBox.Yes:
            return
        self.txs = [t for t in self.txs if int(t.get("id", -1)) != int(last.get("id"))]
        self.save()
        self.refresh_all()
        self.show_info("Undone ✅")

    def reset_all(self):
        if QMessageBox.question(self, "Confirm", "Delete ALL transactions?") != QMessageBox.Yes:
            return
        self.txs.clear()
        self.save()
        self.refresh_all()
        self.show_info("All data cleared ✅")


def main():
    app = QApplication(sys.argv)
    load_stylesheet_from_string(app, THEME_QSS)
    win = FinanceTrackerGUI()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
