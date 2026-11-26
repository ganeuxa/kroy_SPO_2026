from decimal import Decimal
import pytest


def test_health(api):
    assert api.expect('/api/health')['db'] == 'ok'


def test_seed_catalog(api):
    body = api.expect('/api/products')
    assert body['total'] == 8
    assert len(body['items']) == 8


def test_filter_choices(api):
    body = api.expect('/api/filters')
    assert body['sizes'] and body['colors'] and body['categories']
    assert Decimal(body['price_min']) <= Decimal(body['price_max'])


@pytest.mark.parametrize('query', [
    'gender=kids', 'limit=0', 'limit=101', 'offset=-1', 'sort=wrong',
    'price_min=-1', 'price_min=10&price_max=1', 'q=', 'q='+'a'*101,
    'size='+'a'*11, 'color='+'a'*41, 'category='+'a'*81,
])
def test_invalid_catalog_parameters(api, query):
    api.expect('/api/products?' + query, 422)


@pytest.mark.parametrize('query', ['q=nonexistent-qa-product', 'q=%25',
                                  'q=%27%20OR%201%3D1--', 'category=nonexistent'])
def test_empty_search_and_literal_sql_characters(api, query):
    assert api.expect('/api/products?' + query)['total'] == 0


@pytest.mark.parametrize('gender', ['men', 'women', 'unisex'])
def test_gender_filter(api, gender):
    items = api.expect('/api/products?gender=' + gender)['items']
    assert items
    assert all(item['gender'] in (gender, 'unisex') for item in items)


@pytest.mark.parametrize('order', ['asc', 'desc'])
def test_price_sort(api, order):
    prices = [Decimal(p['price']) for p in api.expect('/api/products?sort=price_'+order)['items']]
    assert prices == sorted(prices, reverse=order == 'desc')


def test_pagination(api):
    all_items = api.expect('/api/products')['items']
    body = api.expect('/api/products?limit=2&offset=2')
    assert body['items'] == all_items[2:4]
    assert body['total'] == 8


@pytest.mark.parametrize('product_id,status', [('1', 200), ('999999', 404), ('0', 422), ('-1', 422), ('abc', 422)])
def test_product_details(api, product_id, status):
    body = api.expect('/api/products/' + product_id, status)
    if status == 200:
        assert body['id'] == 1 and body['variants']
