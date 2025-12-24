import sys
import json
import csv
import time
import hashlib
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QFileDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QGroupBox,
    QInputDialog
)

DATA_FILE = "transactions.json"
SETTINGS_FILE = "settings.json"


# ---------------- persistence ----------------
def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_transactions() -> List[Dict[str, Any]]:
    return load_json(DATA_FILE, [])


def save_transactions(txs: List[Dict[str, Any]]) -> None:
    save_json(DATA_FILE, txs)


def load_settings() -> Dict[str, Any]:
    return load_json(SETTINGS_FILE, {"pin_hash": None, "budgets": {}})


def save_settings(settings: Dict[str, Any]) -> None:
    save_json(SETTINGS_FILE, settings)


# ---------------- core logic ----------------
def totals(txs: List[Dict[str, Any]]) -> Dict[str, float]:
    income = sum(t["amount"] for t in txs if t["type"] == "income")
    expenses = sum(t["amount"] for t in txs if t["type"] == "expense")
    return {"income": income, "expenses": expenses, "net": income - expenses}


def totals_by_category(txs: List[Dict[str, Any]], ttype: Optional[str] = None) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for t in txs:
        if ttype and t["type"] != ttype:
            continue
        out[t["category"]] = out.get(t["category"], 0.0) + float(t["amount"])
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0].lower())))


def filter_month(txs: List[Dict[str, Any]], year: int, month: int) -> List[Dict[str, Any]]:
    prefix = f"{year:04d}-{month:02d}-"
    return [t for t in txs if t["date"].startswith(prefix)]


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


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


# ---------------- GUI ----------------
class FinanceTrackerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midaxas Finance")
        self.resize(980, 640)

        self.settings = load_settings()
        if self.settings.get("pin_hash"):
            if not self.prompt_pin():
                QMessageBox.critical(self, "Locked", "Too many attempts. Exiting.")
                raise SystemExit

        self.txs: List[Dict[str, Any]] = load_transactions()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_dashboard = QWidget()
        self.tab_add = QWidget()
        self.tab_history = QWidget()
        self.tab_summary = QWidget()
        self.tab_month = QWidget()
        self.tab_budgets = QWidget()
        self.tab_export = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_dashboard, "Dashboard")
        self.tabs.addTab(self.tab_add, "Add")
        self.tabs.addTab(self.tab_history, "History")
        self.tabs.addTab(self.tab_summary, "Summary")
        self.tabs.addTab(self.tab_month, "Monthly")
        self.tabs.addTab(self.tab_budgets, "Budgets")
        self.tabs.addTab(self.tab_export, "Export")
        self.tabs.addTab(self.tab_settings, "Settings")

        self.build_dashboard()
        self.build_add()
        self.build_history()
        self.build_summary()
        self.build_monthly()
        self.build_budgets()
        self.build_export()
        self.build_settings()

        self.refresh_all()

    # ---------- PIN ----------
    def prompt_pin(self) -> bool:
        for _ in range(3):
            pin, ok = QInputDialog.getText(self, "PIN Required", "Enter PIN:", QLineEdit.Password)
            if not ok:
                return False
            if hash_pin(pin) == self.settings["pin_hash"]:
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
        QMessageBox.critical(self, "Error", msg)

    def show_info(self, msg: str):
        QMessageBox.information(self, "Info", msg)

    # ---------- Dashboard ----------
    def build_dashboard(self):
        layout = QVBoxLayout()

        self.lbl_totals = QLabel("")
        self.lbl_totals.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.lbl_rating = QLabel("")
        self.lbl_rating.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.lbl_budget_warnings = QLabel("")
        self.lbl_budget_warnings.setWordWrap(True)
        self.lbl_budget_warnings.setTextInteractionFlags(Qt.TextSelectableByMouse)

        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_all)
        self.btn_undo = QPushButton("Undo Last Transaction")
        self.btn_undo.clicked.connect(self.undo_last)
        self.btn_reset = QPushButton("Reset ALL Data")
        self.btn_reset.clicked.connect(self.reset_all)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_undo)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)

        layout.addWidget(QLabel("<h2>Dashboard</h2>"))
        layout.addLayout(btn_row)
        layout.addWidget(self.lbl_totals)
        layout.addWidget(self.lbl_rating)
        layout.addWidget(QLabel("<b>Budget warnings (this month):</b>"))
        layout.addWidget(self.lbl_budget_warnings)
        layout.addStretch(1)

        self.tab_dashboard.setLayout(layout)

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
            return

        spent = totals_by_category(month_txs, ttype="expense")
        lines = []
        for cat, limit in budgets.items():
            if limit <= 0:
                continue
            used = spent.get(cat, 0.0)
            pct = (used / limit) * 100.0
            if pct >= 100:
                lines.append(f"OVER: {cat} — {used:.2f}/{limit:.2f} ({pct:.0f}%)")
            elif pct >= 80:
                lines.append(f"Near: {cat} — {used:.2f}/{limit:.2f} ({pct:.0f}%)")
        self.lbl_budget_warnings.setText("\n".join(lines) if lines else "All budgets look OK.")

    # ---------- Add ----------
    def build_add(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>Add Transaction</h2>"))

        form = QFormLayout()

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["income", "expense"])

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
        btn_add.clicked.connect(self.add_tx)
        btn_clear = QPushButton("Clear Fields")
        btn_clear.clicked.connect(self.clear_add_fields)
        btns.addWidget(btn_add)
        btns.addWidget(btn_clear)
        btns.addStretch(1)

        layout.addLayout(form)
        layout.addLayout(btns)
        layout.addStretch(1)

        self.tab_add.setLayout(layout)

    def clear_add_fields(self):
        self.txt_date.clear()
        self.spn_amount.setValue(10.0)
        self.txt_category.clear()
        self.txt_note.clear()

    def add_tx(self):
        ttype = self.cmb_type.currentText().strip()
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

    # ---------- History ----------
    def build_history(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>History</h2>"))

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Date", "Type", "Amount", "Category", "Note", "Created"])
        self.tbl.setSortingEnabled(True)

        row = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_history)
        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(self.delete_selected)
        row.addWidget(btn_refresh)
        row.addWidget(btn_delete)
        row.addStretch(1)

        layout.addLayout(row)
        layout.addWidget(self.tbl)

        self.tab_history.setLayout(layout)

    def refresh_history(self):
        data = sorted(self.txs, key=lambda x: (x.get("date", ""), x.get("created_at", "")), reverse=True)
        self.tbl.setRowCount(len(data))
        for r, t in enumerate(data):
            items = [
                QTableWidgetItem(str(t.get("date", ""))),
                QTableWidgetItem(str(t.get("type", ""))),
                QTableWidgetItem(f"{float(t.get('amount', 0.0)):.2f}"),
                QTableWidgetItem(str(t.get("category", ""))),
                QTableWidgetItem(str(t.get("note", ""))),
                QTableWidgetItem(str(t.get("created_at", ""))),
            ]
            for c, it in enumerate(items):
                it.setFlags(it.flags() ^ Qt.ItemIsEditable)
                self.tbl.setItem(r, c, it)

    def selected_tx_id(self) -> Optional[int]:
        row = self.tbl.currentRow()
        if row < 0:
            return None
        # We need to map table row -> transaction. We refresh sorted desc,
        # so we reconstruct the same ordering and index.
        data = sorted(self.txs, key=lambda x: (x.get("date", ""), x.get("created_at", "")), reverse=True)
        if row >= len(data):
            return None
        return int(data[row].get("id"))

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

    # ---------- Summary ----------
    def build_summary(self):
        layout = QVBoxLayout()
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

        self.tab_summary.setLayout(layout)

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
        self.tab_month.setLayout(layout)

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
            "Top expense categories:"
        ]
        for cat, amt in top:
            lines.append(f"  {cat}: {amt:.2f}")
        self.txt_month.setPlainText("\n".join(lines))

    # ---------- Budgets ----------
    def build_budgets(self):
        layout = QVBoxLayout()
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

        self.tab_budgets.setLayout(layout)

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
        layout.addWidget(QLabel("<h2>Export</h2>"))

        btn = QPushButton("Export CSV…")
        btn.clicked.connect(self.export_csv)

        layout.addWidget(btn)
        layout.addStretch(1)
        self.tab_export.setLayout(layout)

    def export_csv(self):
        if not self.txs:
            self.show_info("No transactions to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "export.csv", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "date", "type", "amount", "category", "note", "created_at"])
            for t in sorted(self.txs, key=lambda x: (x.get("date", ""), x.get("created_at", ""))):
                w.writerow([
                    t.get("id"), t.get("date"), t.get("type"), t.get("amount"),
                    t.get("category"), t.get("note", ""), t.get("created_at", "")
                ])
        self.show_info("Exported ✅")

    # ---------- Settings ----------
    def build_settings(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>Settings</h2>"))

        btn_set_pin = QPushButton("Set / Change PIN")
        btn_set_pin.clicked.connect(self.set_pin)

        btn_clear_pin = QPushButton("Remove PIN")
        btn_clear_pin.clicked.connect(self.remove_pin)

        layout.addWidget(btn_set_pin)
        layout.addWidget(btn_clear_pin)
        layout.addStretch(1)

        self.tab_settings.setLayout(layout)

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
    win = FinanceTrackerGUI()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
