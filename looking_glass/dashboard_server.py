from __future__ import annotations

import json
import os
import threading
import queue
import subprocess
import time
from pathlib import Path
from typing import Iterator

from flask import Flask, Response, request, send_from_directory, jsonify


ROOT = Path(__file__).resolve().parent.parent
DASH_DIR = ROOT / "dashboard"
OUT_JSON = ROOT / "out" / "test_summary.json"

app = Flask(__name__, static_folder=str(DASH_DIR))

_event_q: "queue.Queue[str]" = queue.Queue()
_run_lock = threading.Lock()
_is_running = False


def _sse_format(data: str, event: str | None = None) -> str:
    # Ensure each line is prefixed with 'data: '
    lines = data.splitlines() or [data]
    payload = "".join(["data: " + ln + "\n" for ln in lines])
    if event:
        return f"event: {event}\n" + payload + "\n"
    return payload + "\n"


def _publisher() -> Iterator[bytes]:
    # Keepalive to prevent proxies from closing
    yield _sse_format(json.dumps({"msg": "connected"})).encode("utf-8")
    while True:
        try:
            line = _event_q.get(timeout=10.0)
            yield line.encode("utf-8")
        except queue.Empty:
            # heartbeat (quiet, client ignores in log)
            yield _sse_format(json.dumps({"ping": time.time()})).encode("utf-8")


@app.get("/api/events")
def sse_events():
    return Response(_publisher(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})


def _run_test_worker(args: list[str]):
    global _is_running
    try:
        cmd = ["python", "examples/test.py"] + args
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        _event_q.put(_sse_format(json.dumps({"msg": "started", "cmd": " ".join(cmd)})))
        assert proc.stdout is not None
        for line in proc.stdout:
            _event_q.put(_sse_format(json.dumps({"log": line.rstrip()})))
        proc.wait()
        # When finished, emit final JSON if present
        if OUT_JSON.exists():
            try:
                data = OUT_JSON.read_text(encoding="utf-8")
                # Also send a 'done' event with JSON payload
                _event_q.put(_sse_format(data, event="done"))
            except Exception as e:
                _event_q.put(_sse_format(json.dumps({"error": str(e)})))
        else:
            _event_q.put(_sse_format(json.dumps({"warn": "no JSON output found"})))
    except Exception as e:
        _event_q.put(_sse_format(json.dumps({"error": str(e)})))
    finally:
        _is_running = False


@app.get("/api/run")
def api_run():
    global _is_running
    with _run_lock:
        if _is_running:
            return jsonify({"status": "busy"}), 409
        _is_running = True
    # Build args from query
    trials = request.args.get("trials", "300")
    seed = request.args.get("seed", "123")
    vote3 = request.args.get("vote3", "1")
    autotune = request.args.get("autotune", "1")
    sensitivity = request.args.get("sensitivity", "0")
    base_window = request.args.get("base_window_ns", "10.0")
    neighbor_ct = request.args.get("neighbor_ct", "0")
    path_b_depth = request.args.get("path_b_depth", "0")
    path_b_sweep = request.args.get("path_b_sweep", "0")
    path_b_analog_depth = request.args.get("path_b_analog_depth", None)
    args = ["--trials", str(trials), "--seed", str(seed), "--json", str(OUT_JSON)]
    if vote3 in ("1", "true", "True"): args.append("--vote3")
    if autotune in ("1", "true", "True"): args.append("--autotune")
    if sensitivity in ("1", "true", "True"): args.append("--sensitivity")
    if neighbor_ct in ("1", "true", "True"): args.append("--neighbor-ct")
    args += ["--base-window-ns", str(base_window)]
    if str(path_b_depth) not in ("0", "false", "False", "", None): args += ["--path-b-depth", str(path_b_depth)]
    if str(path_b_sweep) in ("1", "true", "True"): args.append("--path-b-sweep")
    if path_b_analog_depth not in (None, "", "-1"): args += ["--path-b-analog-depth", str(path_b_analog_depth)]
    threading.Thread(target=_run_test_worker, args=(args,), daemon=True).start()
    return jsonify({"status": "started"})


@app.get("/")
def index():
    return send_from_directory(str(DASH_DIR), "index.html")


@app.get("/dashboard/<path:path>")
def static_files(path: str):
    return send_from_directory(str(DASH_DIR), path)


def main():
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

