# Pocket Ledger

A beginner-friendly personal expense tracker built with Python, Flask, SQLite, HTML, CSS, and Matplotlib.

## Features

- Record income and expenses with a category, date, amount, and optional description.
- Review monthly income, expenses, and savings (income minus expenses).
- View an automatically generated chart of spending by category.
- Edit or delete transactions.
- Keep data in a local SQLite database.
- Use the responsive dashboard on desktop or mobile.

## Run locally

Python 3.10 or newer is recommended.

1. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Start the application:

   ```powershell
   python app.py
   ```

4. Open <http://127.0.0.1:5000> in your browser.

The app creates `instance/expenses.sqlite` automatically the first time it runs.
To use a different database file, set `DATABASE_PATH`. Set `SECRET_KEY` to a
private random value before exposing the app beyond your local machine.

## Run tests

```powershell
python -m unittest
```
