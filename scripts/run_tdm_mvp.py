import json
import subprocess
import sys
from pathlib import Path


PY = sys.executable or "python"
ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "examples" / "test.py"
OUT = ROOT / "out"


def run(cmd):
    print("RUN:", " ".join(map(str, cmd)))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit(r.returncode)
    return r


def call_test(json_out: Path, extra: list[str]):
    cmd = [
        PY, str(TEST),
        "--trials", "240",
        "--channels", "16",
        "--base-window-ns", "10",
        "--classifier", "chop",
        "--avg-frames", "2",
        "--apply-calibration",
        "--no-adaptive-input",
        "--no-cold-input",
        "--no-sweeps",
        "--emitter-pack", "configs/packs/tmp_lowcost_emitter_boost.yaml",
        "--sensor-pack", "configs/packs/overlays/receiver_ingaas_typ.yaml",
        "--tia-pack", "configs/packs/overlays/tia_stage_b2_low_noise.yaml",
        "--comparator-pack", "configs/packs/overlays/tuned_comparator.yaml",
        "--clock-pack", "configs/packs/overlays/clock_jitter_20ps.yaml",
        "--normalize-dv",
        "--path-b-depth", "5",
        "--path-b-analog-depth", "5",
        "--path-b-balanced",
        "--path-b-calibrate-vth",
        "--path-b-calibrate-vth-scale", "0.5",
        "--path-b-calibrate-vth-passes", "64",
        "--path-b-stage-gains-db", "2.0,1.0,0,-0.25,-0.25",
        "--path-b-vth-schedule", "12,12,8,6,5",
        "--json", str(json_out),
        "--quiet",
    ]
    cmd.extend(extra)
    OUT.mkdir(parents=True, exist_ok=True)
    run(cmd)
    with json_out.open("r", encoding="utf-8") as f:
        return json.load(f)


def mvp_suite(rotate: bool = False):
    cases = [
        ("mvp_16_strongsa_k8", [
            "--optics-pack", "configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml",
            "--path-b-sparse-active-k", "8", "--path-b-eval-active-only",
        ]),
        ("mvp_16_lightsa_k4", [
            "--optics-pack", "configs/packs/tmp_codex_optics_medium_voa2_lightSA.yaml",
            "--path-b-sparse-active-k", "4", "--path-b-eval-active-only",
        ]),
        ("mvp_32_strongsa_k8", [
            "--channels", "32",
            "--optics-pack", "configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml",
            "--path-b-sparse-active-k", "8", "--path-b-eval-active-only",
        ]),
        ("mvp_32_strongsa_k16", [
            "--channels", "32",
            "--optics-pack", "configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml",
            "--path-b-sparse-active-k", "16", "--path-b-eval-active-only",
        ]),
    ]
    out = {}
    for label, extra in cases:
        if rotate:
            extra = list(extra) + ["--path-b-sparse-rotate"]
        js = OUT / f"{label}.json"
        res = call_test(js, extra)
        out[label] = {
            "path_b": (res.get("path_b") or {}),
        }
    print(json.dumps(out, indent=2))


def tdm_stability(label: str, optics_pack: str, k: int, epochs: int = 6, trials: int = 240, seed0: int = 11001):
    series = []
    for e in range(epochs):
        seed = seed0 + e
        js = OUT / f"{label}_epoch{e+1}.json"
        extra = [
            "--optics-pack", optics_pack,
            "--path-b-sparse-active-k", str(k), "--path-b-eval-active-only",
            "--seed", str(seed),
            "--trials", str(trials),
        ]
        res = call_test(js, extra)
        pb = res.get("path_b") or {}
        series.append({
            "seed": seed,
            "analog_p50_ber": pb.get("analog_p50_ber"),
            "tdm_symbols_per_s": pb.get("tdm_symbols_per_s"),
        })
    report = {"label": label, "k": k, "epochs": series}
    outp = OUT / f"{label}_stability.json"
    outp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["suite", "stability"])
    ap.add_argument("--optics", default="configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--trials", type=int, default=240)
    ap.add_argument("--label", default="tdm16_strongsa_k8")
    ap.add_argument("--rotate", action="store_true", help="Use deterministic subset rotation in suite")
    args = ap.parse_args()
    if args.mode == "suite":
        mvp_suite(rotate=args.rotate)
    else:
        tdm_stability(args.label, args.optics, args.k, args.epochs, args.trials)
