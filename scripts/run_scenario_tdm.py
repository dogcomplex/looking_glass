import json
import subprocess
from pathlib import Path


def load_yaml_or_json(path: str) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except Exception:
        try:
            return json.loads(text)
        except Exception:
            # very simple key: value parser
            out = {}
            for line in text.splitlines():
                s = line.strip()
                if not s or s.startswith('#') or ':' not in s:
                    continue
                k, v = s.split(':', 1)
                out[k.strip()] = v.strip().strip("\"'")
            return out


def build_cmd_from_scenario(scn: dict, json_out: Path, *, k: int, rotate: bool, trials: int | None = None) -> list[str]:
    py = str((Path(__file__).resolve().parents[1] / '.venv' / 'Scripts' / 'python.exe'))
    test = str((Path(__file__).resolve().parents[1] / 'examples' / 'test.py'))
    cmd = [
        py, test,
        '--trials', str(trials if trials is not None else int(scn.get('trials', 240))),
        '--channels', str(int(scn.get('channels', 16))),
        '--base-window-ns', str(float(scn.get('window_ns', 10.0))),
        '--classifier', 'chop', '--avg-frames', '2', '--apply-calibration', '--no-adaptive-input', '--no-cold-input', '--no-sweeps',
        '--normalize-dv', '--path-b-depth', '5', '--path-b-analog-depth', '5', '--path-b-balanced',
        '--path-b-calibrate-vth', '--path-b-calibrate-vth-scale', '0.5', '--path-b-calibrate-vth-passes', '64',
        '--path-b-stage-gains-db', '2.0,1.0,0,-0.25,-0.25', '--path-b-vth-schedule', '12,12,8,6,5',
        '--json', str(json_out), '--quiet',
        '--path-b-sparse-active-k', str(int(k)), '--path-b-eval-active-only',
    ]
    if rotate:
        cmd.append('--path-b-sparse-rotate')

    # Map packs
    packs = {
        'emitter_pack': '--emitter-pack',
        'optics_pack': '--optics-pack',
        'sensor_pack': '--sensor-pack',
        'tia_pack': '--tia-pack',
        'comparator_pack': '--comparator-pack',
        'clock_pack': '--clock-pack',
        'thermal_pack': '--thermal-pack',
    }
    for key, flag in packs.items():
        val = scn.get(key)
        if isinstance(val, dict) and 'path' in val:
            val = val['path']
        if isinstance(val, str) and val.strip():
            cmd += [flag, val.strip()]
    return cmd


def run_cmd(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr)
        raise SystemExit(p.returncode)
    # The JSON is written to file; return {}
    return {}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario', help='Scenario YAML path')
    ap.add_argument('--k', type=int, default=8)
    ap.add_argument('--rotate', action='store_true')
    ap.add_argument('--trials', type=int, default=None)
    ap.add_argument('--json', type=str, default=None)
    args = ap.parse_args()

    scn = load_yaml_or_json(args.scenario)
    out_path = Path(args.json or (Path('out') / 'scenario_tdm.json'))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_cmd_from_scenario(scn, out_path, k=args.k, rotate=bool(args.rotate), trials=args.trials)
    print('RUN:', ' '.join(cmd))
    run_cmd(cmd)
    print('WROTE:', str(out_path))


if __name__ == '__main__':
    main()

