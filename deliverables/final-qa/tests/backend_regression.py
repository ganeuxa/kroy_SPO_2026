"""Integration regressions against a disposable QA PostgreSQL and running backend.

Run in QA backend with PYTHONPATH=/app python /tmp/backend_regression.py.
Uses unittest from stdlib, the actual service code and separate DB sessions.
"""
import json
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from sqlalchemy import select, text
from app.db import SessionLocal
from app.models import Payment, Order
from app.routers import payments
from app.schemas import TestProviderResultIn


def request(path, data=None, token=None, method=None, headers=None):
    h={'Content-Type':'application/json',**(headers or {})}
    if token: h['Authorization']='Bearer '+token
    req=Request('http://127.0.0.1:8000/api'+path,
        data=json.dumps(data).encode() if data is not None else None,headers=h,method=method)
    try:
        with urlopen(req,timeout=20) as r:
            raw=r.read(); return r.status,json.loads(raw) if raw else None
    except HTTPError as e:
        raw=e.read(); return e.code,json.loads(raw) if raw else None


class PaymentConcurrency(unittest.TestCase):
    def setUp(self):
        _,auth=request('/auth/login',{'email':'admin@kroy.test','password':'KroyAdmin-2026'})
        self.admin=auth['access_token']
        _,auth=request('/auth/register',{'email':uuid.uuid4().hex+'@example.com',
            'password':'Regression-2026','full_name':'Regression'})
        self.token=auth['access_token']
        _,filters=request('/filters')
        code,p=request('/admin/products',{'name':'Regression '+uuid.uuid4().hex,
            'category_id':filters['categories'][0]['id'],'gender':'unisex','price':'100.00'},self.admin)
        self.assertEqual(code,201); self.pid=p['id']
        _,v=request(f'/admin/products/{self.pid}/variants',{'size':'M','color':'Test',
            'sku':uuid.uuid4().hex.upper(),'initial_stock':5},self.admin)
        self.vid=v['id']
        request('/cart',{'variant_id':self.vid,'quantity':2},self.token)
        code,self.order=request('/orders',{'delivery_method':'courier',
            'delivery_address':'Test address','contact_phone':'+79990001234'},self.token)
        self.assertEqual(code,201)
        code,self.payment=request(f"/orders/{self.order['id']}/payments",token=self.token,
            method='POST',headers={'Idempotency-Key':str(uuid.uuid4())})
        self.assertEqual(code,201)
        self.provider=uuid.UUID(self.payment['confirmation_url'].rsplit('/',1)[1])

    def tearDown(self):
        request(f'/admin/products/{self.pid}',{'is_active':False},self.admin,method='PATCH')

    def test_concurrent_success_then_failure_is_idempotent(self):
        self._concurrent_results('succeeded','failed','paid')

    def test_concurrent_failure_then_success_is_idempotent(self):
        self._concurrent_results('failed','succeeded','new')

    def _concurrent_results(self, first, second, expected_order):
        # Force both requests to read before either obtains the order lock.
        # The failed notification continues after successful transaction commits.
        target=getattr(payments,'process_notification',payments.test_provider_complete)
        import sys
        module=sys.modules[target.__module__]
        original=module.get_order
        barrier=Barrier(2); committed=Event()
        def locked(db,*args,**kwargs):
            barrier.wait(timeout=10)
            if db.info['result']==second:
                self.assertTrue(committed.wait(10))
            return original(db,*args,**kwargs)
        def run(result):
            with SessionLocal() as db:
                db.info['result']=result
                try:
                    return target(data=TestProviderResultIn(result=result),
                        provider_payment_id=self.provider,db=db).status
                finally:
                    if result==first:committed.set()
        with patch.object(module,'get_order',locked):
            with ThreadPoolExecutor(max_workers=2) as pool:
                a=pool.submit(run,first); b=pool.submit(run,second)
                results=[a.result(),b.result()]
        with SessionLocal() as db:
            status=db.scalar(select(Payment.status).where(Payment.id==self.payment['id']))
            order=db.scalar(select(Order.status).where(Order.id==self.order['id']))
        self.assertEqual((results,status,order),([first,first],first,expected_order))

    def test_cancel_while_notification_waits_keeps_cancelled(self):
        from app import payment_service
        from app.order_service import cancel_order
        original=payment_service.get_order
        def cancel_then_lock(db,*args,**kwargs):
            with SessionLocal() as other:
                order=original(other,self.order['id'],lock=True)
                cancel_order(other,order,'customer',changed_by=order.user_id)
                other.commit()
            return original(db,*args,**kwargs)
        with patch.object(payment_service,'get_order',cancel_then_lock):
            with SessionLocal() as db:
                result=payment_service.process_notification(TestProviderResultIn(result='failed'),self.provider,db)
                self.assertEqual(result.status,'cancelled')
        with SessionLocal() as db:
            self.assertEqual(db.scalar(text('SELECT stock FROM product_variants WHERE id=:id'),{'id':self.vid}),5)

    def test_expiry_releases_stock_once_and_cancels_payment(self):
        from app.order_service import expire_orders
        with SessionLocal() as db:
            db.execute(text("UPDATE orders SET expires_at=now()-interval '1 minute' WHERE id=:id"),
                {'id':self.order['id']}); db.commit()
            expire_orders(db); expire_orders(db)
            stock=db.scalar(text('SELECT stock FROM product_variants WHERE id=:id'),{'id':self.vid})
            status=db.scalar(select(Payment.status).where(Payment.id==self.payment['id']))
            history=db.scalar(text("SELECT count(*) FROM order_status_history WHERE order_id=:id AND to_status='cancelled'"),{'id':self.order['id']})
            self.assertEqual((stock,status,history),(5,'cancelled',1))
        code,result=request('/test-provider/payments/'+str(self.provider),{'result':'succeeded'})
        self.assertEqual((code,result['status']),(200,'cancelled'))


if __name__=='__main__':
    unittest.main(verbosity=2)
