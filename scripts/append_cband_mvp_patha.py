from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	fiber = 'configs/packs/overlays/fiber_cband_loop_typ.yaml'
	recv = 'configs/packs/overlays/receiver_ingaas_typ.yaml'
	comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
	tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

	for w in ['12.0','16.0','19.0','24.0']:
		for avg in ['2','3']:
			label = f"cband_mvp_patha_w{w.replace('.','p')}_avg{avg}_m0.09375_s11001"
			cmd = [
				'--trials','800','--no-sweeps','--light-output','--apply-calibration',
				'--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
				'--classifier','chop','--channels','1','--base-window-ns', w,'--avg-frames', avg,
				'--mask-bad-frac','0.09375','--seed','11001','--gate-thresh-mV','0.6','--gate-extra-frames','1',
			]
			jobs.append({'label': label,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber,'sensor_pack': recv,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band MVP Path A jobs to {queue}")


if __name__ == '__main__':
	main()
