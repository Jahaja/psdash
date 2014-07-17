import unittest
import base64
import sys
from psdash.run import create_app

try:
    import httplib
except ImportError:
    # support for python 3
    import http.client as httplib

class TestBasicAuth(unittest.TestCase):
    default_username = 'tester'
    default_password = 'secret'

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def _enable_basic_auth(self, username, password):
        self.app.config['PSDASH_AUTH_USERNAME'] = username
        self.app.config['PSDASH_AUTH_PASSWORD'] = password

    def _create_auth_headers(self, username, password):
        data = base64.b64encode(':'.join([username, password]))
        headers = [('Authorization', 'Basic %s' % data)]
        return headers

    def test_missing_credentials(self):
        self._enable_basic_auth(self.default_username, self.default_password)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)

    def test_correct_credentials(self):
        self._enable_basic_auth(self.default_username, self.default_password)
        
        headers = self._create_auth_headers(self.default_username, self.default_password)
        resp = self.client.get('/', headers=headers)
        
        self.assertEqual(resp.status_code, httplib.OK)

    def test_incorrect_credentials(self):
        self._enable_basic_auth(self.default_username, self.default_password)

        headers = self._create_auth_headers(self.default_username, 'wrongpass')
        resp = self.client.get('/', headers=headers)

        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)


class TestAllowedRemoteAddresses(unittest.TestCase):
    def test_correct_remote_address(self):
        app = create_app({'PSDASH_ALLOWED_REMOTE_ADDRESSES': '127.0.0.1'})
        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

    def test_incorrect_remote_address(self):
        app = create_app({'PSDASH_ALLOWED_REMOTE_ADDRESSES': '127.0.0.1'})
        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.0.0.1'})
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)

    def test_multiple_remote_addresses(self):
        app = create_app({'PSDASH_ALLOWED_REMOTE_ADDRESSES': '127.0.0.1, 10.0.0.1'})

        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.124.0.1'})
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)

    def test_multiple_remote_addresses_using_list(self):
        app = create_app({'PSDASH_ALLOWED_REMOTE_ADDRESSES': ['127.0.0.1', '10.0.0.1']})

        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.124.0.1'})
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)


if __name__ == '__main__':
    unittest.main()