import pytest


@pytest.mark.parametrize('path', ['/api/cart', '/api/auth/me'])
@pytest.mark.parametrize('token', [None, 'invalid.jwt.token'], ids=['guest', 'invalid-jwt'])
def test_protected_routes(api, path, token):
    api.expect(path, 401, token=token)


def test_guest_cannot_add_to_cart(api):
    api.expect('/api/cart', 401, {'variant_id': 1})


@pytest.mark.parametrize('field,value', [('email', 'invalid'), ('password', 'short'),
    ('password', 'я'*40), ('full_name', '   '), ('phone', 'abc')],
    ids=['email', 'short-password', 'long-utf8-password', 'blank-name', 'phone'])
def test_registration_validation(api, user_data, field, value):
    api.expect('/api/auth/register', 422, {**user_data, field: value})


def test_registration(api, user_data):
    response = api.expect('/api/auth/register', 201, user_data)
    assert response['access_token']
    assert response['user']['role'] == 'customer'
    assert 'password_hash' not in response['user']


@pytest.mark.parametrize('uppercase', [False, True])
def test_duplicate_email(api, account, uppercase):
    data = {key: account[key] for key in ('email', 'password', 'full_name')}
    if uppercase:
        data['email'] = data['email'].upper()
    api.expect('/api/auth/register', 409, data)


def test_wrong_password(api, account):
    api.expect('/api/auth/login', 401, {'email': account['email'], 'password': 'wrong'})


def test_unknown_email(api, user_data):
    api.expect('/api/auth/login', 401, {'email': user_data['email'], 'password': user_data['password']})


def test_login_case_insensitive_email(api, account):
    response = api.expect('/api/auth/login', data={'email': account['email'].upper(), 'password': account['password']})
    assert response['access_token']
    assert response['user']['id'] == account['id']


def test_current_user(api, account):
    assert api.expect('/api/auth/me', token=account['token'])['email'] == account['email']


def test_password_suffix_after_72_utf8_bytes_is_rejected(api, user_data):
    """DEF-02: deliberately fails until login validates bcrypt's byte limit."""
    api.expect('/api/auth/register', 201, {**user_data, 'password': 'я'*36})
    status, _ = api.request('/api/auth/login', {'email': user_data['email'], 'password': 'я'*36+'x'})
    assert status in (401, 422), f'DEF-02: changed password accepted (HTTP {status})'
