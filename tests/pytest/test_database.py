import json
import pytest

CASES = [('Unique email', 'INSERT INTO users(email,password_hash,full_name) SELECT email,password_hash,full_name FROM users LIMIT 1', '23505'), ('User name NOT NULL', "INSERT INTO users(email,password_hash,full_name) VALUES ('qa-null@example.com','x',NULL)", '23502'), ('Role CHECK', "INSERT INTO users(email,password_hash,full_name,role) VALUES ('qa-role@example.com','x','QA','root')", '23514'), ('Price positive', 'UPDATE products SET price=-1 WHERE id=1', '23514'), ('Stock nonnegative', 'UPDATE product_variants SET stock=-1 WHERE id=1', '23514'), ('Gender CHECK', "UPDATE products SET gender='wrong' WHERE id=1", '23514'), ('Product category FK', 'UPDATE products SET category_id=999999 WHERE id=1', '23503'), ('Cart quantity CHECK', 'INSERT INTO cart_items(user_id,variant_id,quantity) VALUES (1,1,0)', '23514'), ('Cart user FK', 'INSERT INTO cart_items(user_id,variant_id,quantity) VALUES (999999,1,1)', '23503'), ('Cart variant FK', 'INSERT INTO cart_items(user_id,variant_id,quantity) VALUES (1,999999,1)', '23503'), ('Rating bounds', 'INSERT INTO reviews(user_id,product_id,rating) VALUES (1,1,6)', '23514'), ('Cannot DROP table', 'DROP TABLE reviews', '42501'), ('Cannot delete order', 'DELETE FROM orders WHERE id=-1', '42501')]

@pytest.mark.parametrize('name,sql,expected', CASES, ids=[c[0] for c in CASES])
def test_database_constraint_or_privilege(api, backend_python, name, sql, expected):
    script = f"""from app.db import engine
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
import json
with engine.connect() as c:
 tx=c.begin()
 try:
  c.execute(text({sql!r}))
  code=None
 except DBAPIError as e:
  code=getattr(e.orig,'sqlstate',None)
 finally:
  tx.rollback()
print(json.dumps(code))
"""
    actual = json.loads(backend_python(script))
    assert actual == expected, f'{name}: SQLSTATE {actual}, expected {expected}'
