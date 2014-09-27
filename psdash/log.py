# coding=utf-8
import glob2
import os
import logging

logger = logging.getLogger('psdash.log')


class LogError(Exception):
    pass


class ReverseFileSearcher(object):
    DEFAULT_CHUNK_SIZE = 8192

    def __init__(self, filename, needle, chunk_size=DEFAULT_CHUNK_SIZE):
        self._chunk_size = int(chunk_size)

        if not needle:
            raise ValueError("Needle is empty")

        if len(needle) > self._chunk_size:
            raise ValueError("Needle size is larger than the chunk size.")

        self._filename = filename
        self._needle = needle
        self._fp = open(filename, "r")
        self.reset()

    def reset(self):
        self._fp.seek(0, os.SEEK_END)

    def __iter__(self):
        return self

    def next(self):
        pos = self.find()
        if pos < 0:
            raise StopIteration
        return pos

    def _read(self):
        """
        Reads and returns a buffer reversely from current file-pointer position.

        :rtype : str
        """
        filepos = self._fp.tell()
        if filepos < 1:
            return ""
        destpos = max(filepos - self._chunk_size, 0)
        self._fp.seek(destpos)
        buf = self._fp.read(filepos - destpos)
        self._fp.seek(destpos)
        return buf

    def find(self):
        """
        Returns the position of the first occurence of needle.
        If the needle was not found, -1 is returned.

        :rtype : int
        """
        lastbuf = ""
        while 0 < self._fp.tell():
            buf = self._read()
            bufpos = (buf + lastbuf).rfind(self._needle)
            if bufpos > -1:
                filepos = self._fp.tell() + bufpos
                self._fp.seek(filepos)
                return filepos

            # for it to work when the needle is split between chunks.
            lastbuf = buf[:len(self._needle)]

        return -1

    def find_all(self):
        """
        Searches the file for occurences of self.needle
        Returns a tuple of positions where occurences was found.

        :rtype : tuple
        """
        self.reset()
        return tuple(pos for pos in self)


class LogReader(object):
    BUFFER_SIZE = 8192

    def __init__(self, filename, buffer_size=BUFFER_SIZE):
        self.filename = filename
        self.fp = open(filename, 'r')
        self.buffer_size = buffer_size
        self._searchers = {}

    def __repr__(self):
        return '<LogReader filename=%s, file-pos=%d>' % (
            self.filename, self.fp.tell()
        )

    def set_tail_position(self):
        stat = os.fstat(self.fp.fileno())
        if stat.st_size >= self.buffer_size:
            self.fp.seek(-self.buffer_size, os.SEEK_END)
        else:
            self.fp.seek(0)

    def read(self):
        buf = self.fp.read(self.buffer_size)
        return buf

    def search(self, text):
        """
        Find text in log file from current position

        returns a tuple containing:
            absolute position,
            position in result buffer,
            result buffer (the actual file contents)
        """
        key = hash(text)
        searcher = self._searchers.get(key)
        if not searcher:
            searcher = ReverseFileSearcher(self.filename, text)
            self._searchers[key] = searcher

        position = searcher.find()
        if position < 0:
            # reset the searcher to start from the tail again.
            searcher.reset()
            return -1, -1, ''

        # try to get some content from before and after the result's position
        read_before = self.buffer_size / 2
        offset = max(position - read_before, 0)
        bufferpos = position if offset == 0 else read_before
        self.fp.seek(offset)
        return position, bufferpos, self.read()

    def close(self):
        self.fp.close()


class Logs(object):
    def __init__(self):
        self.available = set()
        self.readers = {}

    def add_available(self, filename):
        # quick verification that it exists and can be read
        try:
            filename = filename.decode('utf-8')
            f = open(filename)
            f.close()
        except IOError as e:
            raise LogError('Could not read log file "%s" (%s)' % (filename, e))

        logger.debug('Adding log file %s', filename)

        return self.available.add(filename)

    def remove_available(self, filename):
        self.remove(filename)
        self.available.remove(filename)

    def get_available(self):
        available = []
        to_remove = []
        for filename in self.available:
            try:
                log = self.get(filename)
                available.append(log)
            except IOError:
                logger.info('Failed to get "%s", removing from available logs', filename)
                to_remove.append(filename)

        if to_remove:
            map(self.remove_available, to_remove)

        return available

    def clear_available(self):
        self.clear()
        self.available = set()

    def add_patterns(self, patterns):
        i = 0
        for p in patterns:
            for log_file in glob2.iglob(p):
                if os.path.isfile(log_file):
                    try:
                        self.add_available(log_file)
                        i += 1
                    except LogError as e:
                        logger.warning(e)

        logger.info('Added %d log file(s)', i)
        return i

    def clear(self):
        for r in self.readers.itervalues():
            r.close()
        self.readers = {}

    def remove(self, filename):
        for reader_key, r in self.readers.items():
            if reader_key[0] == filename:
                r.close()
                del self.readers[reader_key]

    def create(self, filename, key=None):
        if filename not in self.available:
            raise KeyError('No log with filename "%s" is available' % filename)

        reader_key = (filename, key)
        r = LogReader(filename)
        self.readers[reader_key] = r
        return r

    def get(self, filename, key=None):
        reader_key = (filename, key)
        if reader_key not in self.readers:
            return self.create(filename, key)
        else:
            return self.readers.get(reader_key)
