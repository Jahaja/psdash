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
        asserts = ['user', 'system', 'idle', 'iowait', 'irq', 'nice']
        for a in asserts:
            self.assertIn(a, cpu)

    def test_get_cpu_cores(self):
        cores = self.service.get_cpu_cores()
        self.assertIsInstance(cores, list)
        asserts = ['user', 'system', 'idle', 'iowait', 'irq', 'nice']
        for a in asserts:
            self.assertIn(a, cores[0])

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_get_disks(self):
        disks = self.service.get_disks()
        self.assertIsInstance(disks, list)
        asserts = ['device', 'mountpoint', 'type', 'options', 'space_total',
                 'space_used', 'space_used_percent', 'space_free']
        for a in asserts:
            self.assertIn(a, disks[0])

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_get_disks_counters(self):
        counters = self.service.get_disks_counters()
        self.assertIsInstance(counters, dict)
        dev, c = counters.popitem()
        self.assertTrue(len(dev))
        self.assertIsInstance(dev, str)
        asserts = ['read_count', 'read_bytes', 'read_time',
                 'write_count', 'write_bytes', 'write_time']
        for a in asserts:
            self.assertIn(a, c)

    def test_get_users(self):
        users = self.service.get_users()
        self.assertIsInstance(users, list)

    def test_get_network_interfaces(self):
        self.node.net_io_counters.update()
        netifs = self.service.get_network_interfaces()
        self.assertIsInstance(netifs, dict)
        name, netif = netifs.popitem()
        self.assertGreater(len(name), 0)
        asserts = ['ip', 'bytes_sent', 'bytes_recv', 'packets_sent',
                 'packets_recv', 'errors_in', 'errors_out', 'dropped_in',
                 'dropped_out', 'send_rate', 'recv_rate']
        for a in asserts:
            self.assertIn(a, netif)

    def test_get_process_list(self):
        process_list = self.service.get_process_list()
        self.assertIsInstance(process_list, list)
        proc = process_list.pop()
        asserts = ['pid', 'name', 'cmdline', 'user', 'status', 'created',
                 'mem_rss', 'mem_vms', 'mem_percent', 'cpu_percent']
        for a in asserts:
            self.assertIn(a, proc)

    @unittest2.skipIf(os.environ.get('USER') != 'root', 'os.setuid requires privileged user')
    def test_get_process_list_anonymous_process(self):
        os.setuid(12345)
        process_list = self.service.get_process_list()
        self.assertIsInstance(process_list, list)

    def test_get_process(self):
        proc = self.service.get_process(os.getpid())
        self.assertIsInstance(proc, dict)
        asserts = ['pid', 'ppid', 'parent_name', 'name', 'cmdline',
                 'user', 'uid_real', 'uid_effective', 'uid_saved',
                 'gid_real', 'gid_effective', 'gid_saved', 'status',
                 'created', 'mem_rss', 'mem_shared', 'mem_text',
                 'mem_lib', 'mem_data', 'mem_dirty', 'mem_percent',
                 'terminal', 'nice', 'io_nice_class', 'io_nice_value',
                 'num_threads', 'num_files', 'num_children', 'cwd',
                 'num_ctx_switches_invol', 'num_ctx_switches_vol',
                 'cpu_times_user', 'cpu_times_system', 'cpu_affinity',
                 'cpu_percent']
        for a in asserts:
            self.assertIn(a, proc)

    @unittest2.skipIf('TRAVIS' in os.environ, 'Functionality not supported on Travis CI')
    def test_get_process_limits(self):
        limits = self.service.get_process_limits(os.getpid())
        self.assertIsInstance(limits, dict)
        asserts = ['RLIMIT_AS', 'RLIMIT_CORE', 'RLIMIT_CPU', 'RLIMIT_DATA',
                 'RLIMIT_FSIZE', 'RLIMIT_LOCKS', 'RLIMIT_MEMLOCK',
                 'RLIMIT_MSGQUEUE', 'RLIMIT_NICE', 'RLIMIT_NOFILE',
                 'RLIMIT_NPROC', 'RLIMIT_RSS', 'RLIMIT_RTPRIO',
                 'RLIMIT_RTTIME', 'RLIMIT_SIGPENDING', 'RLIMIT_STACK']
        for a in asserts:
            self.assertIn(a, limits)

    def test_get_process_environment(self):
        env = self.service.get_process_environment(os.getpid())
        self.assertIsInstance(env, dict)

    def test_get_process_threads(self):
        threads = self.service.get_process_threads(os.getpid())
        self.assertIsInstance(threads, list)
        asserts = ['id', 'cpu_time_user', 'cpu_time_system']
        for a in asserts:
            self.assertIn(a, threads[0])

    def test_get_process_open_files(self):
        tempfile.mkstemp()
        files = self.service.get_process_open_files(os.getpid())
        self.assertIsInstance(files, list)
        asserts = ['fd', 'path']
        for a in asserts:
            self.assertIn(a, files[0])

    def test_get_process_connections(self):
        s = socket.socket()
        s.bind(('', 5555))
        s.listen(1)
        conns = self.service.get_process_connections(os.getpid())
        self.assertIsInstance(conns, list)
        asserts = ['fd', 'family', 'type', 'local_addr_host', 'local_addr_port',
                 'remote_addr_host', 'remote_addr_port', 'state']
        for a in asserts:
            self.assertIn(a, conns[0])
        s.close()

    def test_get_process_memory_maps(self):
        memmaps = self.service.get_process_memory_maps(os.getpid())
        self.assertIsInstance(memmaps, list)
        m = memmaps[0]
        asserts = ['path', 'rss', 'size', 'pss', 'shared_clean', 'shared_dirty',
                 'private_clean', 'referenced', 'anonymous', 'swap']
        for a in asserts:
            self.assertIn(a, m)

    def test_get_process_children(self):
        children = self.service.get_process_children(os.getppid())
        self.assertIsInstance(children, list)
        c = children[0]
        asserts = ['pid', 'name', 'cmdline', 'status']
        for a in asserts:
            self.assertIn(a, c)

    def test_get_connections(self):
        conns = self.service.get_connections()
        self.assertIsInstance(conns, list)
        c = conns[0]
        asserts = ['fd', 'pid', 'family', 'type', 'local_addr_host', 'local_addr_port',
                 'remote_addr_host', 'remote_addr_port', 'state']
        for a in asserts:
            self.assertIn(a, c)

    def test_get_logs(self):
        _, filename = tempfile.mkstemp()
        self.node.logs.add_patterns([filename])
        logs = self.service.get_logs()
        self.assertIsInstance(logs, list)
        log = logs[0]
        asserts = ['path', 'size', 'atime', 'mtime']
        for a in asserts:
            self.assertIn(a, log)

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
        asserts = ['position', 'buffer_pos', 'filesize', 'content']
        for a in asserts:
            self.assertIn(a, result)







