import os
import tempfile
import unittest2
import time
from psdash.log import Logs, LogReader, LogError, LogSearcher


class TestLogs(unittest2.TestCase):
    NEEDLE = 'foobar\n'
    POSITIONS = [10000, 8000, 6000, 4000, 2000, 500]

    def setUp(self):
        fd, filename = tempfile.mkstemp()
        self.filename = filename
        self.fp = os.fdopen(fd, 'w+')
        for pos in self.POSITIONS:
            self.fp.seek(pos)
            self.fp.write(self.NEEDLE)
        self.fp.close()
        self.logs = Logs()
        self.logs.add_available(filename)

    def tearDown(self):
        os.remove(self.filename)
        self.logs.clear_available()

    def test_searching(self):
        log = self.logs.get(self.filename)
        positions = [log.search(self.NEEDLE)[0] for _ in xrange(len(self.POSITIONS))]
        self.assertEqual(self.POSITIONS, positions)

    def test_searching_other_buffer_size(self):
        log = LogReader(self.filename, LogReader.BUFFER_SIZE / 2)
        positions = [log.search(self.NEEDLE)[0] for _ in xrange(len(self.POSITIONS))]
        self.assertEqual(self.POSITIONS, positions)

    def test_searching_no_result(self):
        log = self.logs.get(self.filename)
        pos = log.search('wontexist')[0]
        self.assertEqual(pos, -1)

    def test_read_tail(self):
        log = self.logs.get(self.filename)
        log.set_tail_position()
        buf = log.read()
        self.assertEqual(len(buf), LogReader.BUFFER_SIZE)

    def test_add_non_existing(self):
        self.assertRaises(LogError, self.logs.add_available, '/var/log/w0ntre4lly3xist.log')

    def test_repr_works(self):
        log = self.logs.get(self.filename)
        s = LogSearcher(log)
        self.assertIn('<LogReader', repr(log))
        self.assertIn('<LogSearcher', repr(s))

    def test_add_pattern(self):
        ts = time.time()
        suffix = '%d.log' % ts
        tempfile.mkstemp(suffix=suffix)
        tempfile.mkstemp(suffix=suffix)
        num_added = self.logs.add_patterns(['/tmp/*%s' % suffix])
        self.assertEqual(num_added, 2)

    @unittest2.skipIf(os.environ.get('USER') == 'root', "We'll have access to this if we're root")
    def test_add_pattern_no_access(self):
        num_added = self.logs.add_patterns(['/proc/vmallocinfo'])
        self.assertEqual(num_added, 0)


if __name__ == '__main__':
    unittest2.main()