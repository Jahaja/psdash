# coding=utf-8

import time
import os


class LogSearcher(object):
    BUFFER_SIZE = 8192
    # Read 100 bytes extra to not miss keywords split between buffers
    EXTRA_SIZE = 200 

    instances = {}

    @classmethod
    def create(cls, filename, reverse=False, buffer_size=BUFFER_SIZE):
        key = int(str(time.time()).replace(".", ""))
        inst = cls(filename, reverse, buffer_size)
        cls.instances[key] = inst
        return key, inst

    @classmethod
    def load(cls, key):
        return cls.instances[key]

    def __init__(self, filename, reverse=False, buffer_size=BUFFER_SIZE):
        self.filename = filename
        self.fp = open(filename, "r")
        self.buffer_size = buffer_size
        self.stat = os.fstat(self.fp.fileno())
        self.bytes_left = self.stat.st_size
        self.reverse = reverse
        self.occurences = {}
        if reverse:
            self.fp.seek(0, os.SEEK_END)

    def __repr__(self):
        return "<LogSearcher filename=%s, bytes_left=%d, file-pos=%d>" % (
            self.filename, self.bytes_left, self.fp.tell()
        )

    def _set_read_pos(self):
        if self.reverse:
            pos = max(self.bytes_left - self.buffer_size, 0)
            self.fp.seek(pos)

    def _get_buffers(self):
        while self.bytes_left > 0:
            self._set_read_pos()
            buf = self.fp.read(min(self.buffer_size, self.bytes_left))
            self.bytes_left -= len(buf)
            if not buf:
                raise StopIteration

            yield buf

    def _read_result(self, pos):
        # Read a bit extra before the result pos
        padding = min(pos, self.buffer_size / 2)
        self.fp.seek(pos - padding)
        buf = self.fp.read(self.buffer_size)
        return buf

    def reached_end(self):
        return self.bytes_left == 0

    def reset(self):
        self.fp.seek(0, os.SEEK_END if self.reverse else os.SEEK_SET)
        self.stat = os.fstat(self.fp.fileno())
        self.bytes_left = self.stat.st_size

    def close(self):
        self.fp.close()

    def find_next(self, text):
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
                    self.bytes_left = pos
                    return (pos, res)

                lastbuf = buf[:self.EXTRA_SIZE]
            else:
                buf = lastbuf + buf
                i = buf.find(text)
                if i >= 0:
                    pos = (self.fp.tell() - len(buf)) + i
                    res = self._read_result(pos)
                    self.fp.seek(pos + len(text))
                    return (pos, res)

                lastbuf = buf[-self.EXTRA_SIZE:]
        return (-1, "")


class LogReader(object):
    READ_LENGTH = 16384

    available = set()
    logs = {}

    @classmethod
    def load(cls, filename, key=None):
        return cls.logs[(filename, key)]

    @classmethod
    def create(cls, filename, key=None):
        if filename not in cls.available:
            raise KeyError("No log with filename '%s' is available" % filename)

        key = (filename, key)
        inst = cls(filename)
        cls.logs[key] = inst
        return inst

    @classmethod
    def get_tail(cls, filename, key=None):
        key = (filename, key)
        inst = cls.logs.get(key, cls.create(*key))
        inst.set_tail_position()
        return inst

    @classmethod
    def add(cls, filename):
        return cls.available.add(filename)

    @classmethod
    def get_available(cls):
        return [cls(filename) for filename in cls.available]

    def __init__(self, filename):
        self.filename = filename
        self.fp = open(filename, "r")
        self.stat = os.fstat(self.fp.fileno())
        self.set_tail_position()

    def set_tail_position(self):
        if self.stat.st_size >= self.READ_LENGTH:
            self.fp.seek(-self.READ_LENGTH, os.SEEK_END)
        else:
            self.fp.seek(0)

    def read(self):
        return self.fp.read(self.READ_LENGTH)

    def close(self):
        self.fp.close()

