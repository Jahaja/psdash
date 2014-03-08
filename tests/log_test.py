import os
import tempfile
import unittest
from psdash.log import LogReader, Logs

class TestLogs(unittest.TestCase):
    NEEDLE = "foobar\n"
    FILLTEXT = "*" * LogReader.BUFFER_SIZE

    def setUp(self):
        fd, filename = tempfile.mkstemp()
        self.filename = filename
        self.fp = os.fdopen(fd, "w")
        for x in xrange(5):
            self.fp.write(self.FILLTEXT)
            self.fp.write(self.NEEDLE)
        self.fp.close()
        self.logs = Logs()
        self.logs.add_available(filename)

    def tearDown(self):
        self.logs.clear_available()


if __name__ == "__main__":
    unittest.main()