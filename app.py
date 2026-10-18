import base64
import math
import os
import sqlite3
from datetime import date, datetime
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import Flask, abort, flash, g, redirect, render_template, request, url_for


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development-key")
app.config["DATABASE"] = os.environ.get(
    "DATABASE_PATH", os.path.join(app.instance_path, "expenses.sqlite")
)
os.makedirs(app.instance_path, exist_ok=True)

INCOME_CATEGORIES = ["Salary", "Freelance", "Investment", "Gift", "Other"]
EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Housing",
    "Utilities",
    "Health",
    "Shopping",
    "Entertainment",
    "Other",
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
            amount REAL NOT NULL CHECK (amount > 0),
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            transaction_date TEXT NOT NULL
        )
        """
    )
    db.commit()


def selected_month():
    value = request.args.get("month", date.today().strftime("%Y-%m"))
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return date.today().strftime("%Y-%m")


def spending_chart(rows):
    if not rows:
        return None

    categories = [row["category"] for row in rows]
    amounts = [row["total"] for row in rows]
    fig, ax = plt.subplots(figsize=(7, max(2.5, len(rows) * 0.48)))
    bars = ax.barh(categories[::-1], amounts[::-1], color="#5264e8", height=0.58)
    ax.set_xlabel("Amount")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#e7e9f0")
    ax.tick_params(axis="y", length=0, colors="#45495a")
    ax.tick_params(axis="x", colors="#73788a")
    ax.grid(axis="x", color="#edf0f5", linewidth=0.8)
    ax.set_axisbelow(True)
    for bar, amount in zip(bars, amounts[::-1]):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f"  {amount:,.2f}",
            va="center",
            color="#45495a",
            fontsize=9,
        )
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    fig.tight_layout()
    image = BytesIO()
    fig.savefig(image, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(image.getvalue()).decode("ascii")


@app.route("/")
def index():
    month = selected_month()
    db = get_db()
    totals = db.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN kind = 'income' THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE transaction_date LIKE ?
        """,
        (f"{month}%",),
    ).fetchone()
    transactions = db.execute(
        """
        SELECT * FROM transactions
        WHERE transaction_date LIKE ?
        ORDER BY transaction_date DESC, id DESC
        """,
        (f"{month}%",),
    ).fetchall()
    categories = db.execute(
        """
        SELECT category, SUM(amount) AS total FROM transactions
        WHERE kind = 'expense' AND transaction_date LIKE ?
        GROUP BY category ORDER BY total DESC
        """,
        (f"{month}%",),
    ).fetchall()
    savings = totals["income"] - totals["expenses"]
    return render_template(
        "index.html",
        month=month,
        income=totals["income"],
        expenses=totals["expenses"],
        savings=savings,
        transactions=transactions,
        chart=spending_chart(categories),
        categories=categories,
    )


def transaction_values(form):
    kind = form.get("kind", "")
    category = form.get("category", "").strip()
    description = form.get("description", "").strip()
    raw_amount = form.get("amount", "").strip()
    transaction_date = form.get("transaction_date", "").strip()

    if kind not in ("income", "expense"):
        raise ValueError("Choose whether this transaction is income or an expense.")
    allowed_categories = INCOME_CATEGORIES if kind == "income" else EXPENSE_CATEGORIES
    if category not in allowed_categories:
        raise ValueError("Choose a valid category for this transaction type.")
    try:
        amount = float(raw_amount)
    except ValueError:
        raise ValueError("Enter a valid amount.") from None
    if not math.isfinite(amount) or not 0 < amount < 1_000_000_000:
        raise ValueError("Amount must be greater than zero and less than 1,000,000,000.")
    amount = round(amount, 2)
    if amount == 0:
        raise ValueError("Amount must be greater than zero and less than 1,000,000,000.")
    try:
        datetime.strptime(transaction_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Enter a valid transaction date.") from None
    if len(description) > 200:
        raise ValueError("Description must be 200 characters or fewer.")
    return kind, amount, category, description, transaction_date


def get_transaction(transaction_id):
    transaction = get_db().execute(
        "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
    ).fetchone()
    if transaction is None:
        abort(404)
    return transaction


@app.route("/transactions/new", methods=["GET", "POST"])
def new_transaction():
    if request.method == "POST":
        try:
            values = transaction_values(request.form)
        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "transaction_form.html",
                transaction=request.form,
                income_categories=INCOME_CATEGORIES,
                expense_categories=EXPENSE_CATEGORIES,
                page_title="Add transaction",
            ), 400
        db = get_db()
        db.execute(
            """
            INSERT INTO transactions
                (kind, amount, category, description, transaction_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            values,
        )
        db.commit()
        flash("Transaction added.", "success")
        return redirect(url_for("index", month=values[4][:7]))
    return render_template(
        "transaction_form.html",
        transaction={"kind": "expense", "transaction_date": date.today().isoformat()},
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES,
        page_title="Add transaction",
    )


@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
def edit_transaction(transaction_id):
    transaction = get_transaction(transaction_id)
    if request.method == "POST":
        try:
            values = transaction_values(request.form)
        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "transaction_form.html",
                transaction=request.form,
                income_categories=INCOME_CATEGORIES,
                expense_categories=EXPENSE_CATEGORIES,
                page_title="Edit transaction",
            ), 400
        db = get_db()
        db.execute(
            """
            UPDATE transactions
            SET kind = ?, amount = ?, category = ?, description = ?, transaction_date = ?
            WHERE id = ?
            """,
            (*values, transaction_id),
        )
        db.commit()
        flash("Transaction updated.", "success")
        return redirect(url_for("index", month=values[4][:7]))
    return render_template(
        "transaction_form.html",
        transaction=dict(transaction),
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES,
        page_title="Edit transaction",
    )


@app.post("/transactions/<int:transaction_id>/delete")
def delete_transaction(transaction_id):
    transaction = get_transaction(transaction_id)
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    db.commit()
    flash("Transaction deleted.", "success")
    return redirect(url_for("index", month=transaction["transaction_date"][:7]))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
