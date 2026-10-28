import time
import os
import pytest

pytestmark = pytest.mark.ops


def wait_healthy(api):
    for _ in range(30):
        try:
            if api.request('/api/health')[0] == 200:
                return
        except OSError:
            pass
        time.sleep(1)
    pytest.fail('Health did not recover within 30 attempts')


def test_production_build(api, compose):
    if os.getenv('QA_NGINX') == '1':
        pytest.skip('Production frontend already built in Nginx image; no Node runtime there')
    output = compose('exec', '-T', 'frontend', 'npm', 'run', 'build')
    assert 'built in' in output


def test_database_outage_and_recovery(api, compose, account):
    before = api.expect('/api/cart', data={'variant_id': 1}, token=account['token'])
    try:
        compose('stop', 'db')
        api.expect('/api/health', 503)
        api.expect('/api/products', 503)
    finally:
        compose('start', 'db')
        wait_healthy(api)
    assert api.expect('/api/cart', token=account['token']) == before


def test_backend_restart_preserves_cart(api, compose, account):
    before = api.expect('/api/cart', data={'variant_id': 1}, token=account['token'])
    compose('restart', 'backend')
    wait_healthy(api)
    assert api.expect('/api/cart', token=account['token']) == before
