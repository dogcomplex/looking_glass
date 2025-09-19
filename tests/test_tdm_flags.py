from pathlib import Path
import sys
import json
import subprocess


REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]):
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"cmd failed: {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p


def test_scenario_tdm_passthrough_runs(tmp_path: Path):
    out_json = tmp_path / "scenario_tdm_out.json"
    cmd = [
        sys.executable,
        "-m",
        "looking_glass.scenario",
        str(REPO / "configs" / "scenarios" / "tdm_16_lightsa_k4.yaml"),
        "--trials",
        "60",
        "--tdm-k",
        "4",
        "--tdm-eval-active-only",
        "--json",
        str(out_json),
    ]
    _run(cmd)
    assert out_json.exists(), "scenario TDM JSON was not created"
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and (data.get("path_b") is not None)
    assert (data["path_b"].get("analog_p50_ber") is not None)


def test_sparse_rotate_smoke(tmp_path: Path):
    out_json = tmp_path / "tdm_rotate_out.json"
    cmd = [
        sys.executable,
        str(REPO / "examples" / "test.py"),
        "--trials",
        "60",
        "--channels",
        "16",
        "--base-window-ns",
        "10",
        "--classifier",
        "chop",
        "--avg-frames",
        "2",
        "--apply-calibration",
        "--no-adaptive-input",
        "--no-cold-input",
        "--no-sweeps",
        "--emitter-pack",
        "configs/packs/tmp_lowcost_emitter_boost.yaml",
        "--optics-pack",
        "configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml",
        "--sensor-pack",
        "configs/packs/overlays/receiver_ingaas_typ.yaml",
        "--tia-pack",
        "configs/packs/overlays/tia_stage_b2_low_noise.yaml",
        "--comparator-pack",
        "configs/packs/overlays/tuned_comparator.yaml",
        "--clock-pack",
        "configs/packs/overlays/clock_jitter_20ps.yaml",
        "--normalize-dv",
        "--path-b-depth",
        "5",
        "--path-b-analog-depth",
        "5",
        "--path-b-balanced",
        "--path-b-calibrate-vth",
        "--path-b-calibrate-vth-scale",
        "0.5",
        "--path-b-calibrate-vth-passes",
        "32",
        "--path-b-stage-gains-db",
        "2.0,1.0,0,-0.25,-0.25",
        "--path-b-vth-schedule",
        "12,12,8,6,5",
        "--path-b-sparse-active-k",
        "4",
        "--path-b-eval-active-only",
        "--path-b-sparse-rotate",
        "--json",
        str(out_json),
        "--quiet",
    ]
    _run(cmd)
    data = json.loads(out_json.read_text(encoding="utf-8"))
    pb = data.get("path_b") or {}
    assert pb.get("analog_p50_ber") is not None
    # Ensure throughput metrics exist in sparse mode
    assert pb.get("tdm_symbols_per_s") is not None

