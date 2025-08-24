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
                # Only skip if previously completed successfully
                if isinstance(s, str) and status == "ok":
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
    elif isinstance(job.get("raw"), str):
        import shlex
        argv = ["examples/test.py", *shlex.split(job["raw"]) ]
    else:
        argv = build_argv_from_job(job, out_path)

    # Ensure JSON path present in argv
    if "--json" not in argv:
        argv += ["--quiet", "--json", out_path]

    # Execute examples/test.py by path to avoid package import issues
    prev_argv = sys.argv[:]
    try:
        sys.argv = argv
        runpy.run_path("examples/test.py", run_name="__main__")
    finally:
        sys.argv = prev_argv
    data = json.loads(Path(out_path).read_text(encoding="utf-8"))
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


def main():
    ensure_paths()
    print(f"probe_queue_runner: watching queue={QUEUE_PATH}")
    print(f"probe_queue_runner: writing completed to {COMPLETED_PATH}")
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
        print(f"STATUS: queue_lines={len(lines)} completed_ok={len(sig_done)}")
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
                print(f"IDLE: sleeping 2s (quiet; {skip_count} skips)")
            else:
                print("IDLE: sleeping 2s")
            time.sleep(2.0)


if __name__ == "__main__":
    main()


