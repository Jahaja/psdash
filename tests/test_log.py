# coding=utf-8
import os
import tempfile
import unittest2
import time
from cStringIO import StringIO
from psdash.log import Logs, LogReader, LogError, ReverseFileSearcher


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
        self.assertIn('<LogReader', repr(log))

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

    def test_add_dir(self):
        num_added = self.logs.add_patterns(['/tmp'])
        self.assertEqual(num_added, 0)


class TestFileSearcher(unittest2.TestCase):
        def _create_temp_file(self, buf):
            _, filename = tempfile.mkstemp("log")
            with open(filename, "w") as f:
                f.write(buf)
                f.flush()

            return filename

        def setUp(self):
            self.needle = "THENEEDLE"
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)
            self.positions = [1000, 2000, 2500, 3700, 7034, 8343]
            for pos in self.positions:
                buf.seek(pos)
                buf.write(self.needle)

            self.filename = self._create_temp_file(buf.getvalue())
            self.searcher = ReverseFileSearcher(self.filename, self.needle)

        def test_construction(self):
            self.assertEqual(self.searcher._filename, self.filename)
            self.assertEqual(self.searcher._needle, self.needle)

        def test_find_all(self):
            positions = self.searcher.find_all()
            self.assertEqual(positions, tuple(reversed(self.positions)))

        def test_find_one(self):
            pos = self.searcher.find()
            self.assertEqual(pos, self.positions[-1])

        def test_unicode(self):
            encoding = "utf-8"
            needle = u"Åter till testerna, så låt oss nu testa lite".encode(encoding)
            buf = StringIO()
            data = (u"Det är nog bra att ha några konstiga bokstäver här med.\n" * 10000).encode(encoding)
            buf.write(data)
            positions = [1000, 2000, 2500, 3700, 7034, 8343]
            for pos in positions:
                buf.seek(pos)
                buf.write(needle)

            filename = self._create_temp_file(buf.getvalue())
            searcher = ReverseFileSearcher(filename, needle)

            self.assertEqual(searcher.find_all(), tuple(reversed(self.positions)))

        def test_needle_split_by_chunk(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)
            buf.seek(-(ReverseFileSearcher.DEFAULT_CHUNK_SIZE + 5), os.SEEK_END)
            buf.write(self.needle)

            filename = self._create_temp_file(buf.getvalue())
            searcher = ReverseFileSearcher(filename, self.needle)

            found_positions = searcher.find_all()
            self.assertEqual(len(found_positions), 1)

        def test_needle_on_chunk_border(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)
            buf.seek(-ReverseFileSearcher.DEFAULT_CHUNK_SIZE, os.SEEK_END)
            buf.write(self.needle)

            filename = self._create_temp_file(buf.getvalue())
            searcher = ReverseFileSearcher(filename, self.needle)

            found_positions = searcher.find_all()
            self.assertEqual(len(found_positions), 1)

        def test_needle_on_chunk_border_does_not_hide_occurence(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)
            buf.seek(-(ReverseFileSearcher.DEFAULT_CHUNK_SIZE + 100), os.SEEK_END)
            buf.write(self.needle)
            buf.seek(-ReverseFileSearcher.DEFAULT_CHUNK_SIZE, os.SEEK_END)
            buf.write(self.needle)

            filename = self._create_temp_file(buf.getvalue())
            searcher = ReverseFileSearcher(filename, self.needle)

            found_positions = searcher.find_all()
            self.assertEqual(len(found_positions), 2)

        def test_lots_of_needles_in_same_chunk(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)
            buf.seek(-(ReverseFileSearcher.DEFAULT_CHUNK_SIZE + 100), os.SEEK_END)
            for _ in xrange(20):
                buf.write(self.needle)

            filename = self._create_temp_file(buf.getvalue())
            searcher = ReverseFileSearcher(filename, self.needle)

            found_positions = searcher.find_all()
            self.assertEqual(len(found_positions), 20)

        def test_single_chunk(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 100)
            for _ in xrange(20):
                buf.write(self.needle)

            filename = self._create_temp_file(buf.getvalue())
            searcher = ReverseFileSearcher(filename, self.needle)

            found_positions = searcher.find_all()
            self.assertEqual(len(found_positions), 20)

        def test_single_char(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)

            filename = self._create_temp_file(buf.getvalue())
            searcher = ReverseFileSearcher(filename, "C")

            found_positions = searcher.find_all()
            self.assertEqual(len(found_positions), 10000)

        def test_empty_needle(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)

            filename = self._create_temp_file(buf.getvalue())
            self.assertRaises(ValueError, ReverseFileSearcher, filename, "")

        def test_needle_larger_than_chunk_size(self):
            buf = StringIO()
            buf.write("TESTING SOME SEARCHING!\n" * 10000)
            needle = "NEEDLE" * ReverseFileSearcher.DEFAULT_CHUNK_SIZE

            filename = self._create_temp_file(buf.getvalue())
            self.assertRaises(ValueError, ReverseFileSearcher, filename, needle)


if __name__ == '__main__':
    unittest2.main()