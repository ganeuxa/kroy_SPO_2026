import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal
import pytest

pytestmark=pytest.mark.stage3
DELIVERY={'delivery_method':'courier','delivery_address':'QA address 123','contact_phone':'+79990001234'}

@pytest.mark.smoke
def test_checkout_cancel_and_history(api,customer,checkout,stock):
    token=customer(); order=checkout(token)
    assert order['status']=='new' and Decimal(order['total_amount'])==Decimal('246.90')
    assert order['items_count']==2 and stock()==8
    assert api.expect('/api/cart',token=token)['items']==[]
    assert api.expect('/api/orders',token=token)['items'][0]['id']==order['id']
    result=api.expect(f"/api/orders/{order['id']}/cancel",token=token,method='POST')
    assert result['status']=='cancelled' and result['cancel_reason']=='customer'
    assert stock()==10
    api.expect(f"/api/orders/{order['id']}/cancel",409,token=token,method='POST')
    assert stock()==10
    assert [h['to_status'] for h in result['history']]==['new','cancelled']

def test_checkout_repeat_does_not_reserve_twice(api,customer,checkout,stock):
    token=customer(); key=str(uuid.uuid4()); order=checkout(token,key=key)
    again=api.expect('/api/orders',200,DELIVERY,token,extra_headers={'Idempotency-Key':key})
    assert again['id']==order['id'] and stock()==8
    assert api.expect('/api/orders',token=token)['total']==1

@pytest.mark.parametrize('change',[{'delivery_method':'bad'},{'contact_phone':'bad'},{'delivery_address':''},{'pickup_point_id':1},{'delivery_method':'pickup','pickup_point_id':1}])
def test_delivery_validation(api,customer,change):
    api.expect('/api/orders',422,{**DELIVERY,**change},customer())

def test_empty_cart(api,customer):
    api.expect('/api/orders',409,DELIVERY,customer())

@pytest.mark.parametrize('method,path',[('GET','/api/orders'),('GET','/api/orders/1'),('POST','/api/orders'),('POST','/api/orders/1/cancel'),('GET','/api/payments/1')])
def test_guest_denied(api,method,path):
    api.expect(path,401,data=DELIVERY if path=='/api/orders' and method=='POST' else None,method=method)

@pytest.mark.parametrize('method,suffix',[('GET',''),('POST','/cancel'),('POST','/payments')])
def test_foreign_order_denied(api,customer,checkout,method,suffix):
    order=checkout(customer())
    api.expect(f"/api/orders/{order['id']}"+suffix,404,token=customer(),method=method,extra_headers={'Idempotency-Key':str(uuid.uuid4())})

@pytest.mark.smoke
def test_payment_success_and_admin_delivery(api,customer,checkout,admin,stock):
    token=customer(); order=checkout(token); oid=order['id']; key=str(uuid.uuid4())
    payment=api.expect(f'/api/orders/{oid}/payments',201,token=token,method='POST',extra_headers={'Idempotency-Key':key})
    repeat=api.expect(f'/api/orders/{oid}/payments',200,token=token,method='POST',extra_headers={'Idempotency-Key':key})
    assert repeat['id']==payment['id'] and payment['amount']==order['total_amount']
    callback='/api/test-provider/payments/'+payment['confirmation_url'].rsplit('/',1)[1]
    assert api.expect(callback,data={'result':'succeeded'})['status']=='succeeded'
    assert api.expect(callback,data={'result':'succeeded'})['id']==payment['id']
    api.expect(f"/api/payments/{payment['id']}",404,token=customer())
    assert api.expect(f'/api/orders/{oid}',token=token)['status']=='paid'
    api.expect(f'/api/orders/{oid}/cancel',409,token=token,method='POST')
    api.expect(f'/api/orders/{oid}/payments',409,token=token,method='POST',extra_headers={'Idempotency-Key':str(uuid.uuid4())})
    api.expect(f'/api/admin/orders/{oid}/status',409,{'status':'delivered'},admin)
    for status in ['shipped','delivered']:
        assert api.expect(f'/api/admin/orders/{oid}/status',data={'status':status},token=admin)['status']==status
    assert stock()==8
    detail=api.expect(f'/api/orders/{oid}',token=token)
    assert [h['to_status'] for h in detail['history']]==['new','paid','shipped','delivered']
    assert len(detail['payments'])==1

def test_failed_payment_retry_and_cancel(api,customer,checkout,stock):
    token=customer(); order=checkout(token); path=f"/api/orders/{order['id']}/payments"
    api.expect(path,422,token=token,method='POST')
    p=api.expect(path,201,token=token,method='POST',extra_headers={'Idempotency-Key':str(uuid.uuid4())})
    api.expect(path,409,token=token,method='POST',extra_headers={'Idempotency-Key':str(uuid.uuid4())})
    callback='/api/test-provider/payments/'+p['confirmation_url'].rsplit('/',1)[1]
    assert api.expect(callback,data={'result':'failed','failure_reason':'QA decline'})['status']=='failed'
    assert api.expect(f"/api/orders/{order['id']}",token=token)['status']=='new'
    p2=api.expect(path,201,token=token,method='POST',extra_headers={'Idempotency-Key':str(uuid.uuid4())})
    assert p2['id']!=p['id']
    api.expect(f"/api/orders/{order['id']}/cancel",token=token,method='POST')
    assert api.expect(f"/api/payments/{p2['id']}",token=token)['status']=='cancelled'
    assert stock()==10

def test_cart_update_delete_and_ownership(api,customer,product):
    token=customer(); other=customer()
    cart=api.expect('/api/cart',data={'variant_id':product['variant'],'quantity':1},token=token)
    path=f"/api/cart/items/{cart['items'][0]['id']}"
    api.expect(path,404,{'quantity':2},other,method='PATCH')
    api.expect(path,404,token=other,method='DELETE')
    for quantity,code in [(0,422),(11,409),(3,200)]:
        result=api.expect(path,code,{'quantity':quantity},token,method='PATCH')
        if code==200: assert result['total']=='370.35'
    assert api.expect(path,token=token,method='DELETE')['items']==[]
    api.expect(path,404,token=token,method='DELETE')

def test_last_unit_cannot_be_sold_twice(api,admin,product,customer,stock):
    api.expect(f"/api/admin/variants/{product['variant']}/stock-movements",201,{'delta':-9,'comment':'QA last unit'},admin)
    tokens=[customer(),customer()]
    for token in tokens: api.expect('/api/cart',data={'variant_id':product['variant'],'quantity':1},token=token)
    barrier=Barrier(2)
    def buy(token):
        barrier.wait(timeout=10)
        return api.request('/api/orders',DELIVERY,token)
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(buy,tokens))
    assert sorted(r[0] for r in results)==[201,409]
    assert stock()==0
    assert sum(api.expect('/api/orders',token=t)['total'] for t in tokens)==1

@pytest.mark.parametrize('role',['guest','customer'])
@pytest.mark.parametrize('method,path,data',[
('GET','/api/admin/products',None),('POST','/api/admin/products',{}),('PATCH','/api/admin/products/1',{}),
('POST','/api/admin/products/1/variants',{}),('PATCH','/api/admin/variants/1',{}),('POST','/api/admin/variants/1/stock-movements',{}),
('GET','/api/admin/variants/1/stock-movements',None),('GET','/api/admin/orders',None),('GET','/api/admin/orders/1',None),
('POST','/api/admin/orders/1/status',{}),('POST','/api/admin/products/1/images',None),('PATCH','/api/admin/images/1',{}),('DELETE','/api/admin/images/1',None)])
def test_admin_permissions(api,customer,role,method,path,data):
    api.expect(path,401 if role=='guest' else 403,data,customer() if role=='customer' else None,method=method)

def test_admin_stock_visibility_and_unique_sku(api,admin,product,stock):
    path=f"/api/admin/variants/{product['variant']}/stock-movements"
    assert api.expect(path,201,{'delta':3,'comment':'QA receipt'},admin)['stock_after']==13
    api.expect(path,409,{'delta':-14,'comment':'QA impossible'},admin)
    api.expect(path,422,{'delta':0,'comment':'QA zero'},admin)
    assert stock()==13
    assert sum(m['delta'] for m in api.expect(path,token=admin)['items'])==13
    p=api.expect(f"/api/admin/products/{product['id']}",token=admin)
    v=p['variants'][0]
    api.expect(f"/api/admin/products/{product['id']}/variants",409,{'size':'L','color':'other','sku':v['sku']},admin)
    api.expect(f"/api/admin/products/{product['id']}",data={'price':'200.00'},token=admin,method='PATCH')
    assert api.expect(f"/api/products/{product['id']}")['price']=='200.00'
    api.expect(f"/api/admin/products/{product['id']}",data={'is_active':False},token=admin,method='PATCH')
    api.expect(f"/api/products/{product['id']}",404)
