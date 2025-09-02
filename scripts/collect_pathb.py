from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    out_dir = Path('out')
    rows = []
    for p in sorted(out_dir.glob('*.json')):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        label = p.stem
        cfg = data.get('config') or {}
        path_b = data.get('path_b') or {}
        path_b_p50 = path_b.get('p50_ber')
        path_a_p50 = (data.get('path_a') or {}).get('p50_ber')
        base_p50 = (data.get('baseline') or {}).get('p50_ber')
        if path_b_p50 is not None:
            rows.append((label, cfg.get('base_window_ns'), base_p50, path_a_p50, path_b_p50))
    # Print concise summary
    print('label,window_ns,baseline_p50,path_a_p50,path_b_p50')
    for r in rows:
        print(','.join(str(x) for x in r))


if __name__ == '__main__':
    main()


