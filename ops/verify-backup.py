"""Restore a completed snapshot into disposable containers, never the source DB."""
import pathlib,subprocess,sys,time,uuid
folder=pathlib.Path(sys.argv[1]).resolve()
assert (folder/'COMPLETE').is_file()
def run(*args,**kwargs):return subprocess.run(args,check=True,capture_output=True,**kwargs)
run('shasum','-a','256','-c','SHA256SUMS',cwd=folder)
name='kroy-qa-restore-'+uuid.uuid4().hex[:12]
try:
 run('docker','run','-d','--name',name,'--network','none','--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_USER=kroy_owner','-e','POSTGRES_DB=kroy','postgres:16-alpine')
 for i in range(60):
  if subprocess.run(['docker','exec',name,'pg_isready','-U','kroy_owner'],capture_output=True).returncode==0:break
  time.sleep(1)
 run('docker','exec',name,'psql','-U','kroy_owner','-d','kroy','-c','CREATE ROLE kroy_app NOLOGIN')
 with (folder/'database.dump').open('rb') as f:run('docker','exec','-i',name,'pg_restore','--exit-on-error','-U','kroy_owner','-d','kroy',stdin=f)
 result=run('docker','exec',name,'psql','-U','kroy_owner','-d','kroy','-At','-c','SELECT (SELECT count(*) FROM orders),(SELECT count(*) FROM payments),(SELECT count(*) FROM product_images),(SELECT count(*) FROM schema_migrations)')
 print('Restored orders|payments|images|migrations:',result.stdout.decode().strip())
 # Extract raw media on disposable storage, check archive is fully readable.
 run('docker','exec',name,'mkdir','/tmp/media-restore')
 with (folder/'media.tar.gz').open('rb') as f:run('docker','exec','-i',name,'tar','-xzf','-','-C','/tmp/media-restore',stdin=f)
 print('PASS: SHA256, database restore, media archive extraction; source untouched')
finally:
 subprocess.run(['docker','rm','-f',name],capture_output=True)
