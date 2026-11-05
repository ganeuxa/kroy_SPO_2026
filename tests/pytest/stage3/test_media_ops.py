import base64
import hashlib
import json
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
import os
BASE_URL='http://127.0.0.1:18080' if os.getenv('QA_NGINX')=='1' else 'http://127.0.0.1:18000'

pytestmark=pytest.mark.stage3
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')

def upload(product,token,data):
    boundary='qa'+uuid.uuid4().hex
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="qa.png"\r\nContent-Type: image/png\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
    req=Request(BASE_URL+f'/api/admin/products/{product}/images',data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'multipart/form-data; boundary='+boundary})
    try:
        with urlopen(req,timeout=30) as r:return r.status,json.load(r)
    except HTTPError as e:return e.code,None

@pytest.mark.smoke
def test_photo_roundtrip(api,admin,product):
    code,img=upload(product['id'],admin,PNG)
    assert code==201
    try:
        with urlopen(BASE_URL+img['image_url'],timeout=10) as r:
            assert r.status==200 and hashlib.sha256(r.read()).digest()==hashlib.sha256(PNG).digest()
        assert img['image_url'] in api.expect(f"/api/products/{product['id']}")['image_urls']
        updated=api.expect(f"/api/admin/images/{img['id']}",data={'sort_order':2},token=admin,method='PATCH')
        assert updated['sort_order']==2
    finally:api.expect(f"/api/admin/images/{img['id']}",204,token=admin,method='DELETE')
    assert img['image_url'] not in api.expect(f"/api/products/{product['id']}")['image_urls']

@pytest.mark.parametrize('data,code',[(b'not an image',415),(PNG+b'0'*(5*1024*1024),413)])
def test_photo_validation(api,admin,product,data,code):
    assert upload(product['id'],admin,data)[0]==code

@pytest.mark.ops
def test_database_backup_restores_into_separate_database(api,compose):
    # Only this uniquely named temporary database is dropped; source remains untouched.
    name='qa_restore_'+uuid.uuid4().hex
    script='''set -eu
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/qa-restore.dump
pg_restore --list /tmp/qa-restore.dump >/dev/null
createdb -U "$POSTGRES_USER" '''+name+'''
trap 'dropdb -U "$POSTGRES_USER" '''+name+'''; rm -f /tmp/qa-restore.dump' EXIT
pg_restore --exit-on-error -U "$POSTGRES_USER" -d '''+name+''' /tmp/qa-restore.dump
for database in "$POSTGRES_DB" '''+name+'''; do
psql -U "$POSTGRES_USER" -d "$database" -At -c "SELECT (SELECT count(*) FROM orders),(SELECT count(*) FROM order_items),(SELECT count(*) FROM payments),(SELECT count(*) FROM stock_movements),(SELECT sum(stock) FROM product_variants),(SELECT count(*) FROM schema_migrations);"
done
'''
    out=compose('exec','-T','db','sh','-c',script)
    rows=[r for r in out.splitlines() if '|' in r]
    assert len(rows)==2 and rows[0]==rows[1]
