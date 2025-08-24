import sys
import time
import json
import hashlib
import runpy
from pathlib import Path
from datetime import datetime


QUEUE_PATH = Path("queue/probes.jsonl")
COMPLETED_PATH = Path("queue/completed.jsonl")
OUT_DIR = Path("out")


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
                if isinstance(s, str):
                    sigs.add(s)
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        pass
    return sigs


def append_completed(record: dict) -> None:
    with COMPLETED_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


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
        *flag(bool(job.get("no_cold_input", True)), "--no-cold-input"),
        *flag(bool(job.get("no_path_b", True)), "--no-path-b"),
        "--path-b-depth", str(int(job.get("path_b_depth", 0))),
        *flag(bool(job.get("no_path_b_analog", True)), "--no-path-b-analog"),
        # Packs
        "--emitter-pack", str(job.get("emitter_pack", "configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml")),
        "--optics-pack", str(job.get("optics_pack", "configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-5°_typ.yaml")),
        "--sensor-pack", str(job.get("sensor_pack", "configs/packs/vendors/sensors/vishay_BPW34_typ.yaml")),
        # Allow multiple TIA overlays
        "--tia-pack", str(job.get("tia_pack", "configs/packs/vendors/tias/texas_instruments_OPA857EVM_typ.yaml")),
        "--tia-pack", str(job.get("tia_overlay", "configs/packs/overlays/tuned_tia.yaml")),
        "--comparator-pack", str(job.get("comparator_pack", "configs/packs/vendors/comparators/analog_devices_LTC6752_typ.yaml")),
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

    argv = build_argv_from_job(job, out_path)
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
    print("probe_queue_runner: watching queue/probes.jsonl (Ctrl+C to stop)")
    while True:
        sig_done = load_completed_signatures()
        lines = QUEUE_PATH.read_text(encoding="utf-8").splitlines()
        ran_one = False
        for raw in lines:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                job = json.loads(raw)
            except json.JSONDecodeError:
                continue
            sig = job_signature(job)
            if sig in sig_done:
                continue
            started_at = datetime.utcnow().isoformat() + "Z"
            try:
                res = run_job(job)
                summ = summarize(res["data"]) if isinstance(res, dict) else {}
                append_completed({
                    "signature": sig,
                    "started_at": started_at,
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "out": res.get("out"),
                    "summary": summ,
                    "job": job,
                })
                print(f"DONE {sig[:8]} -> {res.get('out')} {summ}")
            except Exception as e:
                append_completed({
                    "signature": sig,
                    "started_at": started_at,
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "error": str(e),
                    "job": job,
                })
                print(f"ERROR {sig[:8]} {e}")
            ran_one = True
            break  # Process only one job per loop
        # Sleep briefly; if we ran one job, loop immediately to check for more
        if not ran_one:
            time.sleep(2.0)


if __name__ == "__main__":
    main()


