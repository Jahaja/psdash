# coding=utf-8
from flask import Flask, render_template, redirect, flash, g
import psutil
import platform
import socket
import time
import os
from datetime import datetime

app = Flask(__name__)
app.config.from_envvar("PSDASH_CONFIG", silent=True)
app.secret_key = "whatisthissourcery"

class NetIOCounters(object):
    _last_req = None
    _last_req_time = None

    @classmethod
    def request(cls):
        io_counters = psutil.network_io_counters(pernic=True)
        if not cls._last_req:
            # no request to compare with so let's just return.
            app.logger.debug("No request to compare with.")
            cls._last_req = io_counters
            cls._last_req_time = time.time()

            io = {"tx_per_sec": 0, "rx_per_sec": 0}
            return dict((n, io) for n in io_counters)

        elapsed = int(time.time() - cls._last_req_time)
        elapsed = max(elapsed, 1)

        netio = {}
        for n, io in io_counters.iteritems():
            last_io = cls._last_req.get(n)
            if not last_io:
                # seemingly a new interface so let's skip this one.
                netio[n] = {"tx_per_sec": 0, "rx_per_sec": 0}
                continue

            netio[n] = {
                "rx_per_sec": (io.bytes_recv - last_io.bytes_recv) / elapsed,
                "tx_per_sec": (io.bytes_sent - last_io.bytes_sent) / elapsed
            }

        cls._last_req = io_counters
        cls._last_req_time = time.time()

        return netio


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
        "netio": NetIOCounters.request()
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
        order=order
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
        section="limits"
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
        section=section
    )


if __name__ == '__main__':
    app.run(debug=app.config.get("ENABLE_DEBUG", True))
