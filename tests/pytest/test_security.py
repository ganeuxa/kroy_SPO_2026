import pytest


@pytest.mark.parametrize('kind', ['expired', 'unknown-user', 'invalid-subject', 'wrong-signature', 'no-expiry', 'unsigned'])
def test_rejected_jwt(api, backend_python, kind):
    token = backend_python(f'''from datetime import datetime,timedelta,timezone
import jwt
from app.config import settings
kind={kind!r}
payload={{'sub':'2','exp':datetime.now(timezone.utc)+timedelta(minutes=5)}}
if kind=='expired': payload['exp']=datetime.now(timezone.utc)-timedelta(seconds=10)
if kind=='unknown-user': payload['sub']='9999999'
if kind=='invalid-subject': payload['sub']='invalid'
if kind=='no-expiry': del payload['exp']
key='wrong-key' if kind=='wrong-signature' else settings.jwt_secret
if kind=='unsigned': print(jwt.encode(payload,'',algorithm='none'))
else: print(jwt.encode(payload,key,algorithm='HS256'))
''').strip()
    api.expect('/api/auth/me', 401, token=token)


def test_blocked_login(api, account, set_db_value):
    set_db_value('users', 'is_active', account['id'], False)
    api.expect('/api/auth/login', 403, {'email': account['email'], 'password': account['password']})


def test_blocked_token(api, account, set_db_value):
    set_db_value('users', 'is_active', account['id'], False)
    api.expect('/api/cart', 401, token=account['token'])


@pytest.mark.parametrize('scenario', ['detail', 'add', 'catalog'])
def test_hidden_product(api, account, set_db_value, scenario):
    set_db_value('products', 'is_active', 1, False)
    if scenario == 'detail':
        api.expect('/api/products/1', 404)
    elif scenario == 'add':
        api.expect('/api/cart', 404, {'variant_id': 1}, account['token'])
    else:
        assert all(p['id'] != 1 for p in api.expect('/api/products')['items'])


def test_zero_stock(api, account, set_db_value):
    set_db_value('product_variants', 'stock', 1, 0)
    api.expect('/api/cart', 409, {'variant_id': 1}, account['token'])
