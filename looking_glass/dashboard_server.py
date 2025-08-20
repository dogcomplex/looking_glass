from __future__ import annotations

import json
import time
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
HISTORY_FILE = ROOT / "out" / "runs_history.jsonl"

app = Flask(__name__, static_folder=str(DASH_DIR))

_event_q: "queue.Queue[str]" = queue.Queue()
_run_lock = threading.Lock()
_is_running = False
_pending_jobs: "queue.Queue[list]" = queue.Queue()


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
                # Persist to history
                try:
                    import json as _json, time as _time
                    obj = _json.loads(data)
                    obj["__time"] = _time.time()
                    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
                        hf.write(_json.dumps(obj) + "\n")
                except Exception:
                    pass
            except Exception as e:
                _event_q.put(_sse_format(json.dumps({"error": str(e)})))
        else:
            _event_q.put(_sse_format(json.dumps({"warn": "no JSON output found"})))
    except Exception as e:
        _event_q.put(_sse_format(json.dumps({"error": str(e)})))
    finally:
        _is_running = False


def _process_joblist():
    global _is_running
    try:
        while True:
            try:
                jobs_list = _pending_jobs.get(timeout=0.5)
            except queue.Empty:
                break
            try:
                for (cmd, run_id, out_path, inp, sens, outp, win, depth, ep, op, sp, tp, cp, cap, clp, thp, vres) in jobs_list:
                    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    _event_q.put(_sse_format(json.dumps({"msg": "started", "cmd": " ".join(cmd), "run_id": run_id})))
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        _event_q.put(_sse_format(json.dumps({"log": line.rstrip(), "run_id": run_id})))
                    proc.wait()
                    try:
                        if out_path.exists():
                            data = json.loads(out_path.read_text(encoding="utf-8"))
                            data["__run_id"] = run_id
                            data["__label"] = {
                                "input": inp,
                                "sensitivity": bool(sens in ("1","true","True")),
                                "output": outp,
                                "window_ns": float(win),
                                "analog_depth": int(depth) if str(depth).isdigit() else depth,
                                "packs": {
                                    "emitter": ep,
                                    "optics": op,
                                    "sensor": sp,
                                    "tia": tp,
                                    "comparator": cp,
                                    "camera": cap,
                                    "clock": clp,
                                    "thermal": thp,
                                }
                            }
                            data["__preflight"] = vres
                            _event_q.put(_sse_format(json.dumps(data), event="done"))
                            try:
                                data["__time"] = time.time()
                                HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                                with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
                                    hf.write(json.dumps(data) + "\n")
                            except Exception:
                                pass
                        else:
                            _event_q.put(_sse_format(json.dumps({"warn": "no JSON output found", "run_id": run_id})))
                    except Exception as e:
                        _event_q.put(_sse_format(json.dumps({"error": str(e), "run_id": run_id})))
            finally:
                _pending_jobs.task_done()
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
    # Optional pack overrides (single run)
    for key in ("emitter_pack","optics_pack","sensor_pack","tia_pack","comparator_pack","camera_pack","clock_pack","thermal_pack"):
        path = request.args.get(key)
        if path:
            args += [f"--{key.replace('_','-')}", str(path)]
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
@app.get("/api/packs")
def api_packs_list():
    """List available vendor packs per component under configs/packs/vendors/*"""
    base = ROOT / "configs" / "packs" / "vendors"
    root = ROOT / "configs" / "packs"
    out: dict[str, list[str]] = {}
    try:
        # helper to prepend root *_typ.yaml to each category if present
        def _prepend_typical(cat: str, lst: list[str]):
            try:
                for p in root.glob(f"{cat[:-1]}_*.yaml") if cat.endswith('s') else []:
                    # only pick *_typ.yaml
                    if str(p.name).endswith("_typ.yaml"):
                        rel = str(p.relative_to(ROOT))
                        if rel not in lst:
                            lst.insert(0, rel)
            except Exception:
                pass
        for comp_dir in base.iterdir():
            if comp_dir.is_dir():
                files = [str(p.relative_to(ROOT)) for p in comp_dir.glob("*.yaml")]
                if files:
                    files = sorted(files)
                    _prepend_typical(comp_dir.name, files)
                    out[comp_dir.name] = files
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(out)


@app.get("/api/history")
def api_history():
    """Return recent run history (JSONL) with optional filters.

    Query params:
      - limit: max records (default 50)
      - since: unix timestamp lower bound
      - pack_contains: substring filter against any pack path
      - status: preflight status (ok|warn|fail)
    """
    def _to_int(s, d):
        try:
            return int(s)
        except Exception:
            return d
    def _to_float(s, d):
        try:
            return float(s)
        except Exception:
            return d
    limit = _to_int(request.args.get("limit", "50"), 50)
    since = _to_float(request.args.get("since", "0"), 0.0)
    pack_contains = request.args.get("pack_contains", "")
    status = request.args.get("status", "")
    # Per-component exact pack filters (relative path match)
    pack_filters = {
        "emitter": request.args.get("emitter", ""),
        "optics": request.args.get("optics", ""),
        "sensor": request.args.get("sensor", ""),
        "tia": request.args.get("tia", ""),
        "comparator": request.args.get("comparator", ""),
        "camera": request.args.get("camera", ""),
        "clock": request.args.get("clock", ""),
        "thermal": request.args.get("thermal", ""),
    }
    rows = []
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if since and float(obj.get("__time", 0.0)) < since:
                            continue
                        if pack_contains:
                            packs = (((obj.get("__label") or {}).get("packs")) or {})
                            joined = ",".join([str(v) for v in packs.values() if v])
                            if pack_contains not in joined:
                                continue
                        # component-specific exact matches
                        if any(pack_filters[k] and (str(((obj.get("__label") or {}).get("packs") or {}).get(k, "")) != pack_filters[k]) for k in pack_filters.keys()):
                            continue
                        if status:
                            pref = (obj.get("__preflight") or {}).get("status", "")
                            if pref != status:
                                continue
                        rows.append(obj)
                    except Exception:
                        continue
        rows = rows[-limit:]
        # Optional CSV export of raw rows
        if request.args.get("format") == "csv":
            import io, csv
            buf = io.StringIO()
            # Flatten typical fields for analysis
            fieldnames = [
                "time_iso","run_id","input","sensitivity","output","window_ns","analog_depth","preflight_status","preflight_reasons",
                "baseline_p50_ber","path_a_p50_ber","path_b_p50_ber","path_b_analog_p50_ber",
                "emitter_pack","optics_pack","sensor_pack","tia_pack","comparator_pack","camera_pack","clock_pack","thermal_pack",
            ]
            w = csv.DictWriter(buf, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                label = (r.get("__label") or {})
                packs = (label.get("packs") or {})
                pre = (r.get("__preflight") or {})
                iso = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(r.get("__time", 0))) if r.get("__time") else ""
                row = {
                    "time_iso": iso,
                    "run_id": r.get("__run_id"),
                    "input": label.get("input"),
                    "sensitivity": label.get("sensitivity"),
                    "output": label.get("output"),
                    "window_ns": label.get("window_ns"),
                    "analog_depth": label.get("analog_depth"),
                    "preflight_status": pre.get("status"),
                    "preflight_reasons": "; ".join(pre.get("reasons", [])),
                    "baseline_p50_ber": (r.get("baseline") or {}).get("p50_ber"),
                    "path_a_p50_ber": (r.get("path_a") or {}).get("p50_ber"),
                    "path_b_p50_ber": (r.get("path_b") or {}).get("p50_ber"),
                    "path_b_analog_p50_ber": (r.get("path_b") or {}).get("analog_p50_ber"),
                    "emitter_pack": packs.get("emitter"),
                    "optics_pack": packs.get("optics"),
                    "sensor_pack": packs.get("sensor"),
                    "tia_pack": packs.get("tia"),
                    "comparator_pack": packs.get("comparator"),
                    "camera_pack": packs.get("camera"),
                    "clock_pack": packs.get("clock"),
                    "thermal_pack": packs.get("thermal"),
                }
                w.writerow(row)
            return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=history_all_runs.csv"})
        return jsonify({"count": len(rows), "rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/history_best")
def api_history_best():
    """Aggregate best-of across history, grouped by selected pack keys.

    Query params:
      - group_by: CSV from {emitter,optics,sensor,tia,comparator,camera,clock,thermal} (default: all)
      - since, status, limit, pack filters: same as /api/history
      - path: which BER to optimize: primary|path_a|path_b_analog (default: primary)
    """
    # Reuse loader from api_history
    try:
        # Load rows with existing filters (but large limit by default)
        args = request.args.to_dict()
        args.setdefault("limit", "10000")
        with app.test_request_context(query_string=args):
            hist = api_history()
        if isinstance(hist, tuple):
            return hist
        data = hist.get_json() if hasattr(hist, 'get_json') else hist
        rows = data.get("rows", [])
        gb_csv = request.args.get("group_by", "emitter,optics,sensor,tia,comparator,camera,clock,thermal")
        keys = [k.strip() for k in gb_csv.split(',') if k.strip()]
        which = request.args.get("path", "primary")

        def primary_ber(r):
            try:
                out = (r.get("__label") or {}).get("output")
                if which == "path_a":
                    return r.get("path_a", {}).get("p50_ber") or r.get("baseline", {}).get("p50_ber")
                if which == "path_b_analog":
                    return (r.get("path_b", {}).get("analog_p50_ber")
                            or r.get("path_b", {}).get("p50_ber")
                            or r.get("baseline", {}).get("p50_ber"))
                # primary: follow label output if present
                if out == "path_a":
                    return r.get("path_a", {}).get("p50_ber") or r.get("baseline", {}).get("p50_ber")
                if out == "path_b_analog":
                    return (r.get("path_b", {}).get("analog_p50_ber")
                            or r.get("path_b", {}).get("p50_ber")
                            or r.get("baseline", {}).get("p50_ber"))
                return r.get("baseline", {}).get("p50_ber")
            except Exception:
                return None

        groups = {}
        for r in rows:
            packs = ((r.get("__label") or {}).get("packs") or {})
            group_vals = tuple(packs.get(k) for k in keys)
            if group_vals not in groups:
                groups[group_vals] = {
                    "packs": {k: packs.get(k) for k in keys},
                    "n": 0,
                    "best_p50_ber": None,
                    "best_run_id": None,
                    "best_time": None,
                }
            g = groups[group_vals]
            g["n"] += 1
            ber = primary_ber(r)
            try:
                if ber is not None and (g["best_p50_ber"] is None or float(ber) < float(g["best_p50_ber"])):
                    g["best_p50_ber"] = float(ber)
                    g["best_run_id"] = r.get("__run_id")
                    g["best_time"] = r.get("__time")
            except Exception:
                pass

        # Format as list
        out = []
        for gv, info in groups.items():
            out.append({"group": list(gv), **info})
        # Sorting: best BER asc, then n desc
        out.sort(key=lambda x: (float('inf') if x["best_p50_ber"] is None else x["best_p50_ber"], -x["n"]))
        # CSV export if requested
        if request.args.get("format") == "csv":
            import io, csv
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["best_p50_ber","n","best_run_id","best_time"] + keys)
            writer.writeheader()
            for row in out:
                d = {"best_p50_ber": row.get("best_p50_ber"), "n": row.get("n"), "best_run_id": row.get("best_run_id"), "best_time": row.get("best_time")}
                for k in keys:
                    d[k] = row.get("packs", {}).get(k)
                writer.writerow(d)
            return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=history_best.csv"})
        return jsonify({"count": len(out), "groups": out, "group_by": keys})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



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
        # pack lists per component (CSV of relative paths)
        packs = {
            "emitter_pack": request.args.get("emitter_packs", ""),
            "optics_pack": request.args.get("optics_packs", ""),
            "sensor_pack": request.args.get("sensor_packs", ""),
            "tia_pack": request.args.get("tia_packs", ""),
            "comparator_pack": request.args.get("comparator_packs", ""),
            "camera_pack": request.args.get("camera_packs", ""),
            "clock_pack": request.args.get("clock_packs", ""),
            "thermal_pack": request.args.get("thermal_packs", ""),
        }

        inputs = [s.strip() for s in inputs_csv.split(',') if s.strip()]
        sens_list = [s.strip() for s in sens_csv.split(',') if s.strip()]
        outputs = [s.strip() for s in outputs_csv.split(',') if s.strip()]
        windows = [w.strip() for w in windows_csv.split(',') if w.strip()]
        depths = [d.strip() for d in pba_depths_csv.split(',') if d.strip()]
        if not windows:
            windows = [request.args.get("base_window_ns", "20.0")]
        if not depths:
            depths = [pba_depth]

        # Build pack choices (empty list -> [None])
        def _parse(csv):
            items = [s.strip() for s in csv.split(',') if s.strip()]
            return items if items else [None]
        pack_lists = {k: _parse(v) for k, v in packs.items()}
        # Preload pack YAMLs once for preflight
        import importlib, pathlib
        def _load_yaml(path: str | None):
            if not path:
                return {}
            text = (ROOT / path).read_text(encoding="utf-8") if not path.startswith("/") else pathlib.Path(path).read_text(encoding="utf-8")
            try:
                yaml_mod = importlib.import_module("yaml")
                return yaml_mod.safe_load(text) or {}
            except ModuleNotFoundError:
                return {}
        pack_data = {}
        for lst in pack_lists.values():
            for p in lst:
                if p and p not in pack_data:
                    try:
                        pack_data[p] = _load_yaml(p)
                    except Exception:
                        pack_data[p] = {}

        # Build combos with preflight pruning
        from .preflight import validate_combo
        combos = []
        pruned = 0
        for (inp, sens, outp, win, depth) in itertools.product(inputs, sens_list, outputs, windows, depths):
            for ep in pack_lists["emitter_pack"]:
                for op in pack_lists["optics_pack"]:
                    for sp in pack_lists["sensor_pack"]:
                        for tp in pack_lists["tia_pack"]:
                            for cp in pack_lists["comparator_pack"]:
                                for cap in pack_lists["camera_pack"]:
                                    for clp in pack_lists["clock_pack"]:
                                        for thp in pack_lists["thermal_pack"]:
                                            packs_dict = {
                                                "emitter": pack_data.get(ep, {}),
                                                "optics": pack_data.get(op, {}),
                                                "sensor": pack_data.get(sp, {}),
                                                "tia": pack_data.get(tp, {}),
                                                "comparator": pack_data.get(cp, {}),
                                                "camera": pack_data.get(cap, {}),
                                                "clock": pack_data.get(clp, {}),
                                                "thermal": pack_data.get(thp, {}),
                                            }
                                            v = validate_combo(packs_dict, window_ns=float(win))
                                            if v.get("status") == "fail":
                                                pruned += 1
                                                continue
                                            combos.append((inp, sens, outp, win, depth, ep, op, sp, tp, cp, cap, clp, thp, v))
        # soft cap (configurable via query)
        cap = int(request.args.get("cap", "96"))
        if len(combos) > cap:
            return jsonify({"error": "too many combinations", "count": len(combos), "cap": cap}), 400

        # Prepare jobs
        jobs = []
        for (inp, sens, outp, win, depth, ep, op, sp, tp, cp, cap, clp, thp, vres) in combos:
            run_id = str(uuid.uuid4())
            out_path = ROOT / "out" / f"test_summary_{run_id}.json"
            cmd = ["python", "examples/test.py",
                   "--trials", str(trials), "--seed", str(seed), "--json", str(out_path),
                   "--base-window-ns", str(win)]
            if sens in ("1", "true", "True"): cmd.append("--sensitivity")
            if inp == "digital":
                cmd.append("--no-cold-input")
            if outp == "path_a":
                cmd += ["--no-path-b", "--no-path-b-analog", "--components-mode", "path_a"]
            elif outp == "path_b_analog":
                cmd += ["--path-b-analog-depth", str(depth), "--no-path-b", "--components-mode", "path_b_analog"]
            if inp == "cold" and outp != "path_b_analog":
                cmd += ["--components-mode", "cold"]
            if autotune in ("1", "true", "True"):
                cmd.append("--autotune")
            if ep: cmd += ["--emitter-pack", str(ep)]
            if op: cmd += ["--optics-pack", str(op)]
            if sp: cmd += ["--sensor-pack", str(sp)]
            if tp: cmd += ["--tia-pack", str(tp)]
            if cp: cmd += ["--comparator-pack", str(cp)]
            if cap: cmd += ["--camera-pack", str(cap)]
            if clp: cmd += ["--clock-pack", str(clp)]
            if thp: cmd += ["--thermal-pack", str(thp)]
            jobs.append((cmd, run_id, out_path, inp, sens, outp, win, depth, ep, op, sp, tp, cp, cap, clp, thp, vres))

        def _worker(jobs_list):
            global _is_running
            try:
                for (cmd, run_id, out_path, inp, sens, outp, win, depth, ep, op, sp, tp, cp, cap, clp, thp, vres) in jobs_list:
                    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    _event_q.put(_sse_format(json.dumps({"msg": "started", "cmd": " ".join(cmd), "run_id": run_id})))
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        _event_q.put(_sse_format(json.dumps({"log": line.rstrip(), "run_id": run_id})))
                    proc.wait()
                    try:
                        if out_path.exists():
                            data = json.loads(out_path.read_text(encoding="utf-8"))
                            data["__run_id"] = run_id
                            data["__label"] = {
                                "input": inp,
                                "sensitivity": bool(sens in ("1","true","True")),
                                "output": outp,
                                "window_ns": float(win),
                                "analog_depth": int(depth) if str(depth).isdigit() else depth,
                                "packs": {
                                    "emitter": ep,
                                    "optics": op,
                                    "sensor": sp,
                                    "tia": tp,
                                    "comparator": cp,
                                    "camera": cap,
                                    "clock": clp,
                                    "thermal": thp,
                                }
                            }
                            data["__preflight"] = vres
                            _event_q.put(_sse_format(json.dumps(data), event="done"))
                            try:
                                data["__time"] = time.time()
                                HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                                with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
                                    hf.write(json.dumps(data) + "\n")
                            except Exception:
                                pass
                        else:
                            _event_q.put(_sse_format(json.dumps({"warn": "no JSON output found", "run_id": run_id})))
                    except Exception as e:
                        _event_q.put(_sse_format(json.dumps({"error": str(e), "run_id": run_id})))
            finally:
                _is_running = False

        # Enqueue and start processor
        _pending_jobs.put(jobs)
        threading.Thread(target=_process_joblist, daemon=True).start()
        return jsonify({"status": "started", "runs": len(jobs), "pruned": pruned})
    finally:
        pass


@app.get("/dashboard/<path:path>")
def static_files(path: str):
    return send_from_directory(str(DASH_DIR), path)


def main():
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

