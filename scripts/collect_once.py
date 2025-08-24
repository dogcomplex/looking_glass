import sys
import time
import json
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/collect_once.py out/<file>.json")
        sys.exit(2)
    target = Path(sys.argv[1])
    # Wait up to 15s for the file
    for _ in range(15):
        if target.exists():
            break
        time.sleep(1)
    if not target.exists():
        print(f"MISSING {target}")
        sys.exit(1)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERR reading {target}: {e}")
        sys.exit(1)
    cfg = data.get("config") or {}
    base_cal = data.get("baseline_calibrated") or {}
    pa = data.get("path_a") or {}
    print("file=", target, "win=", cfg.get("base_window_ns"), "base_cal.p50_ber=", base_cal.get("p50_ber"), "path_a.p50_ber=", pa.get("p50_ber"))


if __name__ == "__main__":
    main()


