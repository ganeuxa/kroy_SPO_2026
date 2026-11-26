"""Run inside QA backend: python /tmp/benchmark_catalog.py before|after.

Creates 1000 synthetic products only in a disposable QA database. Never run on production.
Uses the real route function with a fresh Session per request; excludes HTTP/network overhead.
"""
import hashlib
import importlib.util
import json
import os
import statistics
import sys
import time

from sqlalchemy import event, text
from app.db import engine, SessionLocal

route_file = os.getenv("BENCH_PRODUCTS_FILE")
if route_file:
    spec = importlib.util.spec_from_file_location("app.routers._benchmark_products", route_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load benchmark route module: {route_file}")
    route = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(route)
    list_products = route.list_products
else:
    from app.routers.products import list_products

with engine.begin() as c:
    if not c.scalar(text("SELECT count(*) FROM products WHERE name LIKE 'BENCH-IV-%'")):
        c.execute(text("""INSERT INTO products(category_id,name,description,gender,price)
            SELECT (SELECT min(id) FROM categories), 'BENCH-IV-' || lpad(n::text,4,'0'),
            repeat('Benchmark description ',100),'unisex',100+n
            FROM generate_series(1,1000) n"""))
        c.execute(text("""INSERT INTO product_variants(product_id,size,color,sku,stock)
            SELECT p.id, 'M', 'Color-'||n, 'BENCH-'||p.id||'-'||n,10
            FROM products p CROSS JOIN generate_series(1,40) n WHERE p.name LIKE 'BENCH-IV-%'"""))
        c.execute(text("""INSERT INTO product_images(product_id,storage_key,sort_order)
            SELECT p.id,'bench/'||p.id||'/'||n||'.png',n
            FROM products p CROSS JOIN generate_series(1,5) n WHERE p.name LIKE 'BENCH-IV-%'"""))

queries = []
def count(*args):
    queries.append(args[2])
event.listen(engine, 'before_cursor_execute', count)
cases = {}
for limit in (24,100):
    times, counts, hashes = [], [], set()
    for i in range(55):
        queries.clear()
        start=time.perf_counter()
        with SessionLocal() as db:
            result=list_products(gender=None,category=None,size=None,color=None,
                price_min=None,price_max=None,q='BENCH-IV-',sort='new',limit=limit,offset=0,db=db)
            payload=result.model_dump_json()
            identity_count=len(db.identity_map)
        elapsed=(time.perf_counter()-start)*1000
        if i>=5:
            times.append(elapsed); counts.append(len(queries))
            hashes.add(hashlib.sha256(payload.encode()).hexdigest())
    cases[str(limit)]={'median_ms':round(statistics.median(times),3),
        'p95_ms':round(sorted(times)[47],3),'min_ms':round(min(times),3),
        'sql_queries':sorted(set(counts)), 'payload_sha256':sorted(hashes),
        'response_bytes':len(payload.encode()),'total':result.total,'repetitions':50}
print(json.dumps({'phase':sys.argv[1], 'fixture':{'products':1000,'variants_per_product':40,
    'images_per_product':5},'method':'route + database + serialization; 5 warmups, 50 measured',
    'cases':cases},ensure_ascii=False,indent=2))
