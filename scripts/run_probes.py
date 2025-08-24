import sys
import json
from pathlib import Path


def run_one(window_ns: float, out_path: str) -> dict:
    # Build argv to call examples/test.py main() directly (avoids shell quoting issues)
    argv = [
        "examples/test.py",
        "--trials", "200",
        "--seed", "123",
        "--no-sweeps",
        "--no-drift",
        "--light-output",
        "--base-window-ns", str(float(window_ns)),
        "--avg-frames", "1",
        "--classifier", "avg",
        "--apply-calibration",
        "--no-adaptive-input",
        "--no-cold-input",
        "--no-path-b", "--path-b-depth", "0", "--no-path-b-analog",
        # Vendor packs (match winning preset)
        "--emitter-pack", "configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml",
        "--optics-pack", "configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-5°_typ.yaml",
        "--sensor-pack", "configs/packs/vendors/sensors/vishay_BPW34_typ.yaml",
        "--tia-pack", "configs/packs/vendors/tias/texas_instruments_OPA857EVM_typ.yaml",
        "--tia-pack", "configs/packs/overlays/tuned_tia.yaml",
        "--comparator-pack", "configs/packs/vendors/comparators/analog_devices_LTC6752_typ.yaml",
        "--clock-pack", "configs/packs/clock_typ.yaml",
        "--thermal-pack", "configs/packs/thermal_typ.yaml",
        "--quiet",
        "--json", out_path,
    ]
    # Inject argv and call main
    import importlib
    test_mod = importlib.import_module("examples.test")
    prev_argv = sys.argv[:]
    try:
        sys.argv = argv
        test_mod.main()
    finally:
        sys.argv = prev_argv
    # Load result
    data = json.loads(Path(out_path).read_text(encoding="utf-8"))
    return data


def summarize(label: str, data: dict) -> str:
    base_cal = (data.get("baseline_calibrated") or {})
    pa = (data.get("path_a") or {})
    cfg = (data.get("config") or {})
    return "{} win={} base_cal.p50_ber={} path_a.p50_ber={}".format(
        label,
        cfg.get('base_window_ns'),
        base_cal.get('p50_ber'),
        pa.get('p50_ber'),
    )


def main():
    # Minimal fixed set of windows to probe quickly; adjust as needed
    windows = [14.0, 16.0, 18.0, 20.0]
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for w in windows:
        out_path = str(out_dir / f"probe_single_avg_win{int(w)}.json")
        data = run_one(w, out_path)
        lines.append(summarize(f"single_avg", data))
    # Print concise summary lines
    for ln in lines:
        print(ln)


if __name__ == "__main__":
    main()


