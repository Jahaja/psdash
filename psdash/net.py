# coding=utf-8

import socket
import struct
import array
import fcntl
import psutil
import time
import sys
 

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
            res[name].update({"tx_per_sec": 0, "rx_per_sec": 0})

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
                "rx_per_sec": (io["bytes_recv"] - last_io["bytes_recv"]) / time_delta,
                "tx_per_sec": (io["bytes_sent"] - last_io["bytes_sent"]) / time_delta
            })

        self._set_last_request(counters)

        return counters


def get_interface_addresses(max_interfaces=10):
    """
    Get addresses of available network interfaces.
    See netdevice(7) and ioctl(2) for details.

    Returns a list of dicts
    """

    SIOCGIFCONF = 0x8912

    if sys.maxsize > (1 << 31):
        ifreq = struct.Struct("16sH2xI16x")
    else:
        ifreq = struct.Struct("16sHI8x")

    # create request param struct
    ifconf = struct.Struct("iL")
    bufsize = ifreq.size * max_interfaces
    buf = array.array("B", "\0" * bufsize)
    ifconf_val = ifconf.pack(bufsize, buf.buffer_info()[0])

    # make ioctl request
    sock = socket.socket()
    ifconf_res = fcntl.ioctl(sock.fileno(), SIOCGIFCONF, ifconf_val)
    sock.close()

    buflen, _ = ifconf.unpack(ifconf_res)
    resbuf = buf.tostring()

    addresses = []
    for x in xrange(buflen / ifreq.size):
        # read the size of the struct from the result buffer
        # and unpack it.
        start = x * ifreq.size
        stop = start + ifreq.size
        name, family, address = ifreq.unpack(resbuf[start:stop])

        # transform the address to it's string representation
        ip = socket.inet_ntoa(struct.pack("I", address))
        name = name.rstrip("\0")

        addr = {
            "name": name,
            "family": family,
            "ip": ip
        }

        addresses.append(addr)

    return addresses
