"""A tiny local Flask app used only for tests/manual scripts (no internet needed)."""
from flask import Flask, jsonify, request

app = Flask(__name__)
_counter = {"n": 0}


@app.route("/ping")
def ping():
    return jsonify(status="ok")


@app.route("/echo", methods=["POST"])
def echo():
    return jsonify(received=request.get_json(silent=True) or {})


@app.route("/counter")
def counter():
    _counter["n"] += 1
    return jsonify(count=_counter["n"])


@app.route("/slow")
def slow():
    import time

    time.sleep(0.05)
    return jsonify(status="slow-ok")


@app.route("/fail")
def fail():
    return jsonify(error="boom"), 500


def run(port: int = 8931):
    app.run(port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
