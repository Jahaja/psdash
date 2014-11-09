import os
import sys
import platform
from psdash.log import LogReader
import socket
import tempfile
import unittest2
import time
import psutil
from psdash.node import LocalNode


class TestNode(unittest2.TestCase):
    def setUp(self):
        self.node = LocalNode()
        self.service = self.node.get_service()

    def test_get_uptime(self):
        sysinfo = self.service.get_sysinfo()
        uptime = int(time.time() - psutil.boot_time())
        self.assertEqual(sysinfo['uptime'], uptime)

    def test_get_hostname(self):
        sysinfo = self.service.get_sysinfo()
        self.assertEqual(sysinfo['hostname'], socket.gethostname())

    def test_get_os_info(self):
        sysinfo = self.service.get_sysinfo()
        self.assertEqual(sysinfo['os'], platform.platform())

    def test_get_load_avg(self):
        sysinfo = self.service.get_sysinfo()
        self.assertEqual(len(sysinfo['load_avg']), 3)
        self.assertTrue(isinstance(sysinfo['load_avg'][0], float))
        self.assertTrue(isinstance(sysinfo['load_avg'][1], float))
        self.assertTrue(isinstance(sysinfo['load_avg'][2], float))

    def test_get_cpu_count(self):
        sysinfo = self.service.get_sysinfo()
        self.assertEqual(sysinfo['num_cpus'], psutil.cpu_count())

    def test_get_memory_total(self):
        mem = self.service.get_memory()
        self.assertEqual(mem['total'], psutil.virtual_memory().total)

    def test_get_memory_free(self):
        mem = self.service.get_memory()
        self.assertIn('free', mem)

    def test_get_memory_available(self):
        mem = self.service.get_memory()
        self.assertIn('available', mem)

    def test_get_memory_used(self):
        mem = self.service.get_memory()
        self.assertIn('used', mem)

    def test_get_memory_percent(self):
        mem = self.service.get_memory()
        self.assertIn('percent', mem)
        self.assertLessEqual(mem['percent'], 100)
        self.assertGreaterEqual(mem['percent'], 0)
        self.assertIsInstance(mem['percent'], float)

    def test_get_swap_total(self):
        swap = self.service.get_swap_space()
        self.assertEqual(swap['total'], psutil.swap_memory().total)

    def test_get_swap_free(self):
        swap = self.service.get_swap_space()
        self.assertEqual(swap['free'], psutil.swap_memory().free)

    def test_get_swap_used(self):
        swap = self.service.get_swap_space()
        self.assertEqual(swap['used'], psutil.swap_memory().used)

    def test_get_swap_percent(self):
        swap = self.service.get_swap_space()
        self.assertEqual(swap['percent'], psutil.swap_memory().percent)
        self.assertLessEqual(swap['percent'], 100)
        self.assertGreaterEqual(swap['percent'], 0)
        self.assertIsInstance(swap['percent'], float)

    def test_get_swap_swapped_in(self):
        swap = self.service.get_swap_space()
        self.assertEqual(swap['swapped_in'], psutil.swap_memory().sin)

    def test_get_swap_swapped_out(self):
        swap = self.service.get_swap_space()
        self.assertEqual(swap['swapped_out'], psutil.swap_memory().sout)

    def test_get_cpu(self):
        cpu = self.service.get_cpu()
        self.assertIn('user', cpu)
        self.assertIn('system', cpu)
        self.assertIn('idle', cpu)
        self.assertIn('iowait', cpu)
        self.assertIn('irq', cpu)
        self.assertIn('nice', cpu)

    def test_get_cpu_cores(self):
        cores = self.service.get_cpu_cores()
        self.assertIsInstance(cores, list)
        self.assertIn('user', cores[0])
        self.assertIn('system', cores[0])
        self.assertIn('idle', cores[0])
        self.assertIn('iowait', cores[0])
        self.assertIn('irq', cores[0])
        self.assertIn('nice', cores[0])

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_get_disks(self):
        disks = self.service.get_disks()
        self.assertIsInstance(disks, list)
        self.assertIn('device', disks[0])
        self.assertIn('mountpoint', disks[0])
        self.assertIn('type', disks[0])
        self.assertIn('options', disks[0])
        self.assertIn('space_total', disks[0])
        self.assertIn('space_used', disks[0])
        self.assertIn('space_used_percent', disks[0])
        self.assertIn('space_free', disks[0])

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_get_disks_counters(self):
        counters = self.service.get_disks_counters()
        self.assertIsInstance(counters, dict)
        dev, c = counters.popitem()
        self.assertTrue(len(dev))
        self.assertIsInstance(dev, str)
        self.assertIn('read_count', c)
        self.assertIn('read_bytes', c)
        self.assertIn('read_time', c)
        self.assertIn('write_count', c)
        self.assertIn('write_bytes', c)
        self.assertIn('write_time', c)

    def test_get_users(self):
        users = self.service.get_users()
        self.assertIsInstance(users, list)

    def test_get_network_interfaces(self):
        self.node.net_io_counters.update()
        netifs = self.service.get_network_interfaces()
        self.assertIsInstance(netifs, dict)
        name, netif = netifs.popitem()
        self.assertGreater(len(name), 0)
        self.assertIn('name', netif)
        self.assertIn('ip', netif)
        self.assertIn('bytes_sent', netif)
        self.assertIn('bytes_recv', netif)
        self.assertIn('packets_sent', netif)
        self.assertIn('packets_recv', netif)
        self.assertIn('errors_in', netif)
        self.assertIn('errors_out', netif)
        self.assertIn('dropped_in', netif)
        self.assertIn('dropped_out', netif)
        self.assertIn('send_rate', netif)
        self.assertIn('recv_rate', netif)

    def test_get_process_list(self):
        process_list = self.service.get_process_list()
        self.assertIsInstance(process_list, list)
        proc = process_list.pop()
        self.assertIn('pid', proc)
        self.assertIn('name', proc)
        self.assertIn('cmdline', proc)
        self.assertIn('user', proc)
        self.assertIn('status', proc)
        self.assertIn('created', proc)
        self.assertIn('mem_rss', proc)
        self.assertIn('mem_vms', proc)
        self.assertIn('mem_percent', proc)
        self.assertIn('cpu_percent', proc)

    @unittest2.skipIf(os.environ.get('USER') != 'root', 'os.setuid requires privileged user')
    def test_get_process_list_anonymous_process(self):
        os.setuid(12345)
        process_list = self.service.get_process_list()
        self.assertIsInstance(process_list, list)

    def test_get_process(self):
        proc = self.service.get_process(os.getpid())
        self.assertIsInstance(proc, dict)
        self.assertIn('pid', proc)
        self.assertIn('ppid', proc)
        self.assertIn('parent_name', proc)
        self.assertIn('name', proc)
        self.assertIn('cmdline', proc)
        self.assertIn('user', proc)
        self.assertIn('uid_real', proc)
        self.assertIn('uid_effective', proc)
        self.assertIn('uid_saved', proc)
        self.assertIn('gid_real', proc)
        self.assertIn('gid_effective', proc)
        self.assertIn('gid_saved', proc)
        self.assertIn('status', proc)
        self.assertIn('created', proc)
        self.assertIn('mem_rss', proc)
        self.assertIn('mem_vms', proc)
        self.assertIn('mem_shared', proc)
        self.assertIn('mem_text', proc)
        self.assertIn('mem_lib', proc)
        self.assertIn('mem_data', proc)
        self.assertIn('mem_dirty', proc)
        self.assertIn('mem_percent', proc)
        self.assertIn('terminal', proc)
        self.assertIn('nice', proc)
        self.assertIn('io_nice_class', proc)
        self.assertIn('io_nice_value', proc)
        self.assertIn('num_threads', proc)
        self.assertIn('num_files', proc)
        self.assertIn('num_children', proc)
        self.assertIn('cwd', proc)
        self.assertIn('num_ctx_switches_invol', proc)
        self.assertIn('num_ctx_switches_vol', proc)
        self.assertIn('cpu_times_user', proc)
        self.assertIn('cpu_times_system', proc)
        self.assertIn('cpu_affinity', proc)
        self.assertIn('cpu_percent', proc)

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_get_process_limits(self):
        limits = self.service.get_process_limits(os.getpid())
        self.assertIsInstance(limits, dict)
        self.assertIn('RLIMIT_AS', limits)
        self.assertIn('RLIMIT_CORE', limits)
        self.assertIn('RLIMIT_CPU', limits)
        self.assertIn('RLIMIT_DATA', limits)
        self.assertIn('RLIMIT_FSIZE', limits)
        self.assertIn('RLIMIT_LOCKS', limits)
        self.assertIn('RLIMIT_MEMLOCK', limits)
        self.assertIn('RLIMIT_MSGQUEUE', limits)
        self.assertIn('RLIMIT_NICE', limits)
        self.assertIn('RLIMIT_NOFILE', limits)
        self.assertIn('RLIMIT_NPROC', limits)
        self.assertIn('RLIMIT_RSS', limits)
        self.assertIn('RLIMIT_RTPRIO', limits)
        self.assertIn('RLIMIT_RTTIME', limits)
        self.assertIn('RLIMIT_SIGPENDING', limits)
        self.assertIn('RLIMIT_STACK', limits)

    def test_get_process_environment(self):
        env = self.service.get_process_environment(os.getpid())
        self.assertIsInstance(env, dict)

    def test_get_process_threads(self):
        threads = self.service.get_process_threads(os.getpid())
        self.assertIsInstance(threads, list)
        self.assertIn('id', threads[0])
        self.assertIn('cpu_time_user', threads[0])
        self.assertIn('cpu_time_system', threads[0])

    def test_get_process_open_files(self):
        tempfile.mkstemp()
        files = self.service.get_process_open_files(os.getpid())
        self.assertIsInstance(files, list)
        self.assertIn('fd', files[0])
        self.assertIn('path', files[0])

    def test_get_process_connections(self):
        s = socket.socket()
        s.bind(('', 5555))
        s.listen(1)
        conns = self.service.get_process_connections(os.getpid())
        self.assertIsInstance(conns, list)
        self.assertIn('fd', conns[0])
        self.assertIn('family', conns[0])
        self.assertIn('type', conns[0])
        self.assertIn('local_addr_host', conns[0])
        self.assertIn('local_addr_port', conns[0])
        self.assertIn('remote_addr_host', conns[0])
        self.assertIn('remote_addr_port', conns[0])
        self.assertIn('state', conns[0])
        s.close()

    def test_get_process_memory_maps(self):
        memmaps = self.service.get_process_memory_maps(os.getpid())
        self.assertIsInstance(memmaps, list)
        m = memmaps[0]
        self.assertIn('path', m)
        self.assertIn('rss', m)
        self.assertIn('size', m)
        self.assertIn('pss', m)
        self.assertIn('shared_clean', m)
        self.assertIn('shared_dirty', m)
        self.assertIn('private_clean', m)
        self.assertIn('referenced', m)
        self.assertIn('anonymous', m)
        self.assertIn('swap', m)

    def test_get_process_children(self):
        children = self.service.get_process_children(os.getppid())
        self.assertIsInstance(children, list)
        c = children[0]
        self.assertIn('pid', c)
        self.assertIn('name', c)
        self.assertIn('cmdline', c)
        self.assertIn('status', c)

    def test_get_connections(self):
        conns = self.service.get_connections()
        self.assertIsInstance(conns, list)
        c = conns[0]
        self.assertIn('fd', c)
        self.assertIn('pid', c)
        self.assertIn('family', c)
        self.assertIn('type', c)
        self.assertIn('local_addr_host', c)
        self.assertIn('local_addr_port', c)
        self.assertIn('remote_addr_host', c)
        self.assertIn('remote_addr_port', c)
        self.assertIn('state', c)

    def test_get_logs(self):
        _, filename = tempfile.mkstemp()
        self.node.logs.add_patterns([filename])
        logs = self.service.get_logs()
        self.assertIsInstance(logs, list)
        log = logs[0]
        self.assertIn('path', log)
        self.assertIn('size', log)
        self.assertIn('atime', log)
        self.assertIn('mtime', log)

    def test_read_log(self):
        fd, filename = tempfile.mkstemp()
        os.write(fd, 'FOOBAR\n' * 10000)

        num_added = self.node.logs.add_patterns([filename])
        self.assertEqual(num_added, 1)

        content = self.service.read_log(filename, seek_tail=True)
        self.assertEqual(len(content), LogReader.BUFFER_SIZE)
        os.close(fd)

    def test_search_log(self):
        fd, filename = tempfile.mkstemp()
        os.write(fd, 'FOOBAR\n' * 100)
        os.write(fd, 'NEEDLE\n')
        os.write(fd, 'FOOBAR\n' * 100)
        os.fsync(fd)

        self.node.logs.add_patterns([filename])

        result = self.service.search_log(filename, 'NEEDLE')
        self.assertIsInstance(result, dict)
        self.assertIn('position', result)
        self.assertIn('buffer_pos', result)
        self.assertIn('filesize', result)
        self.assertIn('content', result)







