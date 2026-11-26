import time
import os
import pytest
from html.parser import HTMLParser
from urllib.request import urlopen
from urllib.parse import urljoin

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
        # Production image has no Node: verify the deployed build, including
        # referenced JS/CSS. A missing asset served as SPA HTML must fail.
        class Assets(HTMLParser):
            def __init__(self):
                super().__init__()
                self.assets = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'script' and attrs.get('src'):
                    self.assets.append((attrs['src'], 'js'))
                if tag == 'link' and attrs.get('rel') == 'stylesheet':
                    self.assets.append((attrs['href'], 'css'))
        base = 'http://127.0.0.1:18080/'
        with urlopen(base, timeout=10) as response:
            html = response.read().decode()
            assert response.status == 200
            assert 'text/html' in response.headers.get('Content-Type', '')
        assert '<div id="root">' in html
        parser = Assets()
        parser.feed(html)
        assert any(kind == 'js' for _, kind in parser.assets)
        assert any(kind == 'css' for _, kind in parser.assets)
        for path, kind in parser.assets:
            assert path.startswith('/assets/'), f'Unexpected build asset: {path}'
            with urlopen(urljoin(base, path), timeout=10) as response:
                assert response.status == 200
                content_type = response.headers.get('Content-Type', '')
                assert ('javascript' in content_type if kind == 'js' else 'text/css' in content_type)
                assert response.read().strip(), f'Empty build asset: {path}'
        return
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
