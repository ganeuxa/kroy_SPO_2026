"""Selected checks from the team stage-I report, section 5.

Q SQL is copied from the report. C SQL implements the actions specified in its
constraint table. All writes run as kroy_app and are rolled back.
"""
import json

import pytest


@pytest.fixture
def report_db(backend_python):
    def execute(sql):
        return json.loads(backend_python(f'''import json
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from app.db import engine
with engine.connect() as connection:
 transaction = connection.begin()
 try:
  role = connection.execute(text("SELECT current_user")).scalar_one()
  result = connection.execute(text({sql!r}))
  rows = [list(row) for row in result] if result.returns_rows else []
  outcome = {{"role": role, "rows": rows, "sqlstate": None}}
 except DBAPIError as error:
  outcome = {{"role": role, "sqlstate": error.orig.sqlstate,
             "constraint": error.orig.diag.constraint_name}}
 finally:
  transaction.rollback()
print(json.dumps(outcome, default=str, ensure_ascii=False))
'''))
    return execute


def test_Q1_women_unisex_black_M_in_stock(report_db):
    result = report_db("""SELECT p.name, p.gender, p.price, v.size, v.color, v.stock
FROM products p
JOIN product_variants v ON v.product_id = p.id
WHERE p.is_active AND p.gender IN ('women', 'unisex')
  AND v.size = 'M' AND v.color = 'чёрный' AND v.stock > 0
ORDER BY p.price;""")
    assert result['sqlstate'] is None
    assert result['rows'] == [
        ['Футболка оверсайз', 'women', '1590.00', 'M', 'чёрный', 7],
        ['Худи с капюшоном', 'unisex', '3490.00', 'M', 'чёрный', 9],
    ]


def test_Q3_oversize_shirt_variants(report_db):
    result = report_db("""SELECT p.name, v.size, v.color, v.stock
FROM products p JOIN product_variants v ON v.product_id = p.id
WHERE p.name = 'Футболка оверсайз'
ORDER BY v.color, v.size;""")
    assert result['sqlstate'] is None
    assert result['rows'] == [
        ['Футболка оверсайз', 'M', 'серый', 4],
        ['Футболка оверсайз', 'M', 'чёрный', 7],
        ['Футболка оверсайз', 'S', 'чёрный', 5],
    ]


def test_Q5_order_totals_match_lines(report_db):
    result = report_db("""SELECT o.id AS order_id, o.total_amount,
       SUM(oi.quantity * oi.price_at_purchase) AS items_sum,
       o.total_amount = SUM(oi.quantity * oi.price_at_purchase) AS match
FROM orders o JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, o.total_amount
ORDER BY o.id;""")
    assert result['sqlstate'] is None
    assert result['rows'] == [
        [1, '7770.00', '7770.00', True],
        [2, '4780.00', '4780.00', True],
        [3, '2990.00', '2990.00', True],
        [4, '6990.00', '6990.00', True],
    ]


@pytest.mark.parametrize('sql,code,constraint', [
    ("UPDATE product_variants SET stock=-1 WHERE id=1", '23514', 'product_variants_stock_check'),
    ("INSERT INTO users(email,password_hash,full_name) VALUES ('anna@example.com','test-only','QA')", '23505', 'users_email_key'),
    ("""INSERT INTO orders(user_id,total_amount,delivery_method,delivery_address,contact_phone)
        VALUES (9999,100,'pickup','QA address','+79000000000')""", '23503', 'orders_user_id_fkey'),
    ("DELETE FROM orders WHERE id=1", '42501', None),
], ids=['C1-negative-stock', 'C2-duplicate-anna-email', 'C3-order-unknown-user', 'C8-delete-order-forbidden'])
def test_report_constraints(report_db, sql, code, constraint):
    result = report_db(sql)
    assert result['role'] == 'kroy_app'
    assert result['sqlstate'] == code
    assert result['constraint'] == constraint


def test_C10_app_can_read_products_and_add_favorite(report_db):
    result = report_db('SELECT id FROM products ORDER BY id')
    assert result['role'] == 'kroy_app'
    assert result['sqlstate'] is None
    assert len(result['rows']) == 8
    # Choose an unused seed pair, so this remains repeatable without deleting favorites.
    result = report_db("""INSERT INTO favorites(user_id,product_id)
SELECT u.id,p.id FROM users u CROSS JOIN products p
WHERE u.email='anna@example.com'
 AND NOT EXISTS (SELECT 1 FROM favorites f WHERE f.user_id=u.id AND f.product_id=p.id)
ORDER BY p.id LIMIT 1
RETURNING user_id,product_id""")
    assert result['role'] == 'kroy_app'
    assert result['sqlstate'] is None
    assert len(result['rows']) == 1
