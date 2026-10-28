from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import pytest


def test_new_cart_is_empty(api, account):
    cart = api.expect('/api/cart', token=account['token'])
    assert cart['items'] == []
    assert Decimal(cart['total']) == 0
    assert cart['total_quantity'] == 0


@pytest.mark.parametrize('data', [{'variant_id': 0}, {'variant_id': 1, 'quantity': 0},
    {'variant_id': 1, 'quantity': -1}, {'variant_id': 1, 'quantity': 100},
    {'variant_id': 1, 'quantity': 1.5}, {}])
def test_invalid_cart_input(api, account, data):
    api.expect('/api/cart', 422, data, account['token'])


def test_unknown_variant(api, account):
    api.expect('/api/cart', 404, {'variant_id': 999999}, account['token'])


def test_add_and_totals(api, account):
    cart = api.expect('/api/cart', data={'variant_id': 1, 'quantity': 2}, token=account['token'])
    assert cart['total_quantity'] == 2
    assert len(cart['items']) == 1
    assert cart['items'][0]['variant_id'] == 1
    assert Decimal(cart['total']) == sum(Decimal(i['price'])*i['quantity'] for i in cart['items'])


def test_repeated_add_merges_rows(api, account):
    for _ in range(2):
        cart = api.expect('/api/cart', data={'variant_id': 1}, token=account['token'])
    assert len(cart['items']) == 1 and cart['total_quantity'] == 2


def test_stock_overflow(api, account):
    stock = next(v['stock'] for v in api.expect('/api/products/1')['variants'] if v['id'] == 1)
    assert 0 < stock < 99, 'Seed fixture must allow stock overflow with quantity <= 99'
    api.expect('/api/cart', 409, {'variant_id': 1, 'quantity': stock+1}, account['token'])


def test_rejected_add_preserves_cart(api, account):
    before = api.expect('/api/cart', data={'variant_id': 1}, token=account['token'])
    api.expect('/api/cart', 409, {'variant_id': 1, 'quantity': 99}, account['token'])
    assert api.expect('/api/cart', token=account['token']) == before


def test_cart_user_isolation(api, account, user_data):
    api.expect('/api/cart', data={'variant_id': 1}, token=account['token'])
    other = api.expect('/api/auth/register', 201, {**user_data, 'email': 'other-'+user_data['email']})
    assert api.expect('/api/cart', token=other['access_token'])['items'] == []


def test_concurrent_adds_no_lost_update(api, account):
    with ThreadPoolExecutor(max_workers=3) as pool:
        statuses = list(pool.map(lambda _: api.request('/api/cart', {'variant_id': 1}, account['token'])[0], range(3)))
    assert statuses == [200]*3
    cart = api.expect('/api/cart', token=account['token'])
    assert len(cart['items']) == 1 and cart['total_quantity'] == 3
