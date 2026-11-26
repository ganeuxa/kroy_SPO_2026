"""Stage III creates its own products; seed stock is never consumed."""
import uuid
import pytest

@pytest.fixture
def admin(api):
    return api.expect('/api/auth/login', data={'email':'admin@kroy.test','password':'KroyAdmin-2026'})['access_token']

@pytest.fixture
def customer(api):
    def create():
        return api.expect('/api/auth/register', 201, {'email':f'qa-stage3-{uuid.uuid4().hex}@example.com','password':'Stage3-QA-2026','full_name':'QA Stage III'})['access_token']
    return create

@pytest.fixture
def product(api, admin):
    category = api.expect('/api/filters')['categories'][0]['id']
    p = api.expect('/api/admin/products',201,{'name':'QA '+uuid.uuid4().hex,'category_id':category,'gender':'unisex','price':'123.45'},admin)
    try:
        v = api.expect(f"/api/admin/products/{p['id']}/variants",201,{'size':'M','color':'QA','sku':'QA-'+uuid.uuid4().hex[:20].upper(),'initial_stock':10},admin)
        yield {'id':p['id'],'variant':v['id'],'stock':10,'price':'123.45'}
    finally:
        api.expect(f"/api/admin/products/{p['id']}",data={'is_active':False},token=admin,method='PATCH')

@pytest.fixture
def checkout(api, product):
    def create(token, quantity=2, key=None):
        api.expect('/api/cart',data={'variant_id':product['variant'],'quantity':quantity},token=token)
        return api.expect('/api/orders',201,{'delivery_method':'courier','delivery_address':'QA address 123','contact_phone':'+79990001234'},token,extra_headers={'Idempotency-Key':key or str(uuid.uuid4())})
    return create

@pytest.fixture
def stock(api, admin, product):
    def read():
        p=api.expect(f"/api/admin/products/{product['id']}",token=admin)
        return next(v['stock'] for v in p['variants'] if v['id']==product['variant'])
    return read
