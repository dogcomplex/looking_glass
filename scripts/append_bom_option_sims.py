from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Curated BOM tiers (budget/mid/lab) using vendor packs
    tiers = [
        (
            'budget',
            'configs/packs/vendors/emitters/ushio_HL8518MG_typ.yaml',
            'configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-10°_typ.yaml',
            'configs/packs/vendors/sensors/vishay_BPW34_typ.yaml',
            'configs/packs/vendors/tias/texas_instruments_OPA857EVM_typ.yaml',
            'configs/packs/vendors/comparators/texas_instruments_TLV3501_typ.yaml',
        ),
        (
            'mid',
            'configs/packs/vendors/emitters/thorlabs_L850P200_typ.yaml',
            'configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-5°_typ.yaml',
            'configs/packs/vendors/sensors/thorlabs_FDS1010_typ.yaml',
            'configs/packs/vendors/tias/thorlabs_TIA60_typ.yaml',
            'configs/packs/vendors/comparators/analog_devices_LTC6752_typ.yaml',
        ),
        (
            'lab',
            'configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml',
            'configs/packs/vendors/optics/thorlabs_Engineered-Diffuser-3°_typ.yaml',
            'configs/packs/vendors/sensors/thorlabs_FDS1010_typ.yaml',
            'configs/packs/vendors/tias/femto_DLPCA-200_typ.yaml',
            'configs/packs/vendors/comparators/analog_devices_LTC6752_typ.yaml',
        ),
    ]

    windows = ['18.95','19.00','19.05']
    for tag, emit, optx, sensor, tia, comp in tiers:
        for ch in ['8','16']:
            for w in windows:
                label = f"bom_{tag}_ch{ch}_w{w.replace('.','p')}_avg3_m0.09375_s10401_g0p6e1"
                cmd = [
                    '--trials','1000','--no-sweeps','--light-output','--apply-calibration',
                    '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                    '--classifier','chop','--channels', ch,'--base-window-ns', w,'--avg-frames','3',
                    '--mask-bad-frac','0.09375','--seed','10401','--gate-thresh-mV','0.6','--gate-extra-frames','1',
                ]
                jobs.append({
                    'label': label,
                    'cmd': cmd,
                    'emitter_pack': emit,
                    'optics_pack': optx,
                    'sensor_pack': sensor,
                    'tia_pack': tia,
                    'comparator_pack': comp,
                    'json_out': f"out/{label}.json",
                })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} curated BOM option jobs to {queue}")


if __name__ == '__main__':
    main()


