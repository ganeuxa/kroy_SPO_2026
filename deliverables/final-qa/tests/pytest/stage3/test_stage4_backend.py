"""Stage IV backend, access-control and OpenAPI regressions on the shared QA stack."""
import json
import re
import pytest


def test_logout_revokes_all_sessions_and_new_login_works(api, account):
    second=api.expect('/api/auth/login',data={'email':account['email'],'password':account['password']})['access_token']
    assert second != account['token']
    api.expect('/api/auth/logout',204,token=account['token'],method='POST')
    for token in (account['token'],second):
        for path in ('/api/auth/me','/api/cart','/api/orders'):
            api.expect(path,401,token=token)
        api.expect('/api/auth/logout',401,token=token,method='POST')
    fresh=api.expect('/api/auth/login',data={'email':account['email'],'password':account['password']})['access_token']
    api.expect('/api/auth/me',token=fresh)


def test_guest_logout_denied(api):
    api.expect('/api/auth/logout',401,method='POST')


@pytest.mark.parametrize('mode',['expired','wrong-signature','bad-subject','bad-version'])
def test_invalid_signed_tokens(api, account, backend_python, mode):
    script=f'''import jwt
from app.config import settings
from datetime import datetime, timedelta, timezone
p={{"sub":str({account['id']}),"exp":datetime.now(timezone.utc)+timedelta(minutes=5),"ver":0}}
mode={mode!r}
if mode=='expired':p['exp']=datetime.now(timezone.utc)-timedelta(seconds=1)
if mode=='bad-subject':p['sub']='9'*100
if mode=='bad-version':p['ver']=[]
print(jwt.encode(p,'wrong-secret' if mode=='wrong-signature' else settings.jwt_secret,algorithm='HS256'))
'''
    token=backend_python(script).strip()
    api.expect('/api/auth/me',401,token=token)


def test_role_demotion_immediate(api, account, backend_python):
    def role(value):
        backend_python(f'''from app.db import engine
from sqlalchemy import text
with engine.begin() as c:c.execute(text("UPDATE users SET role=:r WHERE id=:id"),{{"r":{value!r},"id":{account['id']}}})
''')
    try:
        role('admin')
        token=api.expect('/api/auth/login',data={'email':account['email'],'password':account['password']})['access_token']
        api.expect('/api/admin/products',token=token)
        role('customer')
        api.expect('/api/admin/products',403,token=token)
    finally:role('customer')


@pytest.mark.parametrize('role',['guest','customer'])
def test_every_admin_operation_denied_from_live_contract(api, account, role):
    schema=api.expect('/api/openapi.json')
    checked=[]
    for path,operations in schema['paths'].items():
        if not path.startswith('/api/admin/'):continue
        for method,op in operations.items():
            if method not in ('get','post','patch','delete','put'):continue
            concrete=re.sub(r'\{[^}]+\}','1',path)
            api.expect(concrete,401 if role=='guest' else 403,
                data={} if 'requestBody' in op and 'application/json' in op['requestBody']['content'] else None,
                token=account['token'] if role=='customer' else None,method=method.upper())
            assert '401' in op['responses'] and '403' in op['responses']
            checked.append((method,path))
    assert len(checked)>=14


def test_openapi_and_response_shapes(api, account):
    schema=api.expect('/api/openapi.json')
    assert schema['info']['version']=='0.4.0'
    assert '204' in schema['paths']['/api/auth/logout']['post']['responses']
    assert 'content' not in schema['paths']['/api/auth/logout']['post']['responses']['204']
    refs=[]
    def walk(value):
        if isinstance(value,dict):
            if '$ref' in value:refs.append(value['$ref'])
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(schema)
    for ref in refs:
        target=schema
        for part in ref.removeprefix('#/').split('/'):target=target[part]
    invalid=api.expect('/api/products?limit=0',422)
    business=api.expect('/api/products?price_min=100&price_max=1',422)
    assert isinstance(invalid['detail'],list) and isinstance(business['detail'],str)
    variants=schema['paths']['/api/products']['get']['responses']['422']['content']['application/json']['schema']['anyOf']
    assert len(variants)==2
    assert schema['paths']['/api/auth/me']['get']['security']
    assert 'password_hash' not in api.expect('/api/auth/me',token=account['token'])


def test_catalog_projection_tracks_live_stock_price_visibility(api, admin, product):
    def card():
        matches=api.expect('/api/products?q=QA&limit=100')['items']
        return next(p for p in matches if p['id']==product['id'])
    assert card()['in_stock'] is True
    api.expect(f"/api/admin/variants/{product['variant']}/stock-movements",201,
        {'delta':-10,'comment':'Stage IV stock check'},admin)
    assert card()['in_stock'] is False
    api.expect(f"/api/admin/products/{product['id']}",data={'price':'234.56'},token=admin,method='PATCH')
    assert card()['price']=='234.56'
    api.expect(f"/api/admin/products/{product['id']}",data={'is_active':False},token=admin,method='PATCH')
    assert all(p['id']!=product['id'] for p in api.expect('/api/products?q=QA&limit=100')['items'])


def test_actual_responses_validate_against_openapi(api, account, checkout, admin):
    from jsonschema import Draft202012Validator
    schema=api.expect('/api/openapi.json')
    order=checkout(account['token'])
    cases=[('/api/health','/api/health',None),
        ('/api/products','/api/products',None),
        ('/api/products/1','/api/products/{product_id}',None),
        ('/api/products?limit=0','/api/products',None),
        ('/api/products?price_min=2&price_max=1','/api/products',None),
        ('/api/auth/me','/api/auth/me',account['token']),
        ('/api/auth/me','/api/auth/me',None),
        ('/api/cart','/api/cart',account['token']),
        (f"/api/orders/{order['id']}",'/api/orders/{order_id}',account['token']),
        ('/api/admin/products','/api/admin/products',account['token']),
        ('/api/admin/products','/api/admin/products',admin)]
    for path,template,token in cases:
        status,body=api.request(path,token=token)
        spec=schema['paths'][template]['get']['responses'][str(status)]['content']['application/json']['schema']
        Draft202012Validator({'components':schema['components'],**spec}).validate(body)
