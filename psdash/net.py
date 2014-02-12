import socket
import struct
import array
import fcntl
import psutil
import time
import sys
 
SIOCGIFCONF = 0x8912

if sys.maxsize > (1 << 31):
    ifreq = struct.Struct("16sH2xI16x")
else:
    # TODO fix format for 32 bit
    ifreq = struct.Struct("16sH2xI16x")

ifconf = struct.Struct("iL")
 
class NetIOCounters(object):
    _last_req = None
    _last_req_time = None

    @classmethod
    def request(cls):
        io_counters = psutil.network_io_counters(pernic=True)

        res = {}
        for name, io in io_counters.iteritems():
            res[name] = io._asdict()
            res[name].update({"tx_per_sec": 0, "rx_per_sec": 0})

        if not cls._last_req:
            # no request to compare with so let's just return.
            cls._last_req = io_counters
            cls._last_req_time = time.time()
            return res

        elapsed = int(time.time() - cls._last_req_time)
        elapsed = max(elapsed, 1)

        for name, io in io_counters.iteritems():
            last_io = cls._last_req.get(name)
            if not last_io:
                continue

            res[name].update({
                "rx_per_sec": (io.bytes_recv - last_io.bytes_recv) / elapsed,
                "tx_per_sec": (io.bytes_sent - last_io.bytes_sent) / elapsed
            })

        cls._last_req = io_counters
        cls._last_req_time = time.time()

        return res


def get_network_interfaces(max_net_inf=10):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bufsize = ifreq.size * max_net_inf
    buf = array.array("B", "\0" * bufsize)
    ifconf_val = ifconf.pack(bufsize, buf.buffer_info()[0])
    ifconf_res = fcntl.ioctl(sock.fileno(), SIOCGIFCONF, ifconf_val)
 
    buflen, _ = ifconf.unpack(ifconf_res)
    resbuf = buf.tostring()

    io_counters = NetIOCounters.request()
 
    interfaces = []
    for x in xrange(buflen / ifreq.size):
        start = x * ifreq.size
        stop = start + ifreq.size
 
        name, family, address = ifreq.unpack(resbuf[start:stop])
        ip = socket.inet_ntoa(struct.pack("I", address))
        name = name.rstrip("\0")

        inf = {
            "name": name,
            "family": family,
            "ip": ip
        }
        inf.update(io_counters.get(name, {}))

        interfaces.append(inf)
 
    return interfaces


