# coding=utf-8
from flask import render_template, request, session, jsonify, Response, Blueprint, current_app
import logging
import psutil
import platform
import socket
import os
from datetime import datetime
import uuid
import locale
from psdash.net import get_interface_addresses
from psdash.run import logs, net_io_counters
from psdash.helpers import (get_disks, get_users, get_network_interfaces, 
                            socket_families, socket_types, get_process_environ)

logger = logging.getLogger("psdash.web")
psdashapp = Blueprint("psdash", __name__, static_folder="static")


@psdashapp.before_request
def check_access():
    allowed_remote_addrs = current_app.config.get("PSDASH_ALLOWED_REMOTE_ADDRESSES")
    if allowed_remote_addrs:
        if request.remote_addr not in allowed_remote_addrs:
            current_app.logger.info(
                "Returning 401 for client %s as address is not in allowed addresses.",
                request.remote_addr
            )
            current_app.logger.debug("Allowed addresses: %s", allowed_remote_addrs)
            return "Access denied", 401

    username = current_app.config.get("PSDASH_AUTH_USERNAME")
    password = current_app.config.get("PSDASH_AUTH_PASSWORD")
    if username and password:
        auth = request.authorization
        if not auth or auth.username != username or auth.password != password:
            return Response(
                "Access deined",
                401,
                {'WWW-Authenticate': 'Basic realm="psDash login required"'}
            )


@psdashapp.before_request
def setup_client_id():
    if "client_id" not in session:
        client_id = uuid.uuid4()
        current_app.logger.debug("Creating id for client: %s", client_id)
        session["client_id"] = client_id


@psdashapp.errorhandler(404)
def page_not_found(e):
    current_app.logger.debug("Client tried to load an unknown route: %s", e)
    return render_template("error.html", error="Page not found."), 404


@psdashapp.errorhandler(psutil.AccessDenied)
def access_denied(e):
    errmsg = "Access denied to %s (pid %d)." % (e.name, e.pid)
    return render_template("error.html", error=errmsg), 401


@psdashapp.errorhandler(psutil.NoSuchProcess)
def access_denied(e):
    errmsg = "No process with pid %d was found." % e.pid
    return render_template("error.html", error=errmsg), 401


@psdashapp.route("/")
def index():
    load_avg = os.getloadavg()
    uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
    disks = get_disks()
    users = get_users()

    netifs = get_network_interfaces()
    netifs.sort(key=lambda x: x.get("bytes_sent"), reverse=True)

    data = {
        "os": platform.platform().decode("utf-8"),
        "hostname": socket.gethostname().decode("utf-8"),
        "uptime": str(uptime).split(".")[0],
        "load_avg": load_avg,
        "cpus": psutil.cpu_count(),
        "vmem": psutil.virtual_memory(),
        "swap": psutil.swap_memory(),
        "disks": disks,
        "cpu_percent": psutil.cpu_times_percent(0),
        "users": users,
        "net_interfaces": netifs,
        "page": "overview",
        "is_xhr": request.is_xhr
    }

    return render_template("index.html", **data)


@psdashapp.route("/processes", defaults={"sort": "cpu", "order": "desc"})
@psdashapp.route("/processes/<string:sort>")
@psdashapp.route("/processes/<string:sort>/<string:order>")
def processes(sort="pid", order="asc"):
    procs = []
    for p in psutil.process_iter():
        rss, vms = p.memory_info()

        # format created date from unix-timestamp
        dt = datetime.fromtimestamp(p.create_time())
        created = dt.strftime("%Y-%m-%d %H:%M:%S")

        proc = {
            "pid": p.pid,
            "name": p.name().decode("utf-8"),
            "cmdline": u" ".join(arg.decode("utf-8") for arg in p.cmdline()),
            "username": p.username().decode("utf-8"),
            "status": p.status(),
            "created": created,
            "rss": rss,
            "vms": vms,
            "memory": p.memory_percent(),
            "cpu": p.cpu_percent(0)
        }

        procs.append(proc)

    procs.sort(
        key=lambda x: x.get(sort),
        reverse=True if order != "asc" else False
    )

    return render_template(
        "processes.html",
        processes=procs,
        sort=sort,
        order=order,
        page="processes",
        is_xhr=request.is_xhr
    )


@psdashapp.route("/process/<int:pid>/limits")
def process_limits(pid):
    p = psutil.Process(pid)

    limits = {
        "RLIMIT_AS": p.rlimit(psutil.RLIMIT_AS),
        "RLIMIT_CORE": p.rlimit(psutil.RLIMIT_CORE),
        "RLIMIT_CPU": p.rlimit(psutil.RLIMIT_CPU),
        "RLIMIT_DATA": p.rlimit(psutil.RLIMIT_DATA),
        "RLIMIT_FSIZE": p.rlimit(psutil.RLIMIT_FSIZE),
        "RLIMIT_LOCKS": p.rlimit(psutil.RLIMIT_LOCKS),
        "RLIMIT_MEMLOCK": p.rlimit(psutil.RLIMIT_MEMLOCK),
        "RLIMIT_MSGQUEUE": p.rlimit(psutil.RLIMIT_MSGQUEUE),
        "RLIMIT_NICE": p.rlimit(psutil.RLIMIT_NICE),
        "RLIMIT_NOFILE": p.rlimit(psutil.RLIMIT_NOFILE),
        "RLIMIT_NPROC": p.rlimit(psutil.RLIMIT_NPROC),
        "RLIMIT_RSS": p.rlimit(psutil.RLIMIT_RSS),
        "RLIMIT_RTPRIO": p.rlimit(psutil.RLIMIT_RTPRIO),
        "RLIMIT_RTTIME": p.rlimit(psutil.RLIMIT_RTTIME),
        "RLIMIT_SIGPENDING": p.rlimit(psutil.RLIMIT_SIGPENDING),
        "RLIMIT_STACK": p.rlimit(psutil.RLIMIT_STACK)
    }

    return render_template(
        "process/limits.html",
        limits=limits,
        process=p,
        section="limits",
        page="processes",
        is_xhr=request.is_xhr
    )


@psdashapp.route("/process/<int:pid>", defaults={"section": "overview"})
@psdashapp.route("/process/<int:pid>/<string:section>")
def process(pid, section):
    valid_sections = [
        "overview",
        "threads",
        "files",
        "connections",
        "memory",
        "environment",
        "children"
    ]

    if section not in valid_sections:
        errmsg = "Invalid subsection when trying to view process %d" % pid
        return render_template("error.html", error=errmsg), 404

    context = {
        "process": psutil.Process(pid),
        "section": section,
        "page": "processes",
        "is_xhr": request.is_xhr
    }

    if section == "environment":
        context["process_environ"] = get_process_environ(pid)

    return render_template(
        "process/%s.html" % section,
        **context
    )


@psdashapp.route("/network")
def view_networks():
    netifs = get_network_interfaces()
    netifs.sort(key=lambda x: x.get("bytes_sent"), reverse=True)

    conns = psutil.net_connections()
    conns.sort(key=lambda x: x.status)

    return render_template(
        "network.html",
        page="network",
        network_interfaces=netifs,
        net_connections=conns,
        socket_families=socket_families,
        socket_types=socket_types,
        is_xhr=request.is_xhr
    )


@psdashapp.route("/disks")
def view_disks():
    disks = get_disks(all_partitions=True)
    io_counters = psutil.disk_io_counters(perdisk=True).items()
    io_counters.sort(key=lambda x: x[1].read_count, reverse=True)
    return render_template(
        "disks.html",
        page="disks",
        disks=disks,
        io_counters=io_counters,
        is_xhr=request.is_xhr
    )


@psdashapp.route("/logs")
def view_logs():
    available_logs = []
    for log in logs.get_available():
        try:
            stat = os.stat(log.filename)
        except OSError:
            logger.warning("Could not stat %s, removing from available logs", log.filename)
            logs.remove_available(log.filename)
            continue

        dt = datetime.fromtimestamp(stat.st_atime)
        last_access = dt.strftime("%Y-%m-%d %H:%M:%S")

        dt = datetime.fromtimestamp(stat.st_mtime)
        last_modification = dt.strftime("%Y-%m-%d %H:%M:%S")

        available_logs.append({
            "filename": log.filename,
            "size": stat.st_size,
            "last_access": last_access,
            "last_modification": last_modification
        })

    available_logs.sort(cmp=lambda x1, x2: locale.strcoll(x1["filename"], x2["filename"]))

    return render_template(
        "logs.html",
        page="logs",
        logs=available_logs,
        is_xhr=request.is_xhr
    )


@psdashapp.route("/log")
def view_log():
    filename = request.args["filename"]

    try:
        log = logs.get(filename, key=session.get("client_id"))
        log.set_tail_position()
        content = log.read()
    except KeyError:
        return render_template("error.html", error="Only files passed through args are allowed."), 401

    return render_template("log.html", content=content, filename=filename)


@psdashapp.route("/log/read")
def read_log():
    filename = request.args["filename"]

    try:
        log = logs.get(filename, key=session.get("client_id"))
        return log.read()
    except KeyError:
        return "Could not find log file with given filename", 404


@psdashapp.route("/log/read_tail")
def read_log_tail():
    filename = request.args["filename"]

    try:
        log = logs.get(filename, key=session.get("client_id"))
        log.set_tail_position()
        return log.read()
    except KeyError:
        return "Could not find log file with given filename", 404


@psdashapp.route("/log/search")
def search_log():
    filename = request.args["filename"]
    query_text = request.args["text"]

    log = logs.get(filename, key=session.get("client_id"))
    pos, bufferpos, res = log.search(query_text)
    if log.searcher.reached_end():
        log.searcher.reset()

    stat = os.stat(log.filename)

    data = {
        "position": pos,
        "buffer_pos": bufferpos,
        "filesize": stat.st_size,
        "content": res
    }

    return jsonify(data)
