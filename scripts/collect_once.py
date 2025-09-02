import sys
import time
import json
from pathlib import Path


def print_one_result(json_path: Path) -> int:
    # Wait up to 15s for the file
    for _ in range(15):
        if json_path.exists():
            break
        time.sleep(1)
    if not json_path.exists():
        print(f"MISSING {json_path}")
        return 1
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERR reading {json_path}: {e}")
        return 1
    cfg = data.get("config") or {}
    base_cal = data.get("baseline_calibrated") or {}
    pa = data.get("path_a") or {}
    print(
        "file=", json_path,
        "win=", cfg.get("base_window_ns"),
        "base_cal.p50_ber=", base_cal.get("p50_ber"),
        "path_a.p50_ber=", pa.get("p50_ber"),
    )
    return 0


def print_completed(after_sig: str | None = None,
                    match_sub: str | None = None,
                    limit: int | None = None,
                    unique: bool = True,
                    csv: bool = False,
                    include_errors: bool = False) -> int:
    comp_path = Path('queue/completed.jsonl')
    if not comp_path.exists():
        print(f"MISSING {comp_path}")
        return 1
    lines = comp_path.read_text(encoding='utf-8').splitlines()
    started = (after_sig is None)
    count = 0
    seen: set[tuple[str, str]] = set()
    if csv:
        print("sig8,out,win,base_cal_p50_ber,path_a_p50_ber")
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        sig = str(rec.get('signature') or '')
        outp = str(rec.get('out') or '')
        summ = rec.get('summary') or {}
        # Skip incomplete/error records unless requested
        if not include_errors and (not outp or not isinstance(summ, dict) or 'path_a_p50_ber' not in summ):
            continue
        if not started:
            if sig.startswith(after_sig):
                started = True
            continue
        if match_sub and (match_sub not in outp):
            continue
        key = (sig, outp)
        if unique and key in seen:
            continue
        seen.add(key)
        if csv:
            print(
                f"{sig[:8]},{outp},{summ.get('base_window_ns')},{summ.get('baseline_calibrated_p50_ber')},{summ.get('path_a_p50_ber')}"
            )
        else:
            print(
                "sig=", sig[:8],
                "out=", outp,
                "win=", summ.get('base_window_ns'),
                "base_cal.p50_ber=", summ.get('baseline_calibrated_p50_ber'),
                "path_a.p50_ber=", summ.get('path_a_p50_ber'),
            )
        count += 1
        if limit is not None and count >= limit:
            break
    return 0


def main():
    # Modes:
    # 1) collect_once.py out/<file>.json  -> summarize one JSON
    # 2) collect_once.py                  -> dump all completed.jsonl shorthand
    #    optional: --after SIG_PREFIX  --match SUBSTR  --limit N  [--no-unique] [--csv] [--include-errors]
    if len(sys.argv) >= 2 and sys.argv[1].endswith('.json'):
        sys.exit(print_one_result(Path(sys.argv[1])))

    after_sig = None
    match_sub = None
    limit = None
    args = sys.argv[1:]
    i = 0
    unique = True
    csv = False
    include_errors = False
    while i < len(args):
        a = args[i]
        if a == '--after' and i+1 < len(args):
            after_sig = args[i+1]
            i += 2
        elif a == '--match' and i+1 < len(args):
            match_sub = args[i+1]
            i += 2
        elif a == '--limit' and i+1 < len(args):
            try:
                limit = int(args[i+1])
            except ValueError:
                limit = None
            i += 2
        elif a == '--no-unique':
            unique = False
            i += 1
        elif a == '--csv':
            csv = True
            i += 1
        elif a == '--include-errors':
            include_errors = True
            i += 1
        else:
            i += 1
    sys.exit(print_completed(after_sig=after_sig, match_sub=match_sub, limit=limit, unique=unique, csv=csv, include_errors=include_errors))


if __name__ == "__main__":
    main()


