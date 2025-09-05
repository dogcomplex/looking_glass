from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	fiber = 'configs/packs/overlays/fiber_cband_loop_typ.yaml'
	comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
	tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
	soa = 'configs/packs/overlays/soa_chain_soft.yaml'

	# Model 8 wavelengths as 8 logical channels with near-zero crosstalk
	# Sweep per-\u03bb VOAs (mask proxy), window, and depth=2..4
	for w in ['12.0','16.0','19.0']:
		for d in ['2','3','4']:
			for m in ['0.05','0.09375']:
				label = f"cband_dwdm_tile_w{w.replace('.','p')}_d{d}_avg3_m{m}_s11201"
				cmd = [
					'--trials','700','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input',
					'--classifier','chop','--channels','8','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac', m,
					'--seed','11201','--path-b-analog-depth', d,
				]
				jobs.append({'label': label,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber,'comparator_overlay': comp,'tia_overlay': tia,'optics_pack': soa,'json_out': f"out/{label}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band DWDM tile jobs to {queue}")


if __name__ == '__main__':
	main()
