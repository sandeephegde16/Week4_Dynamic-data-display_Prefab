"""Synthetic demo database for local presentations."""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from app.data.schema import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from app.debug import log_event


DEMO_DATABASE_NAME = "synthetic_loan_demo"


def create_demo_engine() -> Engine:
    """Create an in-memory SQLite database with deterministic synthetic lending data."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_tables(engine)
    _seed_demo_data(engine)
    log_event("Synthetic demo database initialized.", {"database": DEMO_DATABASE_NAME})
    return engine


def test_demo_connection(engine: Engine) -> None:
    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar_one()
    log_event("Synthetic demo database connection test succeeded.", {"select_1": value})


def demo_schema() -> DatabaseSchema:
    return DatabaseSchema(
        database_name=DEMO_DATABASE_NAME,
        sql_dialect="sqlite",
        tables=[
            _table(
                "loan_accounts",
                420,
                [
                    _column("loan_accounts", "loan_id", 1, "integer", "INTEGER", key="PRI"),
                    _column("loan_accounts", "customer_id", 2, "integer", "INTEGER"),
                    _column("loan_accounts", "product_id", 3, "integer", "INTEGER"),
                    _column("loan_accounts", "opened_date", 4, "date", "DATE"),
                    _column("loan_accounts", "maturity_date", 5, "date", "DATE"),
                    _column("loan_accounts", "status", 6, "varchar", "VARCHAR(24)"),
                    _column("loan_accounts", "currency", 7, "varchar", "VARCHAR(3)"),
                    _column("loan_accounts", "principal_amount", 8, "decimal", "DECIMAL(12,2)"),
                    _column("loan_accounts", "outstanding_amount", 9, "decimal", "DECIMAL(12,2)"),
                    _column("loan_accounts", "interest_rate", 10, "decimal", "DECIMAL(5,2)"),
                    _column("loan_accounts", "origination_fee", 11, "decimal", "DECIMAL(10,2)"),
                    _column("loan_accounts", "servicing_fee", 12, "decimal", "DECIMAL(10,2)"),
                    _column("loan_accounts", "late_fee", 13, "decimal", "DECIMAL(10,2)"),
                    _column("loan_accounts", "risk_grade", 14, "varchar", "VARCHAR(2)"),
                ],
                [
                    ForeignKeyInfo(
                        table_name="loan_accounts",
                        column_name="customer_id",
                        referenced_table_name="customers",
                        referenced_column_name="customer_id",
                    ),
                    ForeignKeyInfo(
                        table_name="loan_accounts",
                        column_name="product_id",
                        referenced_table_name="loan_products",
                        referenced_column_name="product_id",
                    ),
                ],
            ),
            _table(
                "customers",
                180,
                [
                    _column("customers", "customer_id", 1, "integer", "INTEGER", key="PRI"),
                    _column("customers", "customer_name", 2, "varchar", "VARCHAR(80)"),
                    _column("customers", "region", 3, "varchar", "VARCHAR(24)"),
                    _column("customers", "segment", 4, "varchar", "VARCHAR(32)"),
                    _column("customers", "signup_date", 5, "date", "DATE"),
                ],
            ),
            _table(
                "loan_products",
                8,
                [
                    _column("loan_products", "product_id", 1, "integer", "INTEGER", key="PRI"),
                    _column("loan_products", "product_name", 2, "varchar", "VARCHAR(80)"),
                    _column("loan_products", "loan_category", 3, "varchar", "VARCHAR(40)"),
                    _column("loan_products", "base_fee_rate", 4, "decimal", "DECIMAL(5,4)"),
                    _column("loan_products", "active", 5, "boolean", "BOOLEAN"),
                ],
            ),
            _table(
                "fee_transactions",
                1_260,
                [
                    _column("fee_transactions", "fee_id", 1, "integer", "INTEGER", key="PRI"),
                    _column("fee_transactions", "loan_id", 2, "integer", "INTEGER"),
                    _column("fee_transactions", "fee_date", 3, "date", "DATE"),
                    _column("fee_transactions", "fee_type", 4, "varchar", "VARCHAR(40)"),
                    _column("fee_transactions", "fee_category", 5, "varchar", "VARCHAR(40)"),
                    _column("fee_transactions", "fee_amount", 6, "decimal", "DECIMAL(10,2)"),
                    _column("fee_transactions", "waived", 7, "boolean", "BOOLEAN"),
                ],
                [
                    ForeignKeyInfo(
                        table_name="fee_transactions",
                        column_name="loan_id",
                        referenced_table_name="loan_accounts",
                        referenced_column_name="loan_id",
                    )
                ],
            ),
            _table(
                "payments",
                2_100,
                [
                    _column("payments", "payment_id", 1, "integer", "INTEGER", key="PRI"),
                    _column("payments", "loan_id", 2, "integer", "INTEGER"),
                    _column("payments", "payment_date", 3, "date", "DATE"),
                    _column("payments", "payment_amount", 4, "decimal", "DECIMAL(10,2)"),
                    _column("payments", "payment_channel", 5, "varchar", "VARCHAR(32)"),
                ],
                [
                    ForeignKeyInfo(
                        table_name="payments",
                        column_name="loan_id",
                        referenced_table_name="loan_accounts",
                        referenced_column_name="loan_id",
                    )
                ],
            ),
        ],
    )


def _create_tables(engine: Engine) -> None:
    statements = [
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region TEXT NOT NULL,
            segment TEXT NOT NULL,
            signup_date DATE NOT NULL
        )
        """,
        """
        CREATE TABLE loan_products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            loan_category TEXT NOT NULL,
            base_fee_rate REAL NOT NULL,
            active INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE loan_accounts (
            loan_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            opened_date DATE NOT NULL,
            maturity_date DATE NOT NULL,
            status TEXT NOT NULL,
            currency TEXT NOT NULL,
            principal_amount REAL NOT NULL,
            outstanding_amount REAL NOT NULL,
            interest_rate REAL NOT NULL,
            origination_fee REAL NOT NULL,
            servicing_fee REAL NOT NULL,
            late_fee REAL NOT NULL,
            risk_grade TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY(product_id) REFERENCES loan_products(product_id)
        )
        """,
        """
        CREATE TABLE fee_transactions (
            fee_id INTEGER PRIMARY KEY,
            loan_id INTEGER NOT NULL,
            fee_date DATE NOT NULL,
            fee_type TEXT NOT NULL,
            fee_category TEXT NOT NULL,
            fee_amount REAL NOT NULL,
            waived INTEGER NOT NULL,
            FOREIGN KEY(loan_id) REFERENCES loan_accounts(loan_id)
        )
        """,
        """
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY,
            loan_id INTEGER NOT NULL,
            payment_date DATE NOT NULL,
            payment_amount REAL NOT NULL,
            payment_channel TEXT NOT NULL,
            FOREIGN KEY(loan_id) REFERENCES loan_accounts(loan_id)
        )
        """,
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _seed_demo_data(engine: Engine) -> None:
    rng = random.Random(20260509)
    products = _products()
    customers = _customers(rng)
    loans = _loans(rng, customers, products)
    fees = _fees(rng, loans)
    payments = _payments(rng, loans)

    with engine.begin() as connection:
        connection.execute(text(_insert_sql("customers", customers[0].keys())), customers)
        connection.execute(text(_insert_sql("loan_products", products[0].keys())), products)
        connection.execute(text(_insert_sql("loan_accounts", loans[0].keys())), loans)
        connection.execute(text(_insert_sql("fee_transactions", fees[0].keys())), fees)
        connection.execute(text(_insert_sql("payments", payments[0].keys())), payments)


def _products() -> list[dict[str, Any]]:
    return [
        _product(1, "Everyday Personal Loan", "Personal", 0.018),
        _product(2, "Prime Auto Loan", "Auto", 0.014),
        _product(3, "Study Assist Loan", "Education", 0.011),
        _product(4, "Home Upgrade Loan", "Home Improvement", 0.016),
        _product(5, "Working Capital Line", "Working Capital", 0.021),
        _product(6, "Equipment Finance Plan", "Equipment", 0.019),
        _product(7, "Green Energy Loan", "Green Energy", 0.012),
        _product(8, "Travel Flex Loan", "Travel", 0.022),
    ]


def _product(product_id: int, name: str, category: str, fee_rate: float) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "product_name": name,
        "loan_category": category,
        "base_fee_rate": fee_rate,
        "active": 1,
    }


def _customers(rng: random.Random) -> list[dict[str, Any]]:
    first_names = [
        "Avery",
        "Blake",
        "Casey",
        "Dakota",
        "Emerson",
        "Finley",
        "Harper",
        "Jordan",
        "Morgan",
        "Parker",
        "Quinn",
        "Riley",
        "Sawyer",
        "Taylor",
        "Rowan",
    ]
    last_names = [
        "Brooks",
        "Carter",
        "Hayes",
        "Lane",
        "Morgan",
        "Perry",
        "Reed",
        "Stone",
        "Taylor",
        "Walker",
        "Young",
        "Bennett",
    ]
    regions = ["North", "South", "East", "West", "Central"]
    segments = ["Retail", "Preferred", "Self Employed", "Small Enterprise", "Public Sector"]
    start = date(2021, 1, 1)
    return [
        {
            "customer_id": customer_id,
            "customer_name": f"{rng.choice(first_names)} {rng.choice(last_names)} {customer_id:03d}",
            "region": rng.choice(regions),
            "segment": rng.choice(segments),
            "signup_date": _date_text(start + timedelta(days=rng.randint(0, 1_760))),
        }
        for customer_id in range(1, 181)
    ]


def _loans(
    rng: random.Random,
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    amount_ranges = {
        "Personal": (5_000, 45_000),
        "Auto": (8_000, 70_000),
        "Education": (10_000, 120_000),
        "Home Improvement": (15_000, 180_000),
        "Working Capital": (20_000, 400_000),
        "Equipment": (25_000, 300_000),
        "Green Energy": (10_000, 150_000),
        "Travel": (2_000, 25_000),
    }
    statuses = ["Active", "Closed", "Past Due", "Approved", "Pending", "Restructured"]
    risk_grades = ["A", "B", "C", "D"]
    opened_start = date(2022, 1, 1)
    loans = []
    for loan_id in range(1, 421):
        product = rng.choice(products)
        low, high = amount_ranges[str(product["loan_category"])]
        principal = round(rng.uniform(low, high), 2)
        status = rng.choices(statuses, weights=[42, 26, 8, 10, 8, 6], k=1)[0]
        outstanding = 0.0 if status == "Closed" else round(principal * rng.uniform(0.12, 0.96), 2)
        opened_date = opened_start + timedelta(days=rng.randint(0, 1_180))
        maturity_date = opened_date + timedelta(days=rng.choice([365, 730, 1_095, 1_460, 1_825]))
        late_fee = 0.0 if status not in {"Past Due", "Restructured"} else round(rng.uniform(35, 750), 2)
        loans.append(
            {
                "loan_id": loan_id,
                "customer_id": rng.choice(customers)["customer_id"],
                "product_id": product["product_id"],
                "opened_date": _date_text(opened_date),
                "maturity_date": _date_text(maturity_date),
                "status": status,
                "currency": "USD",
                "principal_amount": principal,
                "outstanding_amount": outstanding,
                "interest_rate": round(rng.uniform(4.25, 14.75), 2),
                "origination_fee": round(principal * float(product["base_fee_rate"]), 2),
                "servicing_fee": round(rng.uniform(12, 85), 2),
                "late_fee": late_fee,
                "risk_grade": rng.choice(risk_grades),
            }
        )
    return loans


def _fees(rng: random.Random, loans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fee_types = [
        ("Origination Fee", "Processing", 80, 1_800),
        ("Servicing Fee", "Recurring", 10, 90),
        ("Late Payment Fee", "Penalty", 25, 450),
        ("Documentation Fee", "Processing", 15, 250),
        ("Annual Maintenance Fee", "Recurring", 20, 180),
        ("Early Repayment Fee", "Closure", 50, 600),
    ]
    rows = []
    fee_id = 1
    for loan in loans:
        opened_date = date.fromisoformat(str(loan["opened_date"]))
        for fee_type, fee_category, low, high in rng.sample(fee_types, k=rng.randint(2, 4)):
            amount = float(loan["origination_fee"]) if fee_type == "Origination Fee" else rng.uniform(low, high)
            rows.append(
                {
                    "fee_id": fee_id,
                    "loan_id": loan["loan_id"],
                    "fee_date": _date_text(opened_date + timedelta(days=rng.randint(0, 540))),
                    "fee_type": fee_type,
                    "fee_category": fee_category,
                    "fee_amount": round(amount, 2),
                    "waived": 1 if rng.random() < 0.08 else 0,
                }
            )
            fee_id += 1
    return rows


def _payments(rng: random.Random, loans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    channels = ["Auto Debit", "Bank Transfer", "Card", "Check", "Mobile"]
    rows = []
    payment_id = 1
    for loan in loans:
        opened_date = date.fromisoformat(str(loan["opened_date"]))
        payment_count = rng.randint(2, 8) if loan["status"] != "Pending" else rng.randint(0, 2)
        base_amount = max(float(loan["principal_amount"]) / max(payment_count * 8, 1), 50)
        for index in range(payment_count):
            rows.append(
                {
                    "payment_id": payment_id,
                    "loan_id": loan["loan_id"],
                    "payment_date": _date_text(opened_date + timedelta(days=30 * (index + 1) + rng.randint(0, 10))),
                    "payment_amount": round(base_amount * rng.uniform(0.75, 1.35), 2),
                    "payment_channel": rng.choice(channels),
                }
            )
            payment_id += 1
    return rows


def _insert_sql(table: str, columns: Any) -> str:
    column_list = list(columns)
    names = ", ".join(column_list)
    placeholders = ", ".join(f":{column}" for column in column_list)
    return f"INSERT INTO {table} ({names}) VALUES ({placeholders})"


def _table(
    name: str,
    row_count_estimate: int,
    columns: list[ColumnInfo],
    foreign_keys: list[ForeignKeyInfo] | None = None,
) -> TableInfo:
    return TableInfo(
        table_name=name,
        table_type="BASE TABLE",
        row_count_estimate=row_count_estimate,
        columns=columns,
        foreign_keys=foreign_keys or [],
    )


def _column(
    table: str,
    name: str,
    position: int,
    data_type: str,
    column_type: str,
    *,
    nullable: bool = False,
    key: str = "",
) -> ColumnInfo:
    return ColumnInfo(
        table_name=table,
        column_name=name,
        ordinal_position=position,
        data_type=data_type,
        column_type=column_type,
        is_nullable=nullable,
        column_key=key,
    )


def _date_text(value: date) -> str:
    return value.isoformat()
