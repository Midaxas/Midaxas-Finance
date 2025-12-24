# Midaxas Finance

A small, local personal finance tracker built with PySide6 (Qt) — simple, readable, and useful for tracking income, expenses, budgets and exporting data. Designed as a compact desktop app for personal use.

Repository: [Midaxas/Midaxas-Finance](https://github.com/Midaxas/Midaxas-Finance)

---

Table of contents
- Overview
- Features
- Screenshots (example)
- Quick start (install & run)
- Usage / UI walkthrough
- Data & file format
- Security & privacy notes
- Limitations & known issues
- Development / project structure
- Recommended improvements
- Contributing
- License

---

Overview
--------
Midaxas Finance is a small graphical personal finance tracker implemented with Python and PySide6. It stores transactions locally in JSON files and provides a simple, user-friendly GUI to add transactions, view history, set monthly budgets, generate monthly reports, export CSV, and optionally protect the app with a PIN.

It is intentionally lightweight and self-contained — no external database required.

Features
--------
- Dashboard
  - Total income, total expenses, and net (savings)
  - Simple rating based on net savings
  - Budget warning panel for the current month (over/near budgets)
  - Refresh, Undo last transaction, Reset all data

- Add Transaction
  - Add income or expense
  - Date (YYYY-MM-DD) — leave empty to use today
  - Amount (with 2 decimal places)
  - Category (e.g. Food, Rent, Salary) and optional note
  - Transactions get a generated ID and creation timestamp

- History
  - Table view of all transactions (date, type, amount, category, note, created)
  - Sortable
  - Delete selected transaction(s)

- Summary
  - Totals by category for income and expense
  - Quick snapshot of totals and category breakdowns

- Monthly Report
  - Select year and month, generate a report with income, expense, net and top expense categories

- Budgets
  - Set monthly budget per category
  - Remove budgets
  - Budget listing view (current budgets)
  - Budget warnings shown in the Dashboard for the current month

- Export
  - Export all transactions to CSV (id, date, type, amount, category, note, created_at)

- Settings
  - Set / change a PIN to protect the app on startup
  - Remove PIN

- Persistence
  - Local JSON files:
    - transactions.json — list of transaction objects
    - settings.json — stores pin hash and budgets

- Small UX touches:
  - Confirmations for destructive actions (delete, undo, reset)
  - Informational dialogs after saves/exports
  - Selectable labels for easy copy/paste

Quick start (install & run)
---------------------------
Requirements
- Python 3.9+ (3.10/3.11 recommended)
- PySide6

Optional (recommended)
- Create and use a virtual environment

Example steps
```bash
# Create and activate a virtualenv (Unix-like)
python -m venv venv
source venv/bin/activate

# On Windows (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1

# Install dependencies
pip install PySide6

# Run the application
# Replace `main.py` below with the actual filename containing the app's entry point if different.
python main.py
```

Usage / UI walkthrough
----------------------
1. Startup
   - If a PIN is set in settings.json, you'll be prompted for the PIN on startup (3 attempts).
2. Dashboard
   - See overall totals and a short rating.
   - Budget warnings for the current month list categories near/over their budgets.
   - Buttons: Refresh, Undo Last Transaction, Reset ALL Data.
3. Add
   - Choose `income` or `expense`, enter date (or leave blank for today), amount, category and note.
   - Click Add to save; the app persists to `transactions.json`.
4. History
   - View all transactions in a sortable table.
   - Select a row and click Delete Selected to remove a transaction.
5. Summary
   - View totals and top categories for income and expenses.
6. Monthly
   - Choose year and month and click Generate to see a textual report for that month.
7. Budgets
   - Enter a category and a monthly budget amount.
   - Set/Update or Remove budgets. Budgets are stored in `settings.json`.
8. Export
   - Click Export CSV… to save a CSV file of all transactions.
9. Settings
   - Set/Change a PIN or remove it. The app stores a hash in `settings.json`.

Data & file format
------------------
Files used by the app (by default in the current working directory):
- transactions.json — list of transaction objects
- settings.json — dictionary with keys:
  - pin_hash: (string | null) — hashed PIN (implementation detail)
  - budgets: { "Category": amount, ... }

Example transaction entry
```json
{
  "id": 1700000000000,
  "date": "2025-12-24",
  "type": "expense",
  "amount": 12.50,
  "category": "Food",
  "note": "Lunch",
  "created_at": "2025-12-24T12:34:56"
}
```

Example settings.json
```json
{
  "pin_hash": null,
  "budgets": {
    "Food": 300.0,
    "Rent": 1200.0
  }
}
```

Security & privacy notes
------------------------
- PIN: the app stores a hashed PIN in settings.json. The sample implementation uses SHA-256 without a salt or slow KDF. While fine for learning/personal use, this is not secure against offline brute-force attacks. Consider using a salted, slow KDF (PBKDF2, bcrypt, scrypt or Argon2) and store salt and parameters with the hash.
- Data is stored locally in JSON files. There is no encryption by default. If you need privacy, store data on encrypted volumes or add an encryption layer to the files.
- The app does not transmit data anywhere — all data is local to your machine.

Limitations & known issues
--------------------------
- Amounts are stored and computed using floats — this can lead to rounding errors with monetary values. Consider using integer cents or Decimal for correct financial arithmetic.
- Files are saved directly and not in atomic-write fashion; a crash during a write could corrupt the JSON file.
- `transactions.json` and `settings.json` are stored in the current working directory. You may prefer storing them in a user data directory (e.g., using `appdirs`) to be platform appropriate.
- Some defensive checks on loaded JSON data are minimal — corrupted or manually edited JSON may cause errors.
- The rating algorithm in the dashboard uses an ad-hoc points scheme — results are for illustrative purposes only.

Development / project structure
-------------------------------

- main.py (or app entrypoint)
- README.md
- requirements.txt (optional)
- transactions.json (data)
- settings.json (app settings)
- src/ or modules/
  - persistence.py — load/save JSON helpers
  - models.py — transaction dataclass / validation (recommended)
  - ui_mainwindow.py — GUI code (PySide6)
  - utils.py — helpers (hashing, formatting)
- tests/ — unit tests (recommended)

Recommended improvements (next steps)
------------------------------------
If you'd like to improve the app, consider:
- Use a proper password/PIN hashing scheme (PBKDF2, bcrypt, scrypt, Argon2) with salt and parameter storage.
- Switch monetary arithmetic to Decimal or store amounts as integer cents.
- Use atomic file writes (write to temporary file and os.replace) to avoid corruption.
- Move data files to a platform-appropriate user data directory (appdirs or pathlib-based).
- Introduce a Transaction dataclass and separate model/persistence from GUI to make the core logic unit-testable.
- Add unit tests for totals, filtering, budgets, and persistence behaviors.
- Add logging to capture unexpected errors (rather than silently returning defaults on JSON decode errors).
- Consider optional encryption of data files if you need stronger privacy.

Contributing
------------
Contributions are welcome! Suggested guidelines:
- Fork the repository
- Create a feature branch
- Run tests (if present) and add new tests for changes
- Keep changes focused and documented
- Submit a pull request with a clear description of the change

If you're unsure where to start, suggested good-first-issues:
- Replace SHA-256 PIN hashing with a proper KDF-based approach
- Change amount handling to Decimal or integer cents
- Implement atomic file writes and a configurable data directory
  
MIT:
```
MIT License
Copyright (c) 2025 Midaxas
Permission is hereby granted, free of charge, to any person obtaining a copy...
```

Contact / author
----------------
Created by Midaxas. For questions or help, open an issue on the repository: [https://github.com/Midaxas/Midaxas-Finance](https://github.com/Midaxas/Midaxas-Finance)
