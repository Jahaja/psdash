import socket
import unittest2
import tempfile
from psdash.run import PsDashRunner

class TestRunner(unittest2.TestCase):
    def test_args_log(self):
        _, filename = tempfile.mkstemp()
        r = PsDashRunner.create_from_args(['-l', filename])
        self.assertEqual(r.app.config['PSDASH_LOGS'][0], filename)

    def test_args_bind(self):
        r = PsDashRunner.create_from_args(['-b', '10.0.0.1'])
        self.assertEqual(r.app.config['PSDASH_BIND_HOST'], '10.0.0.1')

    def test_args_port(self):
        r = PsDashRunner.create_from_args(['-p', '5555'])
        self.assertEqual(r.app.config['PSDASH_PORT'], 5555)

    def test_args_debug(self):
        r = PsDashRunner.create_from_args(['-d'])
        self.assertTrue(r.app.debug)

    def test_reload_logs(self):
        _, filename = tempfile.mkstemp()
        r = PsDashRunner.create_from_args(['-l', filename])
        pre_count = len(r.app.psdash.logs.available)
        c = r.reload_logs()
        post_count = len(r.app.psdash.logs.available)
        self.assertEqual(pre_count, post_count)

    def test_update_net_io_counters(self):
        r = PsDashRunner()
        socket.getaddrinfo('example.org', 80)
        counters = r.update_net_io_counters()

        for c in counters.itervalues():
            if c['rx_per_sec'] > 0 and c['tx_per_sec'] > 0:
                break
        else:
            self.fail("Didn't find any changed network interface")
