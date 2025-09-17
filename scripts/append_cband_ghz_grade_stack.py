from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	opt_ultra = 'configs/packs/overlays/optics_harsher_nonlinear_ultra.yaml'
	soa_fast = 'configs/packs/overlays/soa_fast_tau.yaml'
	tia_fast = 'configs/packs/overlays/tia_bw_3000mhz_slew.yaml'
	clk_10 = 'configs/packs/overlays/clock_jitter_20ps.yaml'  # keep 20 ps; sub-ns will show sensitivity
	comp = 'configs/packs/overlays/comparator_jitter_15ps.yaml'

	weak_cal = ['--classifier','chop','--normalize-dv','--normalize-eps-v','2e-2','--avg-frames','2','--apply-calibration','--no-adaptive-input']

	for win in [1.5, 1.2, 1.0, 0.8]:
		lab = f'ghz_stack_edfa8_w{str(win).replace(".","p")}ns'
		cmd = ['--trials','600','--light-output','--channels','8','--base-window-ns',str(win),'--seed','27101','--path-b-analog-depth','12'] + weak_cal
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ultra,'optics_pack': soa_fast,'comparator_overlay': comp,'clock_pack': clk_10,'tia_overlay': tia_fast,'json_out': f"out/{lab}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} GHz-grade stack tests to {queue}")


if __name__ == '__main__':
	main()





