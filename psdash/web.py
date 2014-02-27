# coding=utf-8
from flask import Flask, render_template, redirect, flash, g, request, session, jsonify
import sys
import psutil
import platform
import socket
import time
import os
from datetime import datetime
from net import get_network_interfaces
from log import LogReader, LogSearcher


app = Flask(__name__)
app.config.from_envvar("PSDASH_CONFIG", silent=True)
app.secret_key = "whatisthissourcery"


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

@app.route("/overview/cpu")
def overview_cpu():
    cpu = psutil.cpu_times_percent(0)
    data = {
        "load_avg": os.getloadavg(),
        "user": cpu.user,
        "system": cpu.system,
        "idle": cpu.idle,
        "iowait": cpu.iowait
    }
    return jsonify(data)

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
    if request.is_xhr:
        filesizeformat = app.jinja_env.filters['filesizeformat']
        network_interfaces = []
        for netif in get_network_interfaces():
            netif["rx_per_sec"] = filesizeformat(netif["rx_per_sec"])
            netif["tx_per_sec"] = filesizeformat(netif["tx_per_sec"])
            network_interfaces.append(netif)

        return jsonify({"network_interfaces": network_interfaces})
    else:
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
    available_logs = []
    for l in LogReader.get_available():
        dt = datetime.fromtimestamp(l.stat.st_atime)
        last_access = dt.strftime("%Y-%m-%d %H:%M:%S")

        dt = datetime.fromtimestamp(l.stat.st_mtime)
        last_modification = dt.strftime("%Y-%m-%d %H:%M:%S")

        alog = {
            "filename": l.filename,
            "size": l.stat.st_size,
            "last_access": last_access,
            "last_modification": last_modification
        }
        available_logs.append(alog)

    return render_template("logs.html", page="logs", logs=available_logs)


@app.route("/log")
def view_log():
    filename = request.args["filename"]

    try:
        log = LogReader.get_tail(filename)
    except KeyError:
        return render_template("error.html", error="Only files passed through args are allowed."), 401

    return render_template("log.html", content=log.read(), filename=filename)


@app.route("/log/read")
def read_log():
    filename = request.args["filename"]

    try:
        log = LogReader.load(filename)
    except KeyError:
        return "Could not find log file with given filename", 404
    
    return log.read()


@app.route("/log/read_tail")
def read_log_tail():
    filename = request.args["filename"]

    try:
        log = LogReader.get_tail(filename)
    except KeyError:
        return "Could not find log file with given filename", 404
    
    return log.read()


@app.route("/log/search")
def search_log():
    filename = request.args["filename"]
    query_text = request.args["text"]
    
    skey = session.get("search_key")
    if not skey:
        skey, searcher = LogSearcher.create(filename, reverse=True)
        session["search_key"] = skey
    else:
        searcher = LogSearcher.load(skey)

    pos, res = searcher.find_next(query_text)
    app.logger.debug("Pos: %d", pos)
    app.logger.debug("Searcher: %r", searcher)
    if searcher.reached_end():
        searcher.reset()

    data = {
        "position": pos, 
        "filesize": searcher.stat.st_size, 
        "content": res
    }

    return jsonify(data)


@app.route("/log/search/reset")
def search_reset():
    del session["search_key"]
    return "OK"


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for log in sys.argv[1:]:
            LogReader.add(log)

    app.run(debug=True)



