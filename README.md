# Midaxas Finance

Polished, single-file local personal finance tracker built with PySide6 (Qt).  
Lightweight desktop app for tracking income, expenses, budgets, generating monthly reports, exporting CSV and optionally protecting the app with a PIN.

Release: v1.1.0 — 2025-12-25
- Major UI polish: frameless window with custom title bar, dark theme, non-blocking toast notifications, page fade animations, and navigation row.
- History moved to a proper QAbstractTableModel + QTableView.
- Atomic JSON saves to prevent file corruption.
- Optional interactive dashboard chart (pyqtgraph) and optional icons (qtawesome).
- Safer parsing and error handling across the app.

Repository: https://github.com/Midaxas/Midaxas-Finance

---

Table of contents
- Overview
- What’s new in v1.1.0
- Features
- Quick start (install & run)
- Optional enhancements
- Usage / UI walkthrough
- Data & file format
- Security & privacy notes
- Limitations & known issues
- Development / project structure
- Contributing
- License

---

Overview
--------
Midaxas Finance is a simple, local desktop app to track personal finances. It stores data in local JSON files (no external servers) and focuses on an easy-to-use UI for adding transactions, viewing history, setting monthly budgets, seeing a dashboard, exporting CSV, and protecting the app with a PIN.

What’s new in v1.1.0
--------------------
- Frameless window with custom TitleBar (drag-to-move, minimize/maximize/close, refresh).
- Embedded dark theme (QSS) applied at startup.
- Non-blocking Toast notifications and fade-in page transitions.
- Navigation row + QStackedWidget replaces the previous tab widget UI.
- TransactionModel using QAbstractTableModel powering a QTableView for history (stable sorting and selection).
- Optional chart on the dashboard powered by pyqtgraph (if installed).
- Atomic JSON file writes to avoid partial/corrupt files.
- Improved parsing/fallbacks for numeric/date fields and better export error handling.

Features
--------
- Dashboard
  - Total income, total expenses, net (savings) and a simple rating.
  - Budget warnings for the current month (over/near budgets).
  - Optional interactive chart of net/income/expenses (requires pyqtgraph).

- Add Transaction
  - Type: `income` or `expense` (text input with fallback to `expense` if left empty).
  - Date: YYYY-MM-DD (leave empty to use today).
  - Amount: 2 decimal places (validated).
  - Category and optional note.
  - Transactions are saved with ID and created_at timestamp.

- History
  - Table view (QTableView) backed by TransactionModel (sort and select rows).
  - Delete selected transaction.

- Summary
  - Totals by category for income and expenses.

- Monthly Report
  - Generate income/expense/net report for a chosen year/month and list top expense categories.

- Budgets
  - Set monthly budget per category.
  - Dashboard warns when budgets are near/over the limit.

- Export
  - Export transactions to CSV (id, date, type, amount, category, note, created_at).

- Settings
  - Set / change / remove a PIN to protect the app on startup.

Quick start (install & run)
---------------------------
Requirements
- Python 3.9+ recommended
- PySide6

Install and run:
```bash
# optional: create virtualenv
python -m venv venv
# Activate the venv (platform-specific)
# Install required dependency
pip install PySide6
# Optional: install enhanced features
pip install pyqtgraph qtawesome
# Run the app (single-file)
python Tracker.py
```

Optional enhancements
- pyqtgraph — interactive dashboard charts (recommended, optional)
- qtawesome — optional icons
Install them with:
```bash
pip install pyqtgraph qtawesome
```

Usage / UI walkthrough
----------------------
- Title bar
  - Custom title bar supports drag-to-move, double-click to maximize/restore, minimize, maximize, close and includes a refresh button.
- Navigation
  - Use the navigation buttons (Dashboard, Add, History, Summary, Monthly, Budgets, Export, Settings) to switch pages. Pages fade in for smooth transitions.
- Adding a transaction
  - Enter Type (`income` or `expense`), date (or leave blank), amount, category and optional note. Click Add to save and return to Dashboard.
- History
  - Use the History page to sort and inspect transactions. Select a row and click Delete Selected to remove one transaction.
- Budgets
  - Set monthly budgets by category and check Dashboard warnings for exceedances.
- Export
  - Export all transactions to CSV using Export → Export CSV… (errors are reported by non-blocking toasts).
- PIN
  - Protect the app with a PIN saved as a hash. On startup, if a PIN is set you will be prompted to enter it.

Data & file format
------------------
Files are stored in the application directory by default:
- transactions.json — list of transaction objects:
  - id: integer (ms epoch)
  - date: "YYYY-MM-DD"
  - type: "income" | "expense"
  - amount: number
  - category: string
  - note: string
  - created_at: ISO timestamp
- settings.json — minimal settings:
  - pin_hash: SHA-256 hex string or null
  - budgets: { "Category Name": amount, ... }

These formats are backwards-compatible with earlier versions; no migration steps are required.

Security & privacy notes
------------------------
- All data is stored locally in JSON files — nothing is sent to any server.
- PINs are hashed with SHA-256. This is sufficient for local convenience but not as strong as a modern password KDF (PBKDF2/Argon2). If you require stronger protection, consider replacing the hash with a KDF and adding a migration strategy.
- If the device is compromised, local JSON files can be read by an attacker with local access. Encrypting the files is out of scope of this app at this time.

Limitations & known issues
--------------------------
- Add Transaction "Type" input is a text field in v1.1.0. Users must type `income` or `expense` (fallback to `expense` if left empty). If you prefer a fixed choice to avoid typos, consider reverting that widget to a QComboBox.
- Frameless windows may behave differently across operating systems and window managers (resizing and system menus). Test on your target platforms.
- Optional features (charts/icons) are not required; the app falls back gracefully when they are not installed.
- No automated tests currently included.

Development / project structure
-------------------------------
- Tracker.py — single-file application (entry point)
- transactions.json, settings.json — data files created at runtime
- Optional additions: tests/, scripts/ may be added in future iterations

Contributing
------------
Contributions are welcome. Typical workflow:
- Fork the repo
- Create a feature branch
- Open a pull request with a clear description and, if applicable, screenshots or short video of UX changes

Please follow the existing code style and keep UI changes consistent with the theme.

License
-------
See the repository LICENSE file for full licensing terms.

---
