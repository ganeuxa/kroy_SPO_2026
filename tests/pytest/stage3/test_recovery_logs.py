import base64
import json
import uuid
from datetime import datetime, timezone
import pytest

pytestmark=pytest.mark.stage3

@pytest.mark.ops
def test_media_backup_restore_checksum(backend_python):
    # Own object only. Backup, remove, restore and compare bytes via S3 API.
    key='qa-recovery/'+uuid.uuid4().hex+'.txt'
    result=backend_python(f'''import hashlib,io,json
from app.storage import _client,_ensure_bucket
from app.config import settings
c=_client();_ensure_bucket(c);b=settings.minio_bucket;k={key!r}
payload=b'QA media recovery evidence'
try:
 c.put_object(b,k,io.BytesIO(payload),len(payload),'text/plain')
 r=c.get_object(b,k)
 try: backup=r.read()
 finally:r.close();r.release_conn()
 c.remove_object(b,k)
 missing=False
 try:c.stat_object(b,k)
 except Exception as e:
  missing=getattr(e,'code',None)=='NoSuchKey'
 assert missing
 c.put_object(b,k,io.BytesIO(backup),len(backup),'text/plain')
 r=c.get_object(b,k)
 try:restored=r.read()
 finally:r.close();r.release_conn()
 print(json.dumps({{'match':hashlib.sha256(payload).hexdigest()==hashlib.sha256(restored).hexdigest()}}))
finally:c.remove_object(b,k)
''')
    assert json.loads(result)['match']

def test_logs_do_not_contain_canary_secrets(api,compose):
    start=datetime.now(timezone.utc).isoformat()
    unique=uuid.uuid4().hex
    email=f'qa-log-{unique}@example.com';password='Secret-'+unique
    phone='+79991239876';name='QA-log-'+unique
    response=api.expect('/api/auth/register',201,{'email':email,'password':password,'full_name':name,'phone':phone})
    api.expect('/api/auth/me',token=response['access_token'])
    logs=compose('logs','--since',start,'backend','nginx')
    for value in [email,password,phone,name,response['access_token']]:
        assert value not in logs,'Sensitive canary value found in logs (value redacted)'
    assert '/api/auth/register' in logs and '/api/auth/me' in logs

@pytest.mark.ops
def test_migration_repeat_and_changed_checksum(compose):
    assert 'Миграции применены' in compose('run','--rm','migrate')
    script='''import os,pathlib,shutil,subprocess,sys
shutil.copytree('/app/migrations','/dev/shm/qa-migrations')
p=next(pathlib.Path('/dev/shm/qa-migrations').glob('V002__*.sql'))
p.write_text(p.read_text()+'\\n-- QA changed checksum\\n')
r=subprocess.run([sys.executable,'-m','app.migrate'],env={**os.environ,'MIGRATIONS_DIR':'/dev/shm/qa-migrations'},capture_output=True,text=True)
assert r.returncode!=0
assert 'файл изменён после применения' in r.stderr
print('checksum protection OK')
'''
    result=compose('run','--rm','--no-deps','--entrypoint','python','migrate','-c',script)
    assert 'checksum protection OK' in result
