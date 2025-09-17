from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)
	jobs: list[dict] = []
	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	edfa = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	opt_ultra = 'configs/packs/overlays/optics_harsher_nonlinear_ultra.yaml'
	clk_20 = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	cj_15 = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	tia_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'
	tweak_cal = ['--classifier','chop','--normalize-dv','--normalize-eps-v','2e-2','--avg-frames','2','--apply-calibration','--no-adaptive-input']
	for dlam_nm in [0.2, 0.4, 0.6, 1.0]:
		lab = f'cband_lramps_edfa8_w6p0ns_dlam{str(dlam_nm).replace(".","p")}nm'
		cmd = ['--trials','600','--light-output','--channels','8','--base-window-ns','6.0','--seed','24101','--path-b-analog-depth','12'] + tweak_cal
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ultra,'optics_pack': edfa,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})
	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} lambda drift tests to {queue}")


if __name__ == '__main__':
	main()




