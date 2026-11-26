"""Small read-only localhost HTTP load test, no external dependencies."""
import concurrent.futures,json,time,statistics,urllib.request,urllib.error
from pathlib import Path
URL='http://127.0.0.1:18080/api/products?limit=24'
def one(_):
 start=time.perf_counter()
 try:
  with urllib.request.urlopen(URL,timeout=15) as r: code=r.status;r.read()
 except urllib.error.HTTPError as e:code=e.code
 except OSError:code=0
 return (time.perf_counter()-start)*1000,code
result=[]
for concurrency in [1,5,10]:
 for i in range(5):one(i)
 start=time.perf_counter()
 with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool: rows=list(pool.map(one,range(100)))
 elapsed=time.perf_counter()-start;lat=sorted(x[0] for x in rows)
 result.append(dict(concurrency=concurrency,requests=100,duration_s=round(elapsed,3),rps=round(100/elapsed,2),median_ms=round(statistics.median(lat),2),p95_ms=round(lat[94],2),max_ms=round(max(lat),2),errors=sum(c!=200 for _,c in rows)))
print(json.dumps({'url':URL,'warmups_per_case':5,'results':result},indent=2))
