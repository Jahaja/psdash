import unittest2
import socket
from psdash.net import NetIOCounters


class TestNet(unittest2.TestCase):
    def setUp(self):
        self.io_counter = NetIOCounters()

    def test_first_time_return(self):
        self.assertEqual(self.io_counter.get(), None)

    def test_one_update_gives_defaulted_rates(self):
        self.io_counter.update()
        name, c = self.io_counter.get().popitem()
        self.assertEqual(c['rx_per_sec'], 0)
        self.assertEqual(c['tx_per_sec'], 0)

    def test_two_updates_gives_rates(self):
        self.io_counter.update()
        # make sure to actually use the network a bit
        socket.getaddrinfo('example.org', 80)
        self.io_counter.update()

        for c in self.io_counter.get().itervalues():
            if c['rx_per_sec'] > 0 and c['tx_per_sec'] > 0:
                break
        else:
            self.fail("Didn't find any changed network interface")
