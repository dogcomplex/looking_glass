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
	recv_typ = 'configs/packs/overlays/receiver_ingaas_typ.yaml'
	recv_low = 'configs/packs/overlays/receiver_ingaas_lowbw.yaml'
	soa_stress = 'configs/packs/overlays/soa_chain_stress.yaml'
	edfa_stress = 'configs/packs/overlays/edfa_chain_stress.yaml'
	dwdm_imp = 'configs/packs/overlays/dwdm_crosstalk_ripple.yaml'

	# Shorter windows for GHz push; deeper loops; impairments overlays
	windows = ['8.0','10.0','12.0']
	depths = ['2','3','4','6','8']
	masks = ['0.05','0.09375']

	for w in windows:
		for d in depths:
			for m in masks:
				# SOA stress
				lab = f"cband_real_soa_d{d}_w{w.replace('.','p')}_avg3_m{m}_s11301"
				cmd = ['--trials','700','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','1','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac', m,'--seed','11301','--path-b-analog-depth', d]
				jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber,'optics_pack': soa_stress,'comparator_overlay': comp,'tia_overlay': tia,'sensor_pack': recv_typ,'json_out': f"out/{lab}.json"})
				# EDFA stress + DWDM impairments + low-BW receiver
				lab2 = f"cband_real_edfa_dwdm_lowrx_d{d}_w{w.replace('.','p')}_avg3_m{m}_s11302"
				cmd2 = ['--trials','700','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','8','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac', m,'--seed','11302','--path-b-analog-depth', d]
				jobs.append({'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': dwdm_imp,'optics_pack': edfa_stress,'comparator_overlay': comp,'tia_overlay': tia,'sensor_pack': recv_low,'json_out': f"out/{lab2}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band realism sweep jobs to {queue}")


if __name__ == '__main__':
	main()
