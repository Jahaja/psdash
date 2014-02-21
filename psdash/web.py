# coding=utf-8
from flask import Flask, render_template, redirect, flash, g, request
import sys
import psutil
import platform
import socket
import time
import os
from datetime import datetime
from net import get_network_interfaces

app = Flask(__name__)
app.config.from_envvar("PSDASH_CONFIG", silent=True)
app.secret_key = "whatisthissourcery"


class LogSearcher(object):
    BUFFER_SIZE = 8192
    # read 100 bytes extra to avoid missing keywords split between buffers
    EXTRA_SIZE = 100 

    def __init__(self, filename, reverse=False, buffer_size=BUFFER_SIZE):
        self.filename = filename
        self.fp = open(filename, "r")
        self.buffer_size = buffer_size
        self.stat = os.fstat(self.fp.fileno())
        self.bytes_left = self.stat.st_size
        self.reverse = reverse
        if reverse:
            self.fp.seek(0, os.SEEK_END)

    def _set_read_pos(self):
        currpos = self.fp.tell()
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
        self.fp.seek(pos - (self.buffer_size / 2))
        buf = self.fp.read(self.buffer_size) 
        return buf

    def reset(self):
        if self.reverse:
            self.seek(0, os.SEEK_END)
        else:
            self.seek(0)

    def find(self, text):
        lastbuf = ""
        for buf in self._get_buffers():
            buf = lastbuf + buf
            if self.reverse:
                i = buf.rfind(text)
                if i >= 0:
                    pos = self.bytes_left + i
                    return self._read_result(pos)
            else:
                i = buf.find(text)
                if i >= 0:
                    pos = (self.fp.tell() - len(buf)) + i
                    return self._read_result(pos)

            lastbuf = buf[-self.EXTRA_SIZE:]
        return 0


class Log(object):
    TAIL_LENGTH = 1024 * 5
    READ_LENGTH = 1024 * 5

    logs = {}

    @classmethod
    def get(cls, filename, key=None):
        idt = filename
        if filename not in cls.logs:
            cls.logs[idt] = cls(filename)

        return cls.logs[idt]

    @classmethod
    def add(cls, filename, key=None):
        return cls.get(filename, key)

    def __init__(self, filename):
        self.filename = filename
        self.fp = open(filename, "r")
        self.stat = os.fstat(self.fp.fileno())

        if self.stat.st_size >= self.TAIL_LENGTH:
            self.fp.seek(-self.TAIL_LENGTH, os.SEEK_END)

    def read(self):
        self.stat = os.fstat(self.fp.fileno())
        return self.fp.read(self.READ_LENGTH)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="Page not found."), 404


@app.errorhandler(psutil.AccessDenied)
def access_denied(e):
    errmsg = "Access denied to %s (pid %d)." % (e.name, e.pid)
    return render_template("error.html", error=errmsg), 401


@app.errorhandler(psutil.NoSuchProcess)
def access_denied(e):
    errmsg = "No process with pid %d was found." % e.pid
    return render_template("error.html", error=errmsg), 401


@app.route("/")
def index():
    load_avg = os.getloadavg()
    uptime = datetime.now() - datetime.fromtimestamp(psutil.get_boot_time())
    disks = [
        (dp, psutil.disk_usage(dp.mountpoint)) 
        for dp in psutil.disk_partitions()
    ]

    users = []
    for u in psutil.get_users():
        dt = datetime.fromtimestamp(u.started)
        user = {
            "name": u.name,
            "terminal": u.terminal,
            "started": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "host": u.host
        }

        users.append(user)

    data = {
        "os": platform.platform(),
        "hostname": socket.gethostname(),
        "uptime": str(uptime).split(".")[0],
        "load_avg": load_avg,
        "cpus": psutil.NUM_CPUS,
        "vmem": psutil.virtual_memory(),
        "swap": psutil.swap_memory(),
        "disks": disks,
        "cpu_percent": psutil.cpu_times_percent(0),
        "users": users,
        "net_interfaces": get_network_interfaces(),
        "page": "overview"
    }

    return render_template("index.html", **data)


@app.route("/processes", defaults={"sort": "cpu", "order": "desc"})
@app.route("/processes/<string:sort>")
@app.route("/processes/<string:sort>/<string:order>")
def processes(sort="pid", order="asc"):
    procs = []
    for p in psutil.process_iter():
        rss, vms = p.get_memory_info()

        # format created date from unix-timestamp
        dt = datetime.fromtimestamp(p.create_time)
        created = dt.strftime("%Y-%m-%d %H:%M:%S")

        proc = {
            "pid": p.pid,
            "name": p.name,
            "cmdline": " ".join(p.cmdline),
            "username": p.username,
            "status": p.status,
            "created": created,
            "rss": rss,
            "vms": vms,
            "memory": p.get_memory_percent(),
            "cpu": p.get_cpu_percent(0)
        }

        procs.append(proc)

    procs.sort(
        key=lambda p: p.get(sort), 
        reverse=True if order != "asc" else False
    )

    return render_template(
        "processes.html", 
        processes=procs, 
        sort=sort, 
        order=order,
        page="processes"
    )


@app.route("/process/<int:pid>/limits")
def process_limits(pid):
    p = psutil.Process(pid)

    limits = {
        "RLIMIT_AS": p.get_rlimit(psutil.RLIMIT_AS),
        "RLIMIT_CORE": p.get_rlimit(psutil.RLIMIT_CORE),
        "RLIMIT_CPU": p.get_rlimit(psutil.RLIMIT_CPU),
        "RLIMIT_DATA": p.get_rlimit(psutil.RLIMIT_DATA),
        "RLIMIT_FSIZE": p.get_rlimit(psutil.RLIMIT_FSIZE),
        "RLIMIT_LOCKS": p.get_rlimit(psutil.RLIMIT_LOCKS),
        "RLIMIT_MEMLOCK": p.get_rlimit(psutil.RLIMIT_MEMLOCK),
        "RLIMIT_MSGQUEUE": p.get_rlimit(psutil.RLIMIT_MSGQUEUE),
        "RLIMIT_NICE": p.get_rlimit(psutil.RLIMIT_NICE),
        "RLIMIT_NOFILE": p.get_rlimit(psutil.RLIMIT_NOFILE),
        "RLIMIT_NPROC": p.get_rlimit(psutil.RLIMIT_NPROC),
        "RLIMIT_RSS": p.get_rlimit(psutil.RLIMIT_RSS),
        "RLIMIT_RTPRIO": p.get_rlimit(psutil.RLIMIT_RTPRIO),
        "RLIMIT_RTTIME": p.get_rlimit(psutil.RLIMIT_RTTIME),
        "RLIMIT_SIGPENDING": p.get_rlimit(psutil.RLIMIT_SIGPENDING),
        "RLIMIT_STACK": p.get_rlimit(psutil.RLIMIT_STACK)
    }

    return render_template(
        "process/limits.html", 
        limits=limits,
        process=p,
        section="limits",
        page="processes"
    )


@app.route("/process/<int:pid>", defaults={"section": "overview"})
@app.route("/process/<int:pid>/<string:section>")
def process(pid, section):
    valid_sections = [
        "overview", 
        "threads", 
        "files", 
        "connections",
        "memory",
        "children"
    ]

    if section not in valid_sections:
        errmsg = "Invalid subsection when trying to view process %d" % pid
        return render_template("error.html", error=errmsg), 404

    return render_template(
        "process/%s.html" % section, 
        process=psutil.Process(pid), 
        section=section,
        page="processes"
    )

@app.route("/network")
def network():
    return render_template(
        "network.html", 
        page="network", 
        network_interfaces=get_network_interfaces()
    )


@app.route("/memory")
def memory():
    return render_template("memory.html", page="memory")


@app.route("/disks")
def disks():
    disks = [
        (dp, psutil.disk_usage(dp.mountpoint)) 
        for dp in psutil.disk_partitions(all=True)
    ]

    return render_template(
        "disks.html", 
        page="disks", 
        disks=disks,
        io_counters=psutil.disk_io_counters(perdisk=True)
    )


@app.route("/users")
def users():
    return render_template("users.html", page="users")


@app.route("/logs")
def view_logs():
    return render_template("logs.html", page="logs", logs=Log.logs)


@app.route("/log")
def view_log():
    filename = request.args["filename"]
    if filename not in Log.logs:
        return render_template("error.html", error="Only files passed through args are allowed."), 401

    log = Log.get(filename)
    return render_template("log.html", content=log.read(), filename=filename)


@app.route("/log/read")
def read_log():
    filename = request.args["filename"]
    if filename not in Log.logs:
        return render_template("error.html", error="Only files passed through args are allowed."), 401

    log = Log.get(filename)
    return log.read()


@app.route("/log/search")
def search_log():
    filename = request.args["filename"]
    query_text = request.args["text"]
    searcher = LogSearcher(filename, True)
    res = searcher.find(query_text)
    if res:
        return res
    else:
        return "Could not find '%s'" % query_text


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for log in sys.argv[1:]:
            Log.add(log)

    app.run(debug=True)



