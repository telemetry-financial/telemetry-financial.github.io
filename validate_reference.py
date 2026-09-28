#!/usr/bin/env python3
"""Validate reference-data.json before it is published (the app runs the same checks on load).

Usage: python3 validate_reference.py NEW.json [OLD.json]
  OLD defaults to the version committed at HEAD. Exits non-zero (and prints why) if anything is off,
  so a bad table never reaches the app. Every rule mirrors _refValidate() in telemetry-financial-2.0.html.
"""
import json, subprocess, sys

def load_old(path):
    if path:
        return json.load(open(path))
    try:
        return json.loads(subprocess.check_output(['git', 'show', 'HEAD:reference-data.json'], stderr=subprocess.DEVNULL))
    except Exception:
        return None

def ratio_ok(n, o, lo, hi):
    return (n >= 0) if not o else lo <= n / o <= hi

def main():
    new = json.load(open(sys.argv[1]))
    old = load_old(sys.argv[2] if len(sys.argv) > 2 else None)
    errs = []
    if new.get('schema') != 1:
        errs.append('schema must be 1')
    mp = new.get('milPay', {})
    rows, yos = mp.get('rows', {}), mp.get('yos', [])
    if yos != [0,2,3,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40]:
        errs.append('milPay.yos changed')
    grades = ['E1','E2','E3','E4','E5','E6','E7','E8','E9','W1','W2','W3','W4','W5','O1','O2','O3','O4','O5','O6','O7','O8','O9','O10','O1E','O2E','O3E']
    for g in grades:
        r = rows.get(g)
        if not isinstance(r, list) or len(r) != 22:
            errs.append(f'milPay {g} missing or wrong length'); continue
        prev = 0
        for i, v in enumerate(r):
            if not isinstance(v, (int, float)) or v < 0:
                errs.append(f'milPay {g}[{i}] bad value'); continue
            if v and v < prev - 0.001:
                errs.append(f'milPay {g} decreases at column {i}')
            if v: prev = v
    va = new.get('va', {}).get('rates', {})
    for st in ['alone', 'spouse', 'spouse_child', 'child']:
        t = va.get(st, {})
        vals = [t.get(str(r)) for r in range(0, 101, 10)]
        if any(v is None for v in vals):
            errs.append(f'va {st} missing ratings'); continue
        if any(b < a for a, b in zip(vals, vals[1:])):
            errs.append(f'va {st} not ascending')
    if old:
        if mp.get('effective', '') > old['milPay']['effective']:
            raise_pct = mp.get('raisePct')
            for g in grades:
                for i, (n, o) in enumerate(zip(rows.get(g, []), old['milPay']['rows'].get(g, []))):
                    if n and o and not ratio_ok(n, o, 0.995, 1.15):
                        errs.append(f'milPay {g}[{i}] moved {100*(n/o-1):.1f}%')
                    if n and o and raise_pct is not None and abs(n - o * (1 + raise_pct / 100)) > 1.0:
                        errs.append(f'milPay {g}[{i}] {n} != old {o} x {1+raise_pct/100:.3f} (±$1)')
        elif mp != old.get('milPay'):
            errs.append('milPay changed without a newer effective date')
        if new.get('va', {}).get('effective', '') > old['va']['effective']:
            for st, t in va.items():
                for r, v in t.items():
                    o = old['va']['rates'][st][r]
                    if o and not ratio_ok(v, o, 0.995, 1.15):
                        errs.append(f'va {st} {r}% out of range')
        if new.get('bas', {}).get('effective', '') > old['bas']['effective']:
            for k in ('officer', 'enlisted'):
                if not ratio_ok(new['bas'][k], old['bas'][k], 0.995, 1.15):
                    errs.append(f'bas {k} out of range')
        if int(new.get('irs', {}).get('year', 0)) > int(old['irs']['year']):
            for k, o in old['irs'].items():
                if isinstance(o, (int, float)) and k != 'year':
                    n = new['irs'].get(k)
                    if not (isinstance(n, (int, float)) and o <= n <= o * 1.25):
                        errs.append(f'irs {k} out of range')
    ra = new.get('raises', {}).get('history', {})
    for y, v in ra.items():
        if not (y.isdigit() and isinstance(v, (int, float)) and 0 <= v <= 15):
            errs.append(f'raises {y} invalid')
    if old and old.get('raises'):
        for y, v in old['raises']['history'].items():
            if ra.get(y) != v:
                errs.append(f'raises {y} changed or removed (history is append-only)')
        if mp.get('effective', '') > old['milPay']['effective']:
            yr = mp['effective'][:4]
            if mp.get('raisePct') is not None and ra.get(yr) != mp.get('raisePct'):
                errs.append(f'raises[{yr}] must equal milPay.raisePct')
    if errs:
        print('INVALID:\n  ' + '\n  '.join(errs[:40]))
        sys.exit(1)
    print('OK: reference-data.json passes every check')

if __name__ == '__main__':
    main()
