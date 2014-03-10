import os
import tempfile
import unittest
from psdash.log import Logs, LogReader


class TestLogs(unittest.TestCase):
    NEEDLE = "foobar\n"
    POSITIONS = [10000, 8000, 6000, 4000, 2000, 500]

    def setUp(self):
        fd, filename = tempfile.mkstemp()
        self.filename = filename
        self.fp = os.fdopen(fd, "w+")
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
        log.searcher.reset()
        positions = [log.search(self.NEEDLE)[0] for _ in xrange(len(self.POSITIONS))]
        self.assertEqual(self.POSITIONS, positions)

    def test_searching_other_buffer_size(self):
        log = LogReader(self.filename, LogReader.BUFFER_SIZE / 2)
        log.searcher.reset()
        positions = [log.search(self.NEEDLE)[0] for _ in xrange(len(self.POSITIONS))]
        self.assertEqual(self.POSITIONS, positions)


if __name__ == "__main__":
    unittest.main()