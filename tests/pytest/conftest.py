"""Fixtures for the isolated kroy-varvara-qa Docker Compose instance."""
import json
import os
import subprocess
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import pytest

ROOT = Path(__file__).resolve().parents[2]
NGINX = os.getenv('QA_NGINX') == '1'
BASE_URL = 'http://127.0.0.1:18080' if NGINX else 'http://127.0.0.1:18000'
COMPOSE = ['docker', 'compose', '-f', 'docker-compose.test.yml' if NGINX else 'docker-compose.yml', '--env-file', '.env.qa', '-p', 'kroy-varvara-nginx-qa' if NGINX else 'kroy-varvara-qa']


def pytest_addoption(parser):
    parser.addoption('--run-ops', action='store_true', help='Include QA service restarts')


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--run-ops'):
        for item in items:
            if 'ops' in item.keywords:
                item.add_marker(pytest.mark.skip(reason='Enable with --run-ops (restarts QA services)'))


class Client:
    def request(self, path, data=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = Request(BASE_URL + path,
                          data=json.dumps(data).encode() if data is not None else None,
                          headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def expect(self, path, status=200, data=None, token=None):
        actual, body = self.request(path, data, token)
        # Do not include authentication response bodies (tokens) in assertion output.
        assert actual == status, f'{path}: HTTP {actual}, expected {status}'
        return body


@pytest.fixture(scope='session')
def api():
    client = Client()
    try:
        status, _ = client.request('/api/health')
    except (URLError, OSError) as error:
        pytest.fail(f'QA server unavailable. Start Docker Compose: {error}', pytrace=False)
    if status != 200:
        pytest.fail(f'QA health is HTTP {status}; check database setup before tests', pytrace=False)
    return client


@pytest.fixture
def user_data():
    return {'email': 'qa-pytest-' + uuid.uuid4().hex + '@example.com',
            'password': 'Qa-Strong-2026', 'full_name': 'Варя QA'}


@pytest.fixture
def account(api, user_data):
    response = api.expect('/api/auth/register', 201, user_data)
    return {**user_data, 'token': response['access_token'], 'id': response['user']['id']}


@pytest.fixture(scope='session')
def compose():
    def run(*args, input=None):
        result = subprocess.run(COMPOSE + list(args), cwd=ROOT, input=input,
                                text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, f'Compose command failed: {args}; {result.stderr}'
        return result.stdout
    return run


@pytest.fixture
def backend_python(compose):
    return lambda script: compose('exec', '-T', 'backend', 'python', input=script)


@pytest.fixture
def set_db_value(backend_python):
    """Temporarily modify a fixture row; restore even after failed assertions."""
    originals = []
    allowed = {('users', 'is_active'), ('products', 'is_active'), ('product_variants', 'stock')}
    def change(table, column, row_id, value):
        assert (table, column) in allowed
        assert isinstance(row_id, int)
        script = f'''from app.db import engine
from sqlalchemy import text
import json
with engine.begin() as c:
 old=c.execute(text("SELECT {column} FROM {table} WHERE id=:id"), {{"id":{row_id}}}).scalar_one()
 c.execute(text("UPDATE {table} SET {column}=:value WHERE id=:id"), {{"id":{row_id},"value":{value!r}}})
print(json.dumps(old))
'''
        old = json.loads(backend_python(script))
        originals.append((table, column, row_id, old))
    yield change
    for table, column, row_id, old in reversed(originals):
        backend_python(f'''from app.db import engine
from sqlalchemy import text
with engine.begin() as c:
 c.execute(text("UPDATE {table} SET {column}=:value WHERE id=:id"), {{"id":{row_id},"value":{old!r}}})
''')
