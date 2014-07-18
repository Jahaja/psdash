# coding=utf-8
import glob2
import os
import logging

logger = logging.getLogger('psdash.log')

class LogError(Exception):
    pass

class LogSearcher(object):
    # Read 200 bytes extra to not miss keywords split between buffers
    EXTRA_SIZE = 200

    def __init__(self, log):
        self.log = log

    @property
    def position(self):
        return self.log.fp.tell()

    def __repr__(self):
        return '<LogSearcher filename=%s, file-pos=%d>' % (
            self.log.filename, self.position
        )

    def _read(self, length=None, offset=None):
        """
        This method reads from the log file starting at the given offset and
        reads at most the number of bytes specified by the length parameter.

        This method will make sure to not alter the file's position when returned.
        """
        if not length:
            length = self.log.buffer_size

        pos = self.position
        if offset:
            self.log.fp.seek(offset)
        buf = self.log.fp.read(length).decode('utf8')
        self.log.fp.seek(pos)
        return buf

    def _get_buffers(self):
        while not self.reached_end():
            # make sure to not read what's already been read
            # when we're at the beginning of the file.
            length = min(self.log.buffer_size, self.position)
            self.log.fp.seek(-length, os.SEEK_CUR)
            buf = self._read(length=length)

            yield buf

    def _read_result(self, position):
        # try to get the result in the middle of a buffer length of content.
        read_before = self.log.buffer_size / 2
        offset = max(position - read_before, 0)
        respos = position if offset == 0 else read_before
        return respos, self._read(offset=offset)

    def reached_end(self):
        return self.position == 0

    def reset(self):
        self.log.fp.seek(0, os.SEEK_END)

    def find_next(self, text):
        """
        Find text in log file from current position

        returns a tuple containing:
            absolute position,
            position in result buffer,
            result buffer (the actual file contents)
        """
        lastbuf = ''
        for buf in self._get_buffers():
            buf += lastbuf
            i = buf.rfind(text.decode('utf8'))
            if i >= 0:
                # get position of the found text
                pos = self.position + i
                # try to read a whole buffer length with the result in the middle
                respos, resbuf = self._read_result(pos)
                # move the file position to the result pos to make sure we start from
                # this position to not miss results in the same buffer.
                self.log.fp.seek(pos)
                return pos, respos, resbuf

            lastbuf = buf[:self.EXTRA_SIZE]
        return -1, -1, ''


class LogReader(object):
    BUFFER_SIZE = 8192

    def __init__(self, filename, buffer_size=BUFFER_SIZE):
        self.filename = filename
        self.fp = open(filename, 'r')
        self.buffer_size = buffer_size
        self.searcher = LogSearcher(self)

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
        return self.searcher.find_next(text)

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
