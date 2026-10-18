import os
import tempfile
import unittest

import app as expense_app


class ExpenseTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        expense_app.app.config.update(
            TESTING=True,
            DATABASE=os.path.join(self.temp_dir.name, "test.sqlite"),
        )
        with expense_app.app.app_context():
            expense_app.init_db()
        self.client = expense_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dashboard_shows_empty_month(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"MONTHLY SAVINGS", response.data)
        self.assertIn(b"A fresh start.", response.data)

    def test_create_income_and_expense_calculates_monthly_savings(self):
        for form in (
            {
                "kind": "income",
                "amount": "2500.00",
                "category": "Salary",
                "description": "Payday",
                "transaction_date": "2025-05-01",
            },
            {
                "kind": "expense",
                "amount": "40.50",
                "category": "Food",
                "description": "Groceries",
                "transaction_date": "2025-05-02",
            },
        ):
            response = self.client.post("/transactions/new", data=form)
            self.assertEqual(response.status_code, 302)

        response = self.client.get("/?month=2025-05")
        self.assertIn(b"$2,500.00", response.data)
        self.assertIn(b"$40.50", response.data)
        self.assertIn(b"$2,459.50", response.data)
        self.assertIn(b"Groceries", response.data)
        self.assertIn(b"Spending by category", response.data)

    def test_invalid_amount_is_rejected(self):
        response = self.client.post(
            "/transactions/new",
            data={
                "kind": "expense",
                "amount": "-8",
                "category": "Food",
                "transaction_date": "2025-05-02",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Amount must be greater than zero", response.data)

    def test_edit_and_delete_transaction(self):
        self.client.post(
            "/transactions/new",
            data={
                "kind": "expense",
                "amount": "8.25",
                "category": "Food",
                "description": "Coffee",
                "transaction_date": "2025-05-02",
            },
        )
        with expense_app.app.app_context():
            transaction_id = expense_app.get_db().execute(
                "SELECT id FROM transactions"
            ).fetchone()["id"]

        self.assertEqual(
            self.client.get(f"/transactions/{transaction_id}/edit").status_code,
            200,
        )
        response = self.client.post(
            f"/transactions/{transaction_id}/edit",
            data={
                "kind": "expense",
                "amount": "9.50",
                "category": "Food",
                "description": "Coffee and snack",
                "transaction_date": "2025-05-03",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            b"Coffee and snack",
            self.client.get("/?month=2025-05").data,
        )

        response = self.client.post(f"/transactions/{transaction_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            b"A fresh start.",
            self.client.get("/?month=2025-05").data,
        )

    def test_missing_transaction_returns_404(self):
        self.assertEqual(self.client.get("/transactions/999/edit").status_code, 404)


if __name__ == "__main__":
    unittest.main()
