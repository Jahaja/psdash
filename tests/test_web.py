import gevent
import json
import unittest2
import base64
import os
import tempfile
import urllib2
from psdash.run import PsDashRunner

try:
    import httplib
except ImportError:
    # support for python 3
    import http.client as httplib

class TestBasicAuth(unittest2.TestCase):
    default_username = 'tester'
    default_password = 'secret'

    def setUp(self):
        self.app = PsDashRunner().app
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


class TestAllowedRemoteAddresses(unittest2.TestCase):
    def test_correct_remote_address(self):
        r = PsDashRunner({'PSDASH_ALLOWED_REMOTE_ADDRESSES': '127.0.0.1'})
        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

    def test_incorrect_remote_address(self):
        r = PsDashRunner({'PSDASH_ALLOWED_REMOTE_ADDRESSES': '127.0.0.1'})
        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.0.0.1'})
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)

    def test_multiple_remote_addresses(self):
        r = PsDashRunner({'PSDASH_ALLOWED_REMOTE_ADDRESSES': '127.0.0.1, 10.0.0.1'})

        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.124.0.1'})
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)

    def test_multiple_remote_addresses_using_list(self):
        r = PsDashRunner({'PSDASH_ALLOWED_REMOTE_ADDRESSES': ['127.0.0.1', '10.0.0.1']})

        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(resp.status_code, httplib.OK)

        resp = r.app.test_client().get('/', environ_overrides={'REMOTE_ADDR': '10.124.0.1'})
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)


class TestEnvironmentWhitelist(unittest2.TestCase):
    def test_show_only_whitelisted(self):
        r = PsDashRunner({'PSDASH_ENVIRON_WHITELIST': ['USER']})
        resp = r.app.test_client().get('/process/%d/environment' % os.getpid())
        self.assertTrue(os.environ['USER'] in resp.data)
        self.assertTrue('*hidden by whitelist*' in resp.data)


class TestUrlPrefix(unittest2.TestCase):
    def setUp(self):
        self.default_prefix = '/subfolder/'

    def test_page_not_found_on_root(self):
        r = PsDashRunner({'PSDASH_URL_PREFIX': self.default_prefix})
        resp = r.app.test_client().get('/')
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)

    def test_works_on_prefix(self):
        r = PsDashRunner({'PSDASH_URL_PREFIX': self.default_prefix})
        resp = r.app.test_client().get(self.default_prefix)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_multiple_level_prefix(self):
        r = PsDashRunner({'PSDASH_URL_PREFIX': '/use/this/folder/'})
        resp = r.app.test_client().get('/use/this/folder/')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_missing_starting_slash_works(self):
        r = PsDashRunner({'PSDASH_URL_PREFIX': 'subfolder/'})
        resp = r.app.test_client().get('/subfolder/')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_missing_trailing_slash_works(self):
        r = PsDashRunner({'PSDASH_URL_PREFIX': '/subfolder'})
        resp = r.app.test_client().get('/subfolder/')
        self.assertEqual(resp.status_code, httplib.OK)


class TestHttps(unittest2.TestCase):
    def _run(self, https=False):
        options = {'PSDASH_PORT': 5051}
        if https:
            options.update({
                'PSDASH_HTTPS_KEYFILE': os.path.join(os.path.dirname(__file__), 'keyfile'),
                'PSDASH_HTTPS_CERTFILE': os.path.join(os.path.dirname(__file__), 'cacert.pem')
            })
        self.r = PsDashRunner(options)
        self.runner = gevent.spawn(self.r.run)
        gevent.sleep(0.3)

    def tearDown(self):
        self.r.server.close()
        self.runner.kill()
        gevent.sleep(0.3)

    def test_https_dont_work_without_certs(self):
        self._run()
        self.assertRaises(urllib2.URLError, urllib2.urlopen, 'https://127.0.0.1:5051')

    def test_https_works_with_certs(self):
        self._run(https=True)
        resp = urllib2.urlopen('https://127.0.0.1:5051')
        self.assertEqual(resp.getcode(), httplib.OK)


class TestEndpoints(unittest2.TestCase):
    def setUp(self):
        self.r = PsDashRunner()
        self.app = self.r.app
        self.client = self.app.test_client()
        self.pid = os.getpid()
        self.r.get_local_node().net_io_counters.update()

    def test_index(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, httplib.OK)

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_disks(self):
        resp = self.client.get('/disks')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_network(self):
        resp = self.client.get('/network')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_processes(self):
        resp = self.client.get('/processes')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_process_overview(self):
        resp = self.client.get('/process/%d' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    @unittest2.skipIf(os.environ.get('USER') == 'root', 'It would fail as root as we would have access to pid 1')
    def test_process_no_access(self):
        resp = self.client.get('/process/1')  # pid 1 == init
        self.assertEqual(resp.status_code, httplib.UNAUTHORIZED)

    def test_process_non_existing_pid(self):
        resp = self.client.get('/process/0')
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)

    def test_process_children(self):
        resp = self.client.get('/process/%d/children' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_process_connections(self):
        resp = self.client.get('/process/%d/connections' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_process_environment(self):
        resp = self.client.get('/process/%d/environment' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_process_files(self):
        resp = self.client.get('/process/%d/files' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_process_threads(self):
        resp = self.client.get('/process/%d/threads' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_process_memory(self):
        resp = self.client.get('/process/%d/memory' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_process_limits(self):
        resp = self.client.get('/process/%d/limits' % self.pid)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_process_invalid_section(self):
        resp = self.client.get('/process/%d/whatnot' % self.pid)
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)

    def test_non_existing(self):
        resp = self.client.get('/prettywronghuh')
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)

    def test_connection_filters(self):
        resp = self.client.get('/network?laddr=127.0.0.1')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_register_node(self):
        resp = self.client.get('/register?name=examplehost&port=500')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_register_node_all_params_required(self):
        resp = self.client.get('/register?name=examplehost')
        self.assertEqual(resp.status_code, httplib.BAD_REQUEST)

        resp = self.client.get('/register?port=500')
        self.assertEqual(resp.status_code, httplib.BAD_REQUEST)


class TestLogs(unittest2.TestCase):
    def _create_log_file(self):
        fd, filename = tempfile.mkstemp()
        fp = os.fdopen(fd, 'w')
        fp.write('woha\n' * 100)
        fp.write('something\n')
        fp.write('woha\n' * 100)
        fp.flush()
        return filename

    def setUp(self):
        self.r = PsDashRunner()
        self.app = self.r.app
        self.client = self.app.test_client()
        self.filename = self._create_log_file()
        self.r.get_local_node().logs.add_available(self.filename)

    def test_logs(self):
        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_logs_removed_file(self):
        filename = self._create_log_file()
        self.r.get_local_node().logs.add_available(filename)

        # first visit to make sure the logs are properly initialized
        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, httplib.OK)

        os.unlink(filename)

        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_logs_removed_file_uninitialized(self):
        filename = self._create_log_file()
        self.r.get_local_node().logs.add_available(filename)

        os.unlink(filename)

        resp = self.client.get('/logs')
        self.assertEqual(resp.status_code, httplib.OK)

    def test_view(self):
        resp = self.client.get('/log?filename=%s' % self.filename)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_search(self):
        resp = self.client.get('/log/search?filename=%s&text=%s' % (self.filename, 'something'),
                               environ_overrides={'HTTP_X_REQUESTED_WITH': 'xmlhttprequest'})

        self.assertEqual(resp.status_code, httplib.OK)
        try:
            data = json.loads(resp.data)
            self.assertIn('something', data['content'])
        except ValueError:
            self.fail('Log search did not return valid json data')

    def test_read(self):
        resp = self.client.get('/log?filename=%s' % self.filename,
                               environ_overrides={'HTTP_X_REQUESTED_WITH': 'xmlhttprequest'})
        self.assertEqual(resp.status_code, httplib.OK)

    def test_read_tail(self):
        resp = self.client.get('/log?filename=%s&seek_tail=1' % self.filename)
        self.assertEqual(resp.status_code, httplib.OK)

    def test_non_existing_file(self):
        filename = "/var/log/surelynotaroundright.log"

        resp = self.client.get('/log?filename=%s' % filename)
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)

        resp = self.client.get('/log/search?filename=%s&text=%s' % (filename, 'something'))
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)

        resp = self.client.get('/log/read?filename=%s' % filename)
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)

        resp = self.client.get('/log/read_tail?filename=%s' % filename)
        self.assertEqual(resp.status_code, httplib.NOT_FOUND)


if __name__ == '__main__':
    unittest2.main()
