# coding=utf-8

import psutil
import time
import netifaces


class NetIOCounters(object):
    def __init__(self, pernic=True):
        self.last_req = None
        self.last_req_time = None
        self.pernic = pernic

    def _get_net_io_counters(self):
        """
        Fetch io counters from psutil and transform it to
        dicts with the additional attributes defaulted
        """
        counters = psutil.net_io_counters(pernic=self.pernic)

        res = {}
        for name, io in counters.iteritems():
            res[name] = io._asdict()
            res[name].update({'tx_per_sec': 0, 'rx_per_sec': 0})

        return res

    def _set_last_request(self, counters):
        self.last_req = counters
        self.last_req_time = time.time()

    def get(self):
        return self.last_req

    def update(self):
        counters = self._get_net_io_counters()

        if not self.last_req:
            self._set_last_request(counters)
            return counters

        time_delta = time.time() - self.last_req_time
        if not time_delta:
            return counters

        for name, io in counters.iteritems():
            last_io = self.last_req.get(name)
            if not last_io:
                continue

            counters[name].update({
                'rx_per_sec': (io['bytes_recv'] - last_io['bytes_recv']) / time_delta,
                'tx_per_sec': (io['bytes_sent'] - last_io['bytes_sent']) / time_delta
            })

        self._set_last_request(counters)

        return counters


def get_interface_addresses():
    """
    Get addresses of available network interfaces.
    See netifaces on pypi for details.

    Returns a list of dicts
    """

    addresses = []
    ifaces = netifaces.interfaces()
    for iface in ifaces:
        addrs = netifaces.ifaddresses(iface)
        families = addrs.keys()

        # put IPv4 to the end so it lists as the main iface address
        if netifaces.AF_INET in families:
            families.remove(netifaces.AF_INET)
            families.append(netifaces.AF_INET)

        for family in families:
            for addr in addrs[family]:
                address = {
                    'name': iface,
                    'family': family,
                    'ip': addr['addr'],
                }
                addresses.append(address)

    return addresses
