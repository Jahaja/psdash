# coding=utf-8

from flask import Flask, render_template, redirect
import psutil
app = Flask(__name__)


@app.route("/")
def index():
    return redirect("/processes")

@app.route("/processes")
@app.route("/processes/<sort>")
def processes(sort="pid"):
    return render_template("processes.html", processes=psutil.process_iter())


if __name__ == '__main__':
    app.run(debug=True)
