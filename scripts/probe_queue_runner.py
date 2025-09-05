import sys
import time
import json
import hashlib
import runpy
from pathlib import Path
from datetime import datetime
import os


BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_PATH = BASE_DIR / "queue" / "probes.jsonl"
COMPLETED_PATH = BASE_DIR / "queue" / "completed.jsonl"
OUT_DIR = BASE_DIR / "out"


def ensure_paths():
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not QUEUE_PATH.exists():
        QUEUE_PATH.write_text("", encoding="utf-8")
    if not COMPLETED_PATH.exists():
        COMPLETED_PATH.write_text("", encoding="utf-8")


def job_signature(job: dict) -> str:
    # Exclude output path from signature so replays to new file don't duplicate
    canon = {k: v for k, v in job.items() if k not in {"json_out", "label"}}
    blob = json.dumps(canon, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def load_completed_signatures() -> set[str]:
    sigs: set[str] = set()
    try:
        for line in COMPLETED_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                s = rec.get("signature")
                status = rec.get("status")
                # Skip signatures that have already been processed (ok or error)
                if isinstance(s, str) and status in ("ok", "error"):
                    sigs.add(s)
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        pass
    return sigs


def append_completed(record: dict) -> None:
    # Write a minimal record to avoid encoding/size issues
    rec_min = {
        "signature": record.get("signature"),
        "status": record.get("status"),
        "out": record.get("out"),
        "summary": record.get("summary"),
        "finished_at": record.get("finished_at"),
        # Include helpful debugging fields when present
        "error": record.get("error"),
        "label": (record.get("job") or {}).get("label") if isinstance(record.get("job"), dict) else None,
        "traceback": record.get("traceback"),
    }
    # Append one JSON line per run and force it to disk immediately
    line = json.dumps(rec_min, ensure_ascii=True) + "\n"
    try:
        before = COMPLETED_PATH.stat().st_size if COMPLETED_PATH.exists() else 0
    except Exception:
        before = -1
    with COMPLETED_PATH.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        try:
            import os
            os.fsync(f.fileno())
        except OSError as _oe:
            print(f"WARN: fsync failed on {COMPLETED_PATH}: {_oe}")
    try:
        after = COMPLETED_PATH.stat().st_size
        print(f"APPENDED completed: +{after-before} bytes at {COMPLETED_PATH}")
    except Exception as _se:
        print(f"WARN: stat failed on {COMPLETED_PATH}: {_se}")


def build_argv_from_job(job: dict, out_path: str) -> list[str]:
    # Allow passthrough args if provided
    if isinstance(job.get("args"), list):
        return ["examples/test.py", *[str(x) for x in job["args"]], "--quiet", "--json", out_path]

    # Defaults and mappings
    trials = int(job.get("trials", 200))
    seed = int(job.get("seed", 123))
    base_window_ns = float(job.get("base_window_ns", 16.0))
    classifier = str(job.get("classifier", "avg"))
    avg_frames = int(job.get("avg_frames", 1))

    def flag(b: bool, name: str):
        return [name] if b else []

    # Optionally merge overlay packs into vendor packs and write temp merged YAMLs
    tmp_dir = Path("queue/tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    def prepare_merged_pack(base_key: str, overlay_key: str, default_path: str, tag: str) -> str:
        base = str(job.get(base_key, default_path))
        over = str(job.get(overlay_key, ""))
        if not over:
            return base
        try:
            import yaml  # type: ignore
            base_d = {}
            over_d = {}
            if Path(base).exists():
                base_d = yaml.safe_load(Path(base).read_text(encoding="utf-8")) or {}
            if Path(over).exists():
                over_d = yaml.safe_load(Path(over).read_text(encoding="utf-8")) or {}
            merged = dict(base_d)
            merged.update(over_d)
            sig = hashlib.sha1(json.dumps({"b": base, "o": over}, sort_keys=True).encode("utf-8")).hexdigest()[:10]
            outp = tmp_dir / f"merged_{tag}_{sig}.yaml"
            outp.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
            return str(outp)
        except ModuleNotFoundError:
            return base
        except Exception:
            return base

    optics_pack_path = prepare_merged_pack(
        "optics_pack", "optics_overlay",
        "configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-5°_typ.yaml", "optics"
    )
    comparator_pack_path = prepare_merged_pack(
        "comparator_pack", "comparator_overlay",
        "configs/packs/vendors/comparators/analog_devices_LTC6752_typ.yaml", "comp"
    )
    tia_pack_base = str(job.get("tia_pack", "configs/packs/vendors/tias/texas_instruments_OPA857EVM_typ.yaml"))
    tia_pack_path = prepare_merged_pack("tia_pack", "tia_overlay", tia_pack_base, "tia")

    argv = [
        "examples/test.py",
        "--trials", str(trials),
        "--seed", str(seed),
        "--no-sweeps",
        "--no-drift",
        "--light-output",
        "--base-window-ns", str(base_window_ns),
        "--avg-frames", str(avg_frames),
        "--classifier", classifier,
        *flag(bool(job.get("apply_calibration", True)), "--apply-calibration"),
        *flag(bool(job.get("no_adaptive_input", True)), "--no-adaptive-input"),
        *flag(bool(job.get("neighbor_ct", False)), "--neighbor-ct"),
        *flag(bool(job.get("no_cold_input", True)), "--no-cold-input"),
        *flag(bool(job.get("no_path_b", True)), "--no-path-b"),
        "--path-b-depth", str(int(job.get("path_b_depth", 0))),
        *flag(bool(job.get("no_path_b_analog", True)), "--no-path-b-analog"),
        *flag(bool(job.get("lockin", False)), "--lockin"),
        *flag(bool(job.get("chop", False)), "--chop"),
        *flag(bool(job.get("mitigated", False)), "--mitigated"),
        *flag(bool(job.get("use_avg_frames_for_path_a", False)), "--use-avg-frames-for-path-a"),
        *flag(bool(job.get("normalize_dv", False)), "--normalize-dv"),
        # Masking controls
        "--mask-bad-frac", str(job.get("mask_bad_frac", 0.0)),
        "--mask-bad-channels", str(int(job.get("mask_bad_channels", 0))),
        "--calib-mask-trials", str(int(job.get("calib_mask_trials", 200))),
        *(["--mask-mode", str(job.get("mask_mode"))] if job.get("mask_mode") else []),
        # Comparator overrides
        *(["--comp-hysteresis-mV", str(job.get("comp_hysteresis_mV"))] if job.get("comp_hysteresis_mV") is not None else []),
        *(["--comp-input-noise-mV", str(job.get("comp_input_noise_mV"))] if job.get("comp_input_noise_mV") is not None else []),
        *(["--comp-vth-mV", str(job.get("comp_vth_mV"))] if job.get("comp_vth_mV") is not None else []),
        *(["--comp-vth-sigma-mV", str(job.get("comp_vth_sigma_mV"))] if job.get("comp_vth_sigma_mV") is not None else []),
        # Per-channel vth workflows
        *(["--export-vth", str(job.get("export_vth"))] if job.get("export_vth") else []),
        *(["--import-vth", str(job.get("import_vth"))] if job.get("import_vth") else []),
        *(["--vth-inline", str(job.get("vth_inline"))] if job.get("vth_inline") else []),
        *(["--vth-scale", str(job.get("vth_scale"))] if job.get("vth_scale") is not None else []),
        *(["--vth-bias-mV", str(job.get("vth_bias_mV"))] if job.get("vth_bias_mV") is not None else []),
        # Packs
        "--emitter-pack", str(job.get("emitter_pack", "configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml")),
        "--optics-pack", optics_pack_path,
        "--sensor-pack", str(job.get("sensor_pack", "configs/packs/vendors/sensors/vishay_BPW34_typ.yaml")),
        "--tia-pack", tia_pack_path,
        "--comparator-pack", comparator_pack_path,
        "--clock-pack", str(job.get("clock_pack", "configs/packs/clock_typ.yaml")),
        "--thermal-pack", str(job.get("thermal_pack", "configs/packs/thermal_typ.yaml")),
        "--quiet",
        "--json", out_path,
    ]
    return argv


def run_job(job: dict) -> dict:
    # Determine output path
    out_path = job.get("json_out")
    if not out_path:
        sig = job_signature(job)
        out_path = str(OUT_DIR / f"probe_{sig[:10]}.json")

    # RAW passthrough modes: job["raw"] string or job["cmd"] array
    if isinstance(job.get("cmd"), list):
        argv = ["examples/test.py", *[str(x) for x in job["cmd"]]]
        # Back-compat/arg hygiene: fix known flag typos and remove deprecated ones
        try:
            # Replace legacy '--gate-thresh-mv' with correct '--gate-thresh-mV'
            argv = ["--gate-thresh-mV" if x == "--gate-thresh-mv" else x for x in argv]
            # Remove '--gate-mode' and its value if present
            if "--gate-mode" in argv:
                gm_idx = argv.index("--gate-mode")
                # Drop flag and following value if any
                del argv[gm_idx: min(gm_idx+2, len(argv))]
        except Exception:
            pass
        # If overlays are provided on the job, append merged packs unless already present
        try:
            def has_flag(flag: str) -> bool:
                try:
                    return flag in argv
                except Exception:
                    return False

            # Reuse merge logic
            tmp_dir = Path("queue/tmp")
            tmp_dir.mkdir(parents=True, exist_ok=True)

            def prepare_merged_pack(base_key: str, overlay_key: str, default_path: str, tag: str) -> str:
                base = str(job.get(base_key, default_path))
                over = str(job.get(overlay_key, ""))
                if not over:
                    return base
                try:
                    import yaml  # type: ignore
                    base_d = {}
                    over_d = {}
                    if Path(base).exists():
                        base_d = yaml.safe_load(Path(base).read_text(encoding="utf-8")) or {}
                    if Path(over).exists():
                        over_d = yaml.safe_load(Path(over).read_text(encoding="utf-8")) or {}
                    merged = dict(base_d)
                    merged.update(over_d)
                    sig = hashlib.sha1(json.dumps({"b": base, "o": over}, sort_keys=True).encode("utf-8")).hexdigest()[:10]
                    outp = tmp_dir / f"merged_{tag}_{sig}.yaml"
                    outp.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
                    return str(outp)
                except ModuleNotFoundError:
                    return base
                except Exception:
                    return base

            # Compute merged pack paths
            optics_pack_path = prepare_merged_pack(
                "optics_pack", "optics_overlay",
                "configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-5°_typ.yaml", "optics"
            )
            comparator_pack_path = prepare_merged_pack(
                "comparator_pack", "comparator_overlay",
                "configs/packs/vendors/comparators/analog_devices_LTC6752_typ.yaml", "comp"
            )
            tia_pack_base = str(job.get("tia_pack", "configs/packs/vendors/tias/texas_instruments_OPA857EVM_typ.yaml"))
            tia_pack_path = prepare_merged_pack("tia_pack", "tia_overlay", tia_pack_base, "tia")

            # Append pack flags if not already provided in cmd
            if not has_flag("--optics-pack"):
                argv += ["--optics-pack", optics_pack_path]
            if not has_flag("--comparator-pack"):
                argv += ["--comparator-pack", comparator_pack_path]
            if not has_flag("--tia-pack"):
                argv += ["--tia-pack", tia_pack_path]
            if not has_flag("--emitter-pack"):
                argv += ["--emitter-pack", str(job.get("emitter_pack", "configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml"))]
            if not has_flag("--sensor-pack"):
                argv += ["--sensor-pack", str(job.get("sensor_pack", "configs/packs/vendors/sensors/vishay_BPW34_typ.yaml"))]
            if not has_flag("--clock-pack"):
                argv += ["--clock-pack", str(job.get("clock_pack", "configs/packs/clock_typ.yaml"))]
            if not has_flag("--thermal-pack"):
                argv += ["--thermal-pack", str(job.get("thermal_pack", "configs/packs/thermal_typ.yaml"))]
            # Support use_avg_frames_for_path_a via job key if requested
            if bool(job.get("use_avg_frames_for_path_a", False)) and not has_flag("--use-avg-frames-for-path-a"):
                argv += ["--use-avg-frames-for-path-a"]
        except Exception as _e_overlay:
            # Non-fatal: continue without overlays if something goes wrong
            pass
    elif isinstance(job.get("raw"), str):
        import shlex
        argv = ["examples/test.py", *shlex.split(job["raw"]) ]
    else:
        argv = build_argv_from_job(job, out_path)

    # Ensure JSON path present in argv
    if "--json" not in argv:
        argv += ["--quiet", "--json", out_path]
    # If job requests verbose, strip any --quiet flags so test.py prints
    try:
        if bool(job.get("verbose", False)):
            argv = [a for a in argv if a != "--quiet"]
    except Exception:
        pass

    # Execute examples/test.py by path to avoid package import issues
    prev_argv = sys.argv[:]
    _se_code = 0
    _se_error = None
    try:
        sys.argv = argv
        # Optionally suppress stdout from test.py to avoid huge prints
        import os as _os
        job_verbose = bool(job.get("verbose", False)) if isinstance(job, dict) else False
        suppress = False if job_verbose else (str(_os.environ.get("SUPPRESS_TEST_STDOUT", "1")).lower() in ("1","true","yes"))
        import traceback as _tb
        import sys as _sys
        import io as _io
        import contextlib as _ctx
        # Prepare stdout capture; if verbose, tee to console
        buf = _io.StringIO()
        class _Tee:
            def __init__(self, a, b):
                self.a = a; self.b = b
            def write(self, s):
                try:
                    self.a.write(s)
                except Exception:
                    pass
                return self.b.write(s)
            def flush(self):
                try:
                    self.a.flush()
                except Exception:
                    pass
                return self.b.flush()
        buf_err = _io.StringIO()
        try:
            if suppress:
                with _ctx.redirect_stdout(buf), _ctx.redirect_stderr(buf_err):
                    runpy.run_path("examples/test.py", run_name="__main__")
            else:
                tee_out = _Tee(_sys.__stdout__, buf)
                tee_err = _Tee(_sys.__stderr__, buf_err)
                with _ctx.redirect_stdout(tee_out), _ctx.redirect_stderr(tee_err):
                    runpy.run_path("examples/test.py", run_name="__main__")
        except SystemExit as _se:
            # Convert nonzero sys.exit from test.py into a regular error so main() can record and continue
            code = getattr(_se, 'code', 0)
            if code not in (None, 0):
                _se_code = int(code) if isinstance(code, int) else 1
                _se_error = f"test.py exited with code {code}\nSTDOUT:\n{buf.getvalue()}\nSTDERR:\n{buf_err.getvalue()}"
        except Exception as _e:
            # Attach traceback string to propagate to main()
            tb = _tb.format_exc()
            raise RuntimeError(f"test.py exception: {_e}\n{tb}\nSTDOUT:\n{buf.getvalue()}\nSTDERR:\n{buf_err.getvalue()}")
    finally:
        sys.argv = prev_argv
    # If test.py exited non-zero but produced JSON, accept it; otherwise raise
    out_file = Path(out_path)
    if _se_code not in (0, None) and not out_file.exists():
        raise RuntimeError(_se_error or f"test.py exited with code {_se_code}")
    data = json.loads(out_file.read_text(encoding="utf-8"))
    return {"out": out_path, "data": data}


def summarize(data: dict) -> dict:
    cfg = data.get("config") or {}
    base_cal = data.get("baseline_calibrated") or {}
    path_a = data.get("path_a") or {}
    return {
        "base_window_ns": cfg.get("base_window_ns"),
        "baseline_calibrated_p50_ber": base_cal.get("p50_ber"),
        "path_a_p50_ber": path_a.get("p50_ber"),
    }
def _play_idle_chime_once() -> None:
    """Play a small, mild chime when entering idle. Best-effort, Windows-first.

    Controlled by env IDLE_CHIME (default: on). Set IDLE_CHIME=0 to disable.
    """
    if str(os.environ.get("IDLE_CHIME", "1")).lower() in ("0", "false", "no"):
        return
    try:
        import winsound  # type: ignore
        mode = str(os.environ.get("IDLE_BEEP", "")).lower()
        if mode in ("1", "true", "yes", "beep"):
            # Explicit simple beep (audible on most Windows systems)
            winsound.Beep(800, 120)  # 800 Hz, 120 ms
        else:
            # Mild system chime; if silent on this host, optionally follow with a short beep
            winsound.MessageBeep(getattr(winsound, "MB_ICONASTERISK", 0))
            if str(os.environ.get("IDLE_FALLBACK_BEEP", "1")).lower() in ("1","true","yes"):
                try:
                    winsound.Beep(800, 80)
                except Exception:
                    pass
        return
    except Exception:
        pass
    # Fallback: ASCII bell (may be ignored on some terminals)
    try:
        print("\a", end="", flush=True)
    except Exception:
        pass



def main():
    ensure_paths()
    print(f"probe_queue_runner: watching queue={QUEUE_PATH}")
    print(f"probe_queue_runner: writing completed to {COMPLETED_PATH}")
    last_status = None
    last_idle = None
    while True:
        # Always reload completed_ok from disk; if file doesn't exist or is empty, treat as empty set
        try:
            sig_done = load_completed_signatures()
        except Exception as e:
            print(f"WARN: failed to read completed file: {e}")
            sig_done = set()
        try:
            text = QUEUE_PATH.read_text(encoding="utf-8")
            lines = text.splitlines()
        except Exception as e:
            print(f"WARN: failed to read queue file: {e}")
            lines = []
        status_msg = f"STATUS: queue_lines={len(lines)} completed_ok={len(sig_done)}"
        if status_msg != last_status:
            print(status_msg)
            last_status = status_msg
        ran_one = False
        quiet_skips = str(os.environ.get("QUIET_SKIPS", "1")).lower() in ("1","true","yes")
        skip_count = 0
        for idx, raw in enumerate(lines):
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                if raw and not quiet_skips:
                    print(f"SKIP[{idx}]: comment/blank")
                continue
            try:
                job = json.loads(raw)
            except json.JSONDecodeError as je:
                if not quiet_skips:
                    preview = raw[:120].replace('\n',' ')
                    print(f"SKIP[{idx}]: json error {je} in '{preview}...'")
                continue
            sig = job_signature(job)
            # Skip if this signature is already present in completed.jsonl
            if sig in sig_done:
                if quiet_skips:
                    skip_count += 1
                else:
                    print(f"SKIP[{idx}]: already completed ok sig={sig[:8]}")
                continue
            started_at = datetime.utcnow().isoformat() + "Z"
            try:
                res = run_job(job)
                summ = summarize(res["data"]) if isinstance(res, dict) else {}
                append_completed({
                    "signature": sig,
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "out": res.get("out"),
                    "summary": summ,
                    "status": "ok",
                })
                print(f"DONE {sig[:8]} -> {res.get('out')} {summ}")
            except Exception as e:
                append_completed({
                    "signature": sig,
                    "started_at": started_at,
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "error": str(e),
                    "traceback": getattr(e, 'args', [None])[-1] if e.args else None,
                    "job": job,
                    "status": "error",
                })
                print(f"ERROR {sig[:8]} {e}")
            # Do NOT remove lines; probes.jsonl remains static. Rely solely on completed.jsonl for skipping.
            try:
                # Show updated completed_ok for visibility
                new_done = load_completed_signatures()
                print(f"UPDATED: completed_ok={len(new_done)}")
            except Exception as _e2:
                print(f"WARN: failed to reload completed: {_e2}")
            if quiet_skips and skip_count:
                print(f"SKIPPED {skip_count} already-completed entries (quiet)")
            ran_one = True
            break  # Process only one job per loop
        # Sleep briefly; if we ran one job, loop immediately to check for more
        if not ran_one:
            if quiet_skips and skip_count:
                idle_msg = f"IDLE: sleeping 2s (quiet; {skip_count} skips)"
            else:
                idle_msg = "IDLE: sleeping 2s"
            if idle_msg != last_idle:
                print(idle_msg)
                # Play a small chime once and log it before the separator
                _play_idle_chime_once()
                try:
                    print("[idle chime]\n==================")
                except Exception:
                    print("==================")
                last_idle = idle_msg
            time.sleep(2.0)


def _run_forever():
    import time as _t
    while True:
        try:
            main()
        except SystemExit as _se:
            code = getattr(_se, 'code', 0)
            if code not in (None, 0):
                print(f"WARN: main exited with code {code}, restarting in 1s")
            _t.sleep(1.0)
            continue
        except Exception as _e:
            print(f"WARN: main crashed: {_e}; restarting in 1s")
            _t.sleep(1.0)
            continue

if __name__ == "__main__":
    _run_forever()


