# coding=utf-8
import argparse
from flask import Flask, render_template, request, session, jsonify, Response, Blueprint
import logging
import psutil
import platform
import socket
import os
from datetime import datetime
import time
import threading
import uuid
import locale
from log import Logs
from net import NetIOCounters, get_interface_addresses

logs = Logs()
net_io_counters = NetIOCounters()
logger = logging.getLogger("psdash.web")


def get_disks(all_partitions=False):
    disks = [
        (dp, psutil.disk_usage(dp.mountpoint))
        for dp in psutil.disk_partitions(all_partitions)
    ]
    disks.sort(key=lambda d: d[1].total, reverse=True)
    return disks


def get_users():
    users = []
    for u in psutil.users():
        dt = datetime.fromtimestamp(u.started)
        user = {
            "name": u.name.decode("utf-8"),
            "terminal": u.terminal,
            "started": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "host": u.host.decode("utf-8")
        }

        users.append(user)
    return users


def get_network_interfaces():
    io_counters = net_io_counters.get()
    addresses = get_interface_addresses()

    for inf in addresses:
        inf.update(io_counters.get(inf["name"], {}))

    return addresses


def get_process_environ(pid):
    with open("/proc/%d/environ" % pid) as f:
        contents = f.read()
        env_vars = dict(row.split("=") for row in contents.split("\0") if "=" in row)

    return env_vars


def socket_constants(prefix):
    return dict((getattr(socket, n), n) for n in dir(socket) if n.startswith(prefix))


socket_families = socket_constants('AF_')
socket_types = socket_constants('SOCK_')

app = Flask(__name__)
app.config.from_envvar("PSDASH_CONFIG", silent=True)

app_url_prefix = app.config.get("PSDASH_URL_PREFIX")
if app_url_prefix:
    app_url_prefix = "/" + app_url_prefix.strip("/")

psdashapp = Blueprint(
    "psdash",
    __name__,
    url_prefix=app_url_prefix,
    static_folder="static"
)

# If the secret key is not read from the config just set it to something.
if not app.secret_key:
    app.secret_key = "whatisthissourcery"


allowed_remote_addrs = []


# Patch the built-in, but not working, filesizeformat filter for now.
# See https://github.com/mitsuhiko/jinja2/pull/59 for more info.
@app.template_filter()
def filesizeformat(value, binary=False):
    """Format the value like a 'human-readable' file size (i.e. 13 kB,
    4.1 MB, 102 Bytes, etc).  Per default decimal prefixes are used (Mega,
    Giga, etc.), if the second parameter is set to `True` the binary
    prefixes are used (Mebi, Gibi).
    """
    bytes = float(value)
    base = binary and 1024 or 1000
    prefixes = [
        (binary and 'KiB' or 'kB'),
        (binary and 'MiB' or 'MB'),
        (binary and 'GiB' or 'GB'),
        (binary and 'TiB' or 'TB'),
        (binary and 'PiB' or 'PB'),
        (binary and 'EiB' or 'EB'),
        (binary and 'ZiB' or 'ZB'),
        (binary and 'YiB' or 'YB')
    ]
    if bytes == 1:
        return '1 Byte'
    elif bytes < base:
        return '%d Bytes' % bytes
    else:
        for i, prefix in enumerate(prefixes):
            unit = base ** (i + 2)
            if bytes < unit:
                return '%.1f %s' % ((base * bytes / unit), prefix)
        return '%.1f %s' % ((base * bytes / unit), prefix)


@app.before_first_request
def load_allowed_remote_addrs():
    addrs = app.config.get("PSDASH_ALLOWED_REMOTE_ADDRESSES")
    if addrs:
        app.logger.info("Setting up allowed remote addresses list.")
        for addr in addrs.split(","):
            allowed_remote_addrs.append(addr.strip())


@app.before_request
def check_access():
    if allowed_remote_addrs:
        if request.remote_addr not in allowed_remote_addrs:
            app.logger.info(
                "Returning 401 for client %s as address is not in allowed addresses.",
                request.remote_addr
            )
            app.logger.debug("Allowed addresses: %s", allowed_remote_addrs)
            return "Access denied", 401

    username = app.config.get("PSDASH_AUTH_USERNAME")
    password = app.config.get("PSDASH_AUTH_PASSWORD")
    if username and password:
        auth = request.authorization
        if not auth or auth.username != username or auth.password != password:
            return Response(
                "Access deined",
                401,
                {'WWW-Authenticate': 'Basic realm="psDash login required"'}
            )


@app.before_request
def setup_client_id():
    if "client_id" not in session:
        client_id = uuid.uuid4()
        app.logger.debug("Creating id for client: %s", client_id)
        session["client_id"] = client_id


@psdashapp.errorhandler(404)
def page_not_found(e):
    app.logger.debug("Client tried to load an unknown route: %s", e)
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="psdash %s - system information web dashboard" % "0.3.0"
    )
    parser.add_argument(
        "-l", "--log",
        action="append",
        dest="logs",
        default=[],
        metavar="path",
        help="log files to make available for psdash. Patterns (e.g. /var/log/**/*.log) are supported. "
             "This option can be used multiple times."
    )
    parser.add_argument(
        "-b", "--bind",
        action="store",
        dest="bind_host",
        default="0.0.0.0",
        metavar="host",
        help="host to bind to. Defaults to 0.0.0.0 (all interfaces)."
    )
    parser.add_argument(
        "-p", "--port",
        action="store",
        type=int,
        dest="port",
        default=5000,
        metavar="port",
        help="port to listen on. Defaults to 5000."
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        dest="debug",
        help="enables debug mode."
    )

    return parser.parse_args()


def start_background_worker(args, sleep_time=3):
    def work():
        update_logs_interval = 60
        i = update_logs_interval
        while True:
            net_io_counters.update()

            # update the list of available logs every minute
            if update_logs_interval <= 0:
                logs.add_patterns(args.logs)
                i = update_logs_interval
            i -= sleep_time

            time.sleep(sleep_time)

    t = threading.Thread(target=work)
    t.daemon = True
    t.start()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s"
    )

    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def enable_verbose_logging():
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logger.setLevel(logging.DEBUG)


def main():
    setup_logging()

    logger.info("Starting psdash v0.3.0")

    # This set locale to the user default (usually controlled by the LANG env var)
    locale.setlocale(locale.LC_ALL, "")

    args = parse_args()
    if args.debug:
        enable_verbose_logging()

    logs.add_patterns(args.logs)
    start_background_worker(args)

    logger.info("Listening on %s:%s", args.bind_host, args.port)

    app.register_blueprint(psdashapp)

    app.run(
        host=args.bind_host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )


if __name__ == '__main__':
    main()
