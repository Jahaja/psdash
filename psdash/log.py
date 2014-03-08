# coding=utf-8
import time
import os


class LogSearcher(object):
    # Read 200 bytes extra to not miss keywords split between buffers
    EXTRA_SIZE = 200

    def __init__(self, log, reverse=False):
        self.log = log
        self.reverse = reverse

    @property
    def bytes_left(self):
        if self.reverse:
            return self.log.fp.tell()
        else:
            return max(self.log.stat.st_size - self.log.fp.tell(), 0)

    def __repr__(self):
        return "<LogSearcher filename=%s, bytes_left=%d, file-pos=%d>" % (
            self.log.filename, self.bytes_left, self.log.fp.tell()
        )

    def _set_read_pos(self):
        if self.reverse:
            pos = max(self.bytes_left - self.log.buffer_size, 0)
            self.log.fp.seek(pos)

    def _get_buffers(self):
        while self.bytes_left > 0:
            self._set_read_pos()
            buf = self.log.fp.read(min(self.log.buffer_size, self.bytes_left))
            if self.reverse:
                self.log.fp.seek(-len(buf), os.SEEK_CUR)
            if not buf:
                raise StopIteration

            yield buf

    def _read_result(self, pos):
        # Read a bit extra before the result pos
        padding = min(pos, self.log.buffer_size / 2)
        self.log.fp.seek(pos - padding)
        buf = self.log.fp.read(self.log.buffer_size)
        return buf

    def reached_end(self):
        return self.bytes_left == 0

    def reset(self):
        self.log.fp.seek(0, os.SEEK_END if self.reverse else os.SEEK_SET)
        self.log.stat = os.fstat(self.log.fp.fileno())

    def find_next(self, text):
        print repr(self)
        lastbuf = ""
        for buf in self._get_buffers():
            if self.reverse:
                buf += lastbuf
                i = buf.rfind(text)
                if i >= 0:
                    # get position of the found text
                    pos = self.bytes_left + i
                    # read a whole buffer with the result in the middle
                    res = self._read_result(pos)
                    # and make sure to start searching the next result from here
                    self.log.fp.seek(pos)
                    return (pos, res)

                lastbuf = buf[:self.EXTRA_SIZE]
            else:
                buf = lastbuf + buf
                i = buf.find(text)
                if i >= 0:
                    pos = (self.log.fp.tell() - len(buf)) + i
                    res = self._read_result(pos)
                    self.log.fp.seek(pos + len(text))
                    return (pos, res)

                lastbuf = buf[-self.EXTRA_SIZE:]
        return (-1, "")


class LogReader(object):
    BUFFER_SIZE = 16384

    def __init__(self, filename, buffer_size=BUFFER_SIZE):
        self.filename = filename
        self.fp = open(filename, "r")
        self.stat = os.fstat(self.fp.fileno())
        self.buffer_size = buffer_size
        self.searcher = LogSearcher(self, reverse=True)

    def set_tail_position(self):
        if self.stat.st_size >= self.buffer_size:
            self.fp.seek(-self.buffer_size, os.SEEK_END)
        else:
            self.fp.seek(0)

    def read(self):
        buf = self.fp.read(self.buffer_size)
        return buf

    def search(self, text):
        return self.searcher.find_next(text)

    def close(self):
        self.fp.close()


class Logs(object):
    def __init__(self):
        self.available = set()
        self.readers = {}

    def add_available(self, filename):
        return self.available.add(filename)

    def get_available(self):
        return [self.get_reader(filename) for filename in self.available]

    def clear_available(self):
        self.available = set()

    def clear_readers(self):
        for r in self.readers.itervalues():
            r.close()
        self.readers = {}

    def create_reader(self, filename, key=None):
        if filename not in self.available:
            raise KeyError("No log with filename '%s' is available" % filename)

        key = (filename, key)
        r = LogReader(filename)
        self.readers[key] = r
        return r

    def get_reader(self, filename, key=None):
        reader_key = (filename, key)
        if reader_key not in self.readers:
            return self.create_reader(filename, key)
        else:
            return self.readers.get(reader_key)

