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
    path_b_depth = request.args.get("path_b_depth", "5")
    path_b_sweep = request.args.get("path_b_sweep", "1")
    path_b_analog_depth = request.args.get("path_b_analog_depth", None)
    path_b_analog = request.args.get("path_b_analog", "1")
    path_b = request.args.get("path_b", "1")
    cold_input = request.args.get("cold_input", "1")
    adaptive_input = request.args.get("adaptive_input", "1")
    adaptive_max_frames = request.args.get("adaptive_max_frames", "3")
    adaptive_margin_mV = request.args.get("adaptive_margin_mV", "0.5")
    args = ["--trials", str(trials), "--seed", str(seed), "--json", str(OUT_JSON)]
    if vote3 in ("1", "true", "True"): args.append("--vote3")
    if autotune in ("1", "true", "True"): args.append("--autotune")
    if sensitivity in ("1", "true", "True"): args.append("--sensitivity")
    if neighbor_ct in ("1", "true", "True"): args.append("--neighbor-ct")
    args += ["--base-window-ns", str(base_window)]
    if str(path_b_depth) not in ("0", "false", "False", "", None): args += ["--path-b-depth", str(path_b_depth)]
    if str(path_b_sweep) in ("1", "true", "True"): args.append("--path-b-sweep")
    if path_b_analog_depth not in (None, "", "-1"): args += ["--path-b-analog-depth", str(path_b_analog_depth)]
    if str(path_b_analog) in ("0", "false", "False"): args.append("--no-path-b-analog")
    if str(path_b) in ("0", "false", "False"): args.append("--no-path-b")
    if str(cold_input) in ("0", "false", "False"): args.append("--no-cold-input")
    if adaptive_input in ("1", "true", "True"): args.append("--adaptive-input")
    args += ["--adaptive-max-frames", str(adaptive_max_frames), "--adaptive-margin-mV", str(adaptive_margin_mV)]
    threading.Thread(target=_run_test_worker, args=(args,), daemon=True).start()
    return jsonify({"status": "started"})


@app.get("/")
def index():
    return send_from_directory(str(DASH_DIR), "index.html")


@app.get("/api/run_matrix")
def api_run_matrix():
    """Run a small matrix of runs sequentially and emit a 'done' event per run.

    Query params (CSV lists accepted):
      - inputs: comma list from {digital,cold}
      - sensitivities: comma list from {0,1}
      - outputs: comma list from {path_a,path_b_analog}
      - windows: optional comma list of base_window_ns values
      - trials, seed, path_b_analog_depth
    """
    global _is_running
    with _run_lock:
        if _is_running:
            return jsonify({"status": "busy"}), 409
        _is_running = True
    try:
        import itertools, uuid
        inputs_csv = request.args.get("inputs", "digital,cold")
        sens_csv = request.args.get("sensitivities", "0,1")
        outputs_csv = request.args.get("outputs", "path_a,path_b_analog")
        windows_csv = request.args.get("windows", "")
        trials = request.args.get("trials", "300")
        seed = request.args.get("seed", "123")
        pba_depth = request.args.get("path_b_analog_depth", "5")
        pba_depths_csv = request.args.get("path_b_analog_depths", "")
        autotune = request.args.get("autotune", "0")

        inputs = [s.strip() for s in inputs_csv.split(',') if s.strip()]
        sens_list = [s.strip() for s in sens_csv.split(',') if s.strip()]
        outputs = [s.strip() for s in outputs_csv.split(',') if s.strip()]
        windows = [w.strip() for w in windows_csv.split(',') if w.strip()]
        depths = [d.strip() for d in pba_depths_csv.split(',') if d.strip()]
        if not windows:
            windows = [request.args.get("base_window_ns", "20.0")]
        if not depths:
            depths = [pba_depth]

        combos = list(itertools.product(inputs, sens_list, outputs, windows, depths))
        # soft cap
        if len(combos) > 64:
            return jsonify({"error": "too many combinations", "count": len(combos)}), 400

        for (inp, sens, outp, win, depth) in combos:
            run_id = str(uuid.uuid4())
            out_path = ROOT / "out" / f"test_summary_{run_id}.json"
            cmd = ["python", "examples/test.py",
                   "--trials", str(trials), "--seed", str(seed), "--json", str(out_path),
                   "--base-window-ns", str(win)]
            # sensitivity
            if sens in ("1", "true", "True"): cmd.append("--sensitivity")
            # input
            if inp == "digital":
                cmd.append("--no-cold-input")
            # outputs / path selection
            if outp == "path_a":
                cmd += ["--no-path-b", "--no-path-b-analog"]
                cmd += ["--components-mode", "path_a"]
            elif outp == "path_b_analog":
                cmd += ["--path-b-analog-depth", str(depth), "--no-path-b"]
                cmd += ["--components-mode", "path_b_analog"]
            # components baseline for cold input
            if inp == "cold" and outp != "path_b_analog":
                cmd += ["--components-mode", "cold"]
            # optional autotune for matrix runs
            if autotune in ("1", "true", "True"):
                cmd.append("--autotune")

            proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            _event_q.put(_sse_format(json.dumps({"msg": "started", "cmd": " ".join(cmd), "run_id": run_id})))
            assert proc.stdout is not None
            for line in proc.stdout:
                _event_q.put(_sse_format(json.dumps({"log": line.rstrip(), "run_id": run_id})))
            proc.wait()
            try:
                if out_path.exists():
                    data = json.loads(out_path.read_text(encoding="utf-8"))
                    # annotate and emit
                    data["__run_id"] = run_id
                    data["__label"] = {
                        "input": inp,
                        "sensitivity": bool(sens in ("1","true","True")),
                        "output": outp,
                        "window_ns": float(win),
                        "analog_depth": int(depth) if str(depth).isdigit() else depth,
                    }
                    _event_q.put(_sse_format(json.dumps(data), event="done"))
                else:
                    _event_q.put(_sse_format(json.dumps({"warn": "no JSON output found", "run_id": run_id})))
            except Exception as e:
                _event_q.put(_sse_format(json.dumps({"error": str(e), "run_id": run_id})))
        return jsonify({"status": "started", "runs": len(combos)})
    finally:
        _is_running = False


@app.get("/dashboard/<path:path>")
def static_files(path: str):
    return send_from_directory(str(DASH_DIR), path)


def main():
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

