# coding=utf-8
from flask import Flask, render_template, redirect, flash
import psutil
from datetime import datetime

app = Flask(__name__)
app.secret_key = "whatisthissourcery"


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="Page not found."), 404


@app.errorhandler(psutil._error.AccessDenied)
def access_denied(e):
    return render_template("error.html", error="Access denied to %s (pid %d)." % (e.name, e.pid)), 401


@app.route("/")
def index():
    return redirect("/processes")


@app.route("/processes", defaults={"sort" : "cpu", "order": "desc"})
@app.route("/processes/<string:sort>")
@app.route("/processes/<string:sort>/<string:order>")
def processes(sort="pid", order="asc"):
    procs = []
    for p in psutil.process_iter():
        rss, vms = p.get_memory_info()

        # format created date
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

    procs.sort(key=lambda p: p.get(sort), reverse=True if order != "asc" else False)

    return render_template("processes.html", processes=procs, sort=sort, order=order)

@app.route("/process/<int:pid>/limits")
def process_limits(pid):
    if not psutil.pid_exists(pid):
        errmsg = "No process with pid %d was found." % pid
        return render_template("error.html", error=errmsg), 404

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
    if not psutil.pid_exists(pid):
        errmsg = "No process with pid %d was found." % pid
        return render_template("error.html", error=errmsg), 404

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

    return render_template("process/%s.html" % section, process=psutil.Process(pid), section=section)


if __name__ == '__main__':
    app.run(debug=True)
