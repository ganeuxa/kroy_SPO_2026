"""Run with QA_NGINX=1 against the isolated production-like Compose stack."""
import json
import os
from urllib.request import urlopen
from urllib.error import HTTPError

import pytest

pytestmark = pytest.mark.skipif(os.getenv('QA_NGINX') != '1', reason='Enable QA_NGINX=1 for Nginx checks')
URL = 'http://127.0.0.1:18080'


@pytest.mark.parametrize('path', ['/', '/cart', '/login', '/register', '/products/1'])
def test_spa_direct_routes(api, path):
    with urlopen(URL + path, timeout=10) as response:
        assert response.status == 200
        assert 'text/html' in response.headers['Content-Type']
        assert '<div id="root">' in response.read().decode()


def test_nginx_health(api):
    with urlopen(URL + '/healthz', timeout=10) as response:
        assert response.status == 200 and response.read().strip() == b'ok'


def test_security_headers(api):
    with urlopen(URL, timeout=10) as response:
        assert response.headers['X-Frame-Options'] == 'DENY'
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert response.headers['Server'] == 'nginx'


def test_missing_asset_is_404(api):
    with pytest.raises(HTTPError) as error:
        urlopen(URL + '/assets/qa-missing.js', timeout=10)
    assert error.value.code == 404


@pytest.mark.parametrize('service', ['backend', 'nginx'])
def test_service_not_root(api, compose, service):
    assert compose('exec', '-T', service, 'id', '-u').strip() != '0'


def test_only_nginx_publishes_port(api, compose):
    output = compose('ps', '--format', 'json')
    # Compose versions emit either an array or newline-delimited JSON objects.
    rows = json.loads(output) if output.lstrip().startswith('[') else [json.loads(line) for line in output.splitlines() if line]
    assert {row['Service'] for row in rows} == {'db', 'backend', 'nginx'}
    for row in rows:
        published = [p for p in row.get('Publishers') or [] if p.get('PublishedPort')]
        if row['Service'] == 'nginx':
            assert len(published) == 1
            assert published[0]['URL'] == '127.0.0.1'
            assert published[0]['PublishedPort'] == 18080
        else:
            assert not published


@pytest.mark.ops
def test_backend_down_returns_json_and_static_stays_available(api, compose):
    from test_operations import wait_healthy
    try:
        compose('stop', 'backend')
        response = api.expect('/api/products', 503)
        assert response['detail'] == 'Сервер временно недоступен, попробуйте позже'
        with urlopen(URL, timeout=10) as page:
            assert page.status == 200
    finally:
        compose('start', 'backend')
        wait_healthy(api)
