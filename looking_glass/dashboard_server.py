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
_seq_counter = 0


def _sse_format(data: str, event: str | None = None) -> str:
    # Ensure each line is prefixed with 'data: '
    lines = data.splitlines() or [data]
    payload = "".join(["data: " + ln + "\n" for ln in lines])
    if event:
        return f"event: {event}\n" + payload + "\n"
    return payload + "\n"
def _basename(p: str | None) -> str:
    if not p:
        return "typ"
    try:
        return Path(p).stem
    except Exception:
        return str(p)


def _build_run_name(label: dict) -> str:
    try:
        packs = (label.get("packs") or {})
        parts = [
            label.get("input") or "",
            label.get("output") or "",
            f"w{int(label.get('window_ns', 0))}ns" if label.get("window_ns") is not None else "",
            f"d{label.get('analog_depth')}" if label.get("analog_depth") else "",
            _basename(packs.get("emitter")),
            _basename(packs.get("tia")),
            _basename(packs.get("comparator")),
            _basename(packs.get("optics")),
            _basename(packs.get("sensor")),
            _basename(packs.get("camera")),
            _basename(packs.get("clock")),
        ]
        return " / ".join([s for s in parts if s])
    except Exception:
        return "run"


def _persist_history(obj: dict) -> None:
    global _seq_counter
    try:
        obj["__time"] = time.time()
        obj["__time_ms"] = int(time.time_ns() // 1_000_000)
        _seq_counter += 1
        obj["__seq"] = _seq_counter
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
            hf.write(json.dumps(obj) + "\n")
    except Exception:
        pass



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
        # Batch stdout lines to reduce SSE chatter and client memory
        _batch = []
        _B = 80
        for line in proc.stdout:
            _batch.append(line.rstrip())
            if len(_batch) >= _B:
                _event_q.put(_sse_format(json.dumps({"log": "\n".join(_batch)})))
                _batch = []
        if _batch:
            _event_q.put(_sse_format(json.dumps({"log": "\n".join(_batch)})))
        proc.wait()
        # When finished, emit final JSON if present
        if OUT_JSON.exists():
            try:
                data = OUT_JSON.read_text(encoding="utf-8")
                # Also send a 'done' event with JSON payload
                _event_q.put(_sse_format(data, event="done"))
                # Persist to history
                try:
                    import json as _json
                    obj = _json.loads(data)
                    _persist_history(obj)
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
                    # Batch stdout lines to reduce SSE chatter and client memory
                    _batch = []
                    _B = 80
                    for line in proc.stdout:
                        _batch.append(line.rstrip())
                        if len(_batch) >= _B:
                            _event_q.put(_sse_format(json.dumps({"log": "\n".join(_batch), "run_id": run_id})))
                            _batch = []
                    if _batch:
                        _event_q.put(_sse_format(json.dumps({"log": "\n".join(_batch), "run_id": run_id})))
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
                            _persist_history(data)
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
    channels = request.args.get("channels", "")
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
    args = ["--trials", str(trials), "--seed", str(seed), "--json", str(OUT_JSON), "--quiet"]
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
    if channels not in (None, "", "None"): args += ["--channels", str(channels)]
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
        rows = sorted(rows, key=lambda r: (float(r.get("__time", 0.0)), int(r.get("__seq", 0))))[-limit:]
        # Optional CSV export of raw rows
        if request.args.get("format") == "csv":
            import io, csv
            buf = io.StringIO()
            # Build dynamic fieldnames including flattened configs and summaries
            def flat(prefix, obj):
                out = {}
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        out.update(flat(f"{prefix}{k}.", v))
                else:
                    out[prefix[:-1]] = obj
                return out

            # Collect all keys across rows
            keys = set()
            flat_rows = []
            for r in rows:
                label = (r.get("__label") or {})
                packs = (label.get("packs") or {})
                pre = (r.get("__preflight") or {})
                # Include ms for ordering
                ts = float(r.get("__time", 0))
                ms = int(r.get("__time_ms", 0))
                iso = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts)) + (f".{ms%1000:03d}" if ms else "") if ts else ""
                base = {
                    "time_iso": iso,
                    "run_id": r.get("__run_id"),
                    "run_name": _build_run_name(label),
                }
                base.update({
                    "label.input": label.get("input"),
                    "label.sensitivity": label.get("sensitivity"),
                    "label.output": label.get("output"),
                    "label.window_ns": label.get("window_ns"),
                    "label.analog_depth": label.get("analog_depth"),
                })
                base.update(flat("packs.", packs))
                base.update({
                    "preflight.status": pre.get("status"),
                    "preflight.reasons": "; ".join(pre.get("reasons", [])),
                })
                # Attach full summaries
                for block in ("baseline","path_a","path_b","path_b_chain","path_b_sweeps","cold_input","realism","components","window_sweep","rin_sweep","crosstalk_sweep","baseline_calibrated","sensitivity","drift","autotune"):
                    if r.get(block) is not None:
                        base.update(flat(f"{block}.", r.get(block)))
                flat_rows.append(base)
                keys.update(base.keys())

            fieldnames = ["time_iso","run_id","run_name","__seq","__time_ms"] + sorted([k for k in keys if k not in ("time_iso","run_id","run_name","__seq","__time_ms")])
            w = csv.DictWriter(buf, fieldnames=fieldnames)
            w.writeheader()
            for fr in flat_rows:
                out = {k: fr.get(k, "") for k in fieldnames}
                w.writerow(out)
            return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=history_all_runs.csv"})
        return jsonify({"count": len(rows), "rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/history/reset")
def api_history_reset():
    """Clear run history (JSONL) and reset sequence counter."""
    global _seq_counter
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        _seq_counter = 0
        return jsonify({"status": "ok", "reset": True})
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
        inputs_csv = request.args.get("inputs", "digital")
        sens_csv = request.args.get("sensitivity", request.args.get("sensitivities", "0"))
        outputs_csv = request.args.get("outputs", "path_a,path_b_analog")
        windows_csv = request.args.get("windows", "")
        channels_csv = request.args.get("channels", "")
        trials = request.args.get("trials", "300")
        seed = request.args.get("seed", "123")
        pba_depth = request.args.get("path_b_analog_depth", "5")
        pba_depths_csv = request.args.get("path_b_analog_depths", "")
        autotune = request.args.get("autotune", "1")
        vote3_csv = request.args.get("vote3", "1")
        neighbor_csv = request.args.get("neighbor_ct", "0")
        adapt_flag_csv = request.args.get("adaptive_input", "1")
        adapt_max_csv = request.args.get("adaptive_max_frames", "12")
        adapt_margin_csv = request.args.get("adaptive_margin_mV", "0.8")
        light_csv = request.args.get("light_output", "0")
        classifier_csv = request.args.get("classifier", "")
        repeat_csv = request.args.get("repeat", "")
        permute_csv = request.args.get("permute_repeats", "0")
        perm_scheme_csv = request.args.get("permute_scheme", "random")
        # extra flags to mirror preset capabilities
        apply_cal_csv = request.args.get("apply_calibration", "0")
        avg_frames_csv = request.args.get("avg_frames", "1")
        soft_thresh_csv = request.args.get("soft_thresh", "0")
        use_avg_path_a_csv = request.args.get("use_avg_frames_for_path_a", "0")
        apply_auto_csv = request.args.get("apply_autotuned_params", "0")
        lock_ct_csv = request.args.get("lock_optics_ct", "0")
        norm_dv_csv = request.args.get("normalize_dv", "0")
        norm_eps_v = request.args.get("normalize_eps_v", "")
        tune_budget_csv = request.args.get("autotune_budget", "")
        tune_trials_csv = request.args.get("autotune_trials", "")
        use_at_primary_csv = request.args.get("use_autotuned_as_primary", "0")
        fast_csv = request.args.get("fast", "0")
        no_sweeps_csv = request.args.get("no_sweeps", "0")
        no_cal_csv = request.args.get("no_cal", "0")
        no_drift_csv = request.args.get("no_drift", "0")
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
        vote_list = [s.strip() for s in vote3_csv.split(',') if s.strip()]
        neigh_list = [s.strip() for s in neighbor_csv.split(',') if s.strip()]
        adapt_list = [s.strip() for s in adapt_flag_csv.split(',') if s.strip()]
        adapt_max_list = [s.strip() for s in adapt_max_csv.split(',') if s.strip()]
        adapt_margin_list = [s.strip() for s in adapt_margin_csv.split(',') if s.strip()]
        apply_cal_list = [s.strip() for s in apply_cal_csv.split(',') if s.strip()]
        avg_frames_list = [s.strip() for s in avg_frames_csv.split(',') if s.strip()]
        soft_thresh_list = [s.strip() for s in soft_thresh_csv.split(',') if s.strip()]
        use_avg_path_a_list = [s.strip() for s in use_avg_path_a_csv.split(',') if s.strip()]
        apply_auto_list = [s.strip() for s in apply_auto_csv.split(',') if s.strip()]
        lock_ct_list = [s.strip() for s in lock_ct_csv.split(',') if s.strip()]
        fast_list = [s.strip() for s in fast_csv.split(',') if s.strip()]
        no_sweeps_list = [s.strip() for s in no_sweeps_csv.split(',') if s.strip()]
        no_cal_list = [s.strip() for s in no_cal_csv.split(',') if s.strip()]
        no_drift_list = [s.strip() for s in no_drift_csv.split(',') if s.strip()]
        use_at_primary_list = [s.strip() for s in use_at_primary_csv.split(',') if s.strip()]
        light_list = [s.strip() for s in light_csv.split(',') if s.strip()]
        outputs = [s.strip() for s in outputs_csv.split(',') if s.strip()]
        channels_list = [s.strip() for s in channels_csv.split(',') if s.strip()]
        classifier_list = [s.strip() for s in classifier_csv.split(',') if s.strip()]
        repeat_list = [s.strip() for s in repeat_csv.split(',') if s.strip()]
        permute_list = [s.strip() for s in permute_csv.split(',') if s.strip()]
        perm_scheme_list = [s.strip() for s in perm_scheme_csv.split(',') if s.strip()]
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
        for (inp, sens, outp, win, depth, v3, neighb, apc, adf, admx, admr, avf, sth, uap, aap, lct, ff, ns, nc, nd, lo, uatp, cls, rep, prm, ps) in itertools.product(
            inputs, sens_list, outputs, windows, depths, vote_list, neigh_list,
            apply_cal_list or ["0"], adapt_list, adapt_max_list, adapt_margin_list,
            avg_frames_list or ["1"], soft_thresh_list or ["0"], use_avg_path_a_list or ["0"],
            apply_auto_list or ["0"], lock_ct_list or ["0"], fast_list or ["0"],
            no_sweeps_list or ["0"], no_cal_list or ["0"], no_drift_list or ["0"], light_list or ["0"], use_at_primary_list or ["0"],
            (classifier_list or [None]), (repeat_list or [None]), (permute_list or ["0"]), (perm_scheme_list or ["random"]) 
        ):
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
                                            combos.append((inp, sens, outp, win, depth, v3, neighb, apc, adf, admx, admr, avf, sth, uap, aap, lct, ff, ns, nc, nd, lo, uatp, cls, rep, prm, ps, ep, op, sp, tp, cp, cap, clp, thp, v))
        # soft cap (configurable via query)
        cap = int(request.args.get("cap", "96"))
        if len(combos) > cap:
            return jsonify({"error": "too many combinations", "count": len(combos), "cap": cap}), 400

        # Prepare jobs
        jobs = []
        for (inp, sens, outp, win, depth, v3, neighb, apc, adf, admx, admr, avf, sth, uap, aap, lct, ff, ns, nc, nd, lo, uatp, cls, rep, prm, ps, ep, op, sp, tp, cp, cap, clp, thp, vres) in combos:
            run_id = str(uuid.uuid4())
            out_path = ROOT / "out" / f"test_summary_{run_id}.json"
            cmd = ["python", "examples/test.py",
                   "--trials", str(trials), "--seed", str(seed), "--json", str(out_path),
                   "--base-window-ns", str(win), "--quiet"]
            if sens in ("1", "true", "True"): cmd.append("--sensitivity")
            if v3 in ("1", "true", "True"): cmd.append("--vote3")
            if neighb in ("1", "true", "True"): cmd.append("--neighbor-ct")
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
            if apc in ("1","true","True"): cmd.append("--apply-calibration")
            # Light-output is optional; not enforced by default
            if adf in ("1", "true", "True"):
                cmd.append("--adaptive-input")
            cmd += ["--adaptive-max-frames", str(admx), "--adaptive-margin-mV", str(admr), "--avg-frames", str(avf)]
            # Fast/skip flags
            if ff in ("1","true","True"): cmd.append("--fast")
            if ns in ("1","true","True"): cmd.append("--no-sweeps")
            if nc in ("1","true","True"): cmd.append("--no-cal")
            if nd in ("1","true","True"): cmd.append("--no-drift")
            if lo in ("1","true","True"): cmd.append("--light-output")
            # Normalization
            if norm_dv_csv in ("1","true","True"): cmd.append("--normalize-dv")
            if norm_eps_v not in (None, "", "None"): cmd += ["--normalize-eps-v", str(norm_eps_v)]
            # Tuner budgets
            if tune_budget_csv not in (None, "", "None"): cmd += ["--autotune-budget", str(tune_budget_csv)]
            if tune_trials_csv not in (None, "", "None"): cmd += ["--autotune-trials", str(tune_trials_csv)]
            # Post-tune application
            if aap in ("1","true","True"): cmd.append("--apply-autotuned-params")
            if uatp in ("1","true","True"): cmd.append("--use-autotuned-as-primary")
            if uap in ("1","true","True"): cmd.append("--use-avg-frames-for-path-a")
            if cls not in (None, "", "None"): cmd += ["--classifier", str(cls)]
            if rep not in (None, "", "None"): cmd += ["--repeat", str(rep)]
            if prm in ("1","true","True"): cmd.append("--permute-repeats")
            if ps not in (None, "", "None"): cmd += ["--permute-scheme", str(ps)]
            if lct in ("1","true","True"): cmd.append("--lock-optics-ct")
            if sth in ("1","true","True"): cmd.append("--soft-thresh")
            if ep: cmd += ["--emitter-pack", str(ep)]
            if op: cmd += ["--optics-pack", str(op)]
            if sp: cmd += ["--sensor-pack", str(sp)]
            if tp: cmd += ["--tia-pack", str(tp)]
            if cp: cmd += ["--comparator-pack", str(cp)]
            if cap: cmd += ["--camera-pack", str(cap)]
            if clp: cmd += ["--clock-pack", str(clp)]
            if thp: cmd += ["--thermal-pack", str(thp)]
            # Channels (if provided globally for matrix)
            if channels_list:
                chv = channels_list[0]
                cmd += ["--channels", str(chv)]
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


@app.post("/api/run_preset")
def api_run_preset():
    """Run a preset JSON describing one or more run branches.

    Schema (example):
      {
        "runs": [
          {
            "trials": [300],
            "seed": [123,321],
            "windows": [20,24],
            "inputs": ["digital"],
            "outputs": ["path_a"],
            "path_b_analog_depths": [5],
            "vote3": ["1"],
            "autotune": ["1"],
            "sensitivity": ["0"],
            "neighbor_ct": ["0"],
            "adaptive_input": ["1"],
            "adaptive_max_frames": ["12"],
            "adaptive_margin_mV": ["0.8"],
            "packs": {
              "emitter_packs": ["configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml"],
              "optics_packs": ["configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-5°_typ.yaml"],
              "sensor_packs": ["configs/packs/vendors/sensors/vishay_BPW34_typ.yaml"],
              "tia_packs": ["configs/packs/vendors/tias/texas_instruments_OPA857EVM_typ.yaml"],
              "comparator_packs": ["configs/packs/vendors/comparators/analog_devices_LTC6752_typ.yaml"],
              "camera_packs": [""],
              "clock_packs": ["configs/packs/clock_typ.yaml"],
              "thermal_packs": ["configs/packs/thermal_typ.yaml"]
            }
          }
        ]
      }
    """
    global _is_running
    try:
        data = request.get_json(force=True, silent=False)
        runs = data.get("runs", []) if isinstance(data, dict) else []
        if not runs:
            return jsonify({"error": "missing runs array"}), 400
    except Exception as e:
        return jsonify({"error": f"invalid JSON: {e}"}), 400
    with _run_lock:
        if _is_running:
            return jsonify({"status": "busy"}), 409
        _is_running = True
    try:
        import itertools, uuid, importlib, pathlib
        from .preflight import validate_combo
        jobs = []
        total_pruned = 0
        total_combos = 0

        def _parse_list(val, default):
            if val is None:
                return default
            if isinstance(val, list):
                return [str(x) for x in val]
            return [str(val)]

        def _load_yaml(path: str | None):
            if not path:
                return {}
            p = (ROOT / path) if not str(path).startswith("/") else pathlib.Path(path)
            text = p.read_text(encoding="utf-8")
            try:
                yaml_mod = importlib.import_module("yaml")
                return yaml_mod.safe_load(text) or {}
            except ModuleNotFoundError:
                return {}

        for branch in runs:
            trialsL = _parse_list(branch.get("trials"), ["300"])
            seedL = _parse_list(branch.get("seed"), ["123"])
            winL = _parse_list(branch.get("windows"), ["20"])  # base window ns
            chanL = _parse_list(branch.get("channels"), [None])
            inputsL = _parse_list(branch.get("inputs"), ["digital"])
            outputsL = _parse_list(branch.get("outputs"), ["path_a"])  # path_a or path_b_analog
            depthL = _parse_list(branch.get("path_b_analog_depths"), ["5"])
            voteL = _parse_list(branch.get("vote3"), ["1"])
            autoL = _parse_list(branch.get("autotune"), ["1"])
            sensL = _parse_list(branch.get("sensitivity"), ["0"])
            neighL = _parse_list(branch.get("neighbor_ct"), ["0"])
            applyCalL = _parse_list(branch.get("apply_calibration"), ["0"])
            adaptL = _parse_list(branch.get("adaptive_input"), ["1"])
            adaptMaxL = _parse_list(branch.get("adaptive_max_frames"), ["12"])
            adaptMargL = _parse_list(branch.get("adaptive_margin_mV"), ["0.8"])
            avgFramesL = _parse_list(branch.get("avg_frames"), ["1"])
            # Fast/skip flags (non-destructive: only skip heavy diagnostics)
            fastL = _parse_list(branch.get("fast"), ["0"])
            noSweepsL = _parse_list(branch.get("no_sweeps"), ["0"])
            noCalL = _parse_list(branch.get("no_cal"), ["0"])
            noDriftL = _parse_list(branch.get("no_drift"), ["0"])
            lightOutL = _parse_list(branch.get("light_output"), ["0"])
            # Optional cap to limit combinatorics per branch
            capL = _parse_list(branch.get("cap"), [None])
            # Normalization and tuner budges
            normDvL = _parse_list(branch.get("normalize_dv"), ["0"])
            normEpsVL = _parse_list(branch.get("normalize_eps_v"), ["1e-6"])
            tuneBudgetL = _parse_list(branch.get("autotune_budget"), [None])
            tuneTrialsL = _parse_list(branch.get("autotune_trials"), [None])
            applyAutoL = _parse_list(branch.get("apply_autotuned_params"), ["0"])
            useAutoPrimaryL = _parse_list(branch.get("use_autotuned_as_primary"), ["0"])
            useAvgPathAL = _parse_list(branch.get("use_avg_frames_for_path_a"), ["0"])
            lockCtL = _parse_list(branch.get("lock_optics_ct"), ["0"])
            softThreshL = _parse_list(branch.get("soft_thresh"), ["0"])
            # Classifier controls (optional)
            classifierL = _parse_list(branch.get("classifier"), [None])
            repeatL = _parse_list(branch.get("repeat"), [None])
            permuteL = _parse_list(branch.get("permute_repeats"), ["0"])
            permSchemeL = _parse_list(branch.get("permute_scheme"), ["random"])
            # Bad-channel mask controls
            maskBadChL = _parse_list(branch.get("mask_bad_channels"), [None])
            maskBadFracL = _parse_list(branch.get("mask_bad_frac"), [None])
            calibMaskTrialsL = _parse_list(branch.get("calib_mask_trials"), [None])

            packs = branch.get("packs", {})
            def P(key):
                v = packs.get(key)
                if isinstance(v, list):
                    return v if v else [None]
                if v:
                    return [v]
                return [None]
            epL = P("emitter_packs"); opL = P("optics_packs"); spL = P("sensor_packs"); tpL = P("tia_packs")
            cpL = P("comparator_packs"); capL = P("camera_packs"); clpL = P("clock_packs"); thpL = P("thermal_packs")

            # Preload pack YAMLs
            pack_data = {}
            for lst in (epL+opL+spL+tpL+cpL+capL+clpL+thpL):
                if lst and lst not in pack_data:
                    try:
                        pack_data[lst] = _load_yaml(lst)
                    except Exception:
                        pack_data[lst] = {}

            for (tr, sd) in itertools.product(trialsL, seedL):
                for (inp, outp, win, depth, v3, au, se, ne, apc, adf, admx, admr, avf, ff, ns, nc, nd, ndv, neps, tb, tt, aap, uatp, uap, lct, sth, lo, cls, rep, prm, ps, ch, mbc, mbf, cmt) in itertools.product(
                    inputsL, outputsL, winL, depthL, voteL, autoL, sensL, neighL, applyCalL, adaptL, adaptMaxL, adaptMargL, avgFramesL, fastL, noSweepsL, noCalL, noDriftL, normDvL, normEpsVL, tuneBudgetL, tuneTrialsL, applyAutoL, useAutoPrimaryL, useAvgPathAL, lockCtL, softThreshL, lightOutL,
                    classifierL, repeatL, permuteL, permSchemeL, chanL, maskBadChL, maskBadFracL, calibMaskTrialsL
                ):
                    for (ep, op, spk, tpv, cpv, cav, clv, thv) in itertools.product(epL, opL, spL, tpL, cpL, capL, clpL, thpL):
                        total_combos += 1
                        packs_dict = {
                            "emitter": pack_data.get(ep, {}),
                            "optics": pack_data.get(op, {}),
                            "sensor": pack_data.get(spk, {}),
                            "tia": pack_data.get(tpv, {}),
                            "comparator": pack_data.get(cpv, {}),
                            "camera": pack_data.get(cav, {}),
                            "clock": pack_data.get(clv, {}),
                            "thermal": pack_data.get(thv, {}),
                        }
                        v = validate_combo(packs_dict, window_ns=float(win))
                        if v.get("status") == "fail":
                            total_pruned += 1
                            continue
                        run_id = str(uuid.uuid4())
                        out_path = ROOT / "out" / f"test_summary_{run_id}.json"
                        cmd = ["python", "examples/test.py",
                               "--trials", str(tr), "--seed", str(sd), "--json", str(out_path),
                               "--base-window-ns", str(win), "--quiet"]
                        if se in ("1","true","True"): cmd.append("--sensitivity")
                        if v3 in ("1","true","True"): cmd.append("--vote3")
                        if ne in ("1","true","True"): cmd.append("--neighbor-ct")
                        if inp == "digital": cmd.append("--no-cold-input")
                        if outp == "path_a": cmd += ["--no-path-b", "--no-path-b-analog", "--components-mode", "path_a"]
                        elif outp == "path_b_analog": cmd += ["--path-b-analog-depth", str(depth), "--no-path-b", "--components-mode", "path_b_analog"]
                        if au in ("1","true","True"): cmd.append("--autotune")
                        if apc in ("1","true","True"): cmd.append("--apply-calibration")
                        # Light-output is optional; not enforced by default
                        if adf in ("1","true","True"): cmd.append("--adaptive-input")
                        cmd += ["--adaptive-max-frames", str(admx), "--adaptive-margin-mV", str(admr), "--avg-frames", str(avf)]
                        # Fast/skip flags from preset
                        if ff in ("1","true","True"): cmd.append("--fast")
                        if ns in ("1","true","True"): cmd.append("--no-sweeps")
                        if nc in ("1","true","True"): cmd.append("--no-cal")
                        if nd in ("1","true","True"): cmd.append("--no-drift")
                        if lo in ("1","true","True"): cmd.append("--light-output")
                        # Normalization
                        if ndv in ("1","true","True"): cmd.append("--normalize-dv")
                        if neps not in (None, "", "None"): cmd += ["--normalize-eps-v", str(neps)]
                        # Tuner budgets
                        if tb not in (None, "", "None"): cmd += ["--autotune-budget", str(tb)]
                        if tt not in (None, "", "None"): cmd += ["--autotune-trials", str(tt)]
                        if aap in ("1","true","True"): cmd.append("--apply-autotuned-params")
                        if uatp in ("1","true","True"): cmd.append("--use-autotuned-as-primary")
                        if uap in ("1","true","True"): cmd.append("--use-avg-frames-for-path-a")
                        if lct in ("1","true","True"): cmd.append("--lock-optics-ct")
                        if sth in ("1","true","True"): cmd.append("--soft-thresh")
                        if ch not in (None, "", "None"): cmd += ["--channels", str(ch)]
                        if cls not in (None, "", "None"): cmd += ["--classifier", str(cls)]
                        if rep not in (None, "", "None"): cmd += ["--repeat", str(rep)]
                        if prm in ("1","true","True"): cmd.append("--permute-repeats")
                        if ps not in (None, "", "None"): cmd += ["--permute-scheme", str(ps)]
                        if mbc not in (None, "", "None"): cmd += ["--mask-bad-channels", str(mbc)]
                        if mbf not in (None, "", "None"): cmd += ["--mask-bad-frac", str(mbf)]
                        if cmt not in (None, "", "None"): cmd += ["--calib-mask-trials", str(cmt)]
                        if ep: cmd += ["--emitter-pack", str(ep)]
                        if op: cmd += ["--optics-pack", str(op)]
                        if spk: cmd += ["--sensor-pack", str(spk)]
                        if tpv: cmd += ["--tia-pack", str(tpv)]
                        if cpv: cmd += ["--comparator-pack", str(cpv)]
                        if cav: cmd += ["--camera-pack", str(cav)]
                        if clv: cmd += ["--clock-pack", str(clv)]
                        if thv: cmd += ["--thermal-pack", str(thv)]
                        jobs.append((cmd, run_id, out_path, inp, se, outp, win, depth, ep, op, spk, tpv, cpv, cav, clv, thv, v))

            # Apply per-branch cap if provided
            try:
                cap_val = next((c for c in capL if c not in (None, "", "None")), None)
                if cap_val is not None:
                    cap_n = int(cap_val)
                    if cap_n > 0 and len(jobs) > cap_n:
                        jobs = jobs[:cap_n]
            except Exception:
                pass

        if not jobs:
            return jsonify({"status": "noop", "pruned": total_pruned, "combos": total_combos}), 200

        # Enqueue and start processor
        _pending_jobs.put(jobs)
        threading.Thread(target=_process_joblist, daemon=True).start()
        return jsonify({"status": "started", "runs": len(jobs), "pruned": total_pruned, "combos": total_combos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/dashboard/<path:path>")
def static_files(path: str):
    return send_from_directory(str(DASH_DIR), path)


def main():
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

