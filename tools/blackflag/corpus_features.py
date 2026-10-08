#!/usr/bin/env python3
"""Overnight corpus feature pass for BF4 RE.

Parses the mass-decompiled C corpus (bf4_re/sp_src, bf4_re/mp_src) into:
  features_{tag}.tsv   per-function: size, callee/string counts, samples
  strings_{tag}.tsv    string -> function  (distinctive literals)
  callers_{tag}.tsv    callee -> caller count (most-called first)
  propnames_{tag}.tsv  proposed names for string-anchored functions
  cross_sp_mp.tsv      SP<->MP function pairs matched by shared strings (>=2)
  summary.txt
"""
import os
import re
import csv
import collections

ROOTS = {
    "sp": r"C:\Users\Administrator\bf4_re\sp_src",
    "mp": r"C:\Users\Administrator\bf4_re\mp_src",
}
OUT = r"C:\Users\Administrator\bf4_re\analysis"
os.makedirs(OUT, exist_ok=True)

HDR = re.compile(r'^// ==== (\S+) @ ([0-9a-fA-F]+) ====\s*$', re.M)
CALL = re.compile(r'\bFUN_([0-9a-fA-F]{6,8})\b')
STR = re.compile(r'L?"((?:[^"\\\n]|\\.){3,60})"')

FAMILIES = ("M2R_", "S2C_", "C2S_", "M2All_", "D2M_", "M2D_", "M2A_", "Job", "On", "Get", "Set")


def scrub(s):
    return s.replace("\\n", " ").replace("\\t", " ").replace("\\r", " ").strip()


def suggested_name(strs):
    ident = [s for s in strs if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{4,47}", s)]
    for p in FAMILIES:
        for s in ident:
            if s.startswith(p):
                return s
    cands = [s for s in ident if ("_" in s or (s[0].isupper() and any(c.isupper() for c in s[1:])))]
    if cands:
        return min(cands, key=len)
    return ""


def parse_root(tag, root):
    files = sorted(f for f in os.listdir(root) if f.startswith("part_") and f.endswith(".c"))
    str2funcs = collections.defaultdict(set)
    callees_all = collections.Counter()
    n_funcs = 0
    n_named = 0
    with open(os.path.join(OUT, f"features_{tag}.tsv"), "w", newline="", encoding="utf-8") as ff, \
         open(os.path.join(OUT, f"strings_{tag}.tsv"), "w", newline="", encoding="utf-8") as fs, \
         open(os.path.join(OUT, f"propnames_{tag}.tsv"), "w", newline="", encoding="utf-8") as fp:
        wf = csv.writer(ff, delimiter="\t")
        ws = csv.writer(fs, delimiter="\t")
        wp = csv.writer(fp, delimiter="\t")
        wf.writerow(["func", "file", "lines", "n_callees", "n_strings", "callees", "strings"])
        wp.writerow(["func", "suggested", "evidence"])
        for i, fn in enumerate(files):
            with open(os.path.join(root, fn), "r", encoding="utf-8", errors="replace") as fh:
                buf = fh.read()
            parts = HDR.split(buf)
            for j in range(1, len(parts) - 2, 3):
                name = parts[j]
                body = parts[j + 2]
                callees = {"FUN_" + m for m in CALL.findall(body)}
                strs = {scrub(s) for s in STR.findall(body)}
                strs = {s for s in strs if len(s) >= 4}
                wf.writerow([name, fn, body.count("\n") + 1, len(callees), len(strs),
                             ",".join(sorted(callees)[:12]), " | ".join(sorted(strs, key=len)[:8])])
                for s in strs:
                    ws.writerow([s, name])
                    str2funcs[s].add(name)
                callees_all.update(callees)
                sn = suggested_name(strs)
                if sn:
                    wp.writerow([name, sn, " | ".join(sorted(strs, key=len)[:4])])
                    n_named += 1
                n_funcs += 1
            if (i + 1) % 50 == 0:
                print(f"{tag}: {i+1}/{len(files)} files, {n_funcs} funcs", flush=True)
    with open(os.path.join(OUT, f"callers_{tag}.tsv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["callee", "n_callers"])
        for c, n in callees_all.most_common():
            w.writerow([c, n])
    print(f"{tag}: DONE {n_funcs} functions, {n_named} name proposals, "
          f"{len(str2funcs)} distinct strings", flush=True)
    return n_funcs, n_named, str2funcs


def main():
    summary = []
    maps = {}
    for tag, root in ROOTS.items():
        if not os.path.isdir(root):
            print(f"skip {tag}: no {root}")
            continue
        n_funcs, n_named, str2funcs = parse_root(tag, root)
        maps[tag] = str2funcs
        summary.append(f"{tag}: funcs={n_funcs} name_proposals={n_named} strings={len(str2funcs)}")

    if "sp" in maps and "mp" in maps:
        sp, mp = maps["sp"], maps["mp"]
        pair = collections.Counter()
        shared = set(sp) & set(mp)
        for s in shared:
            if len(s) < 6:
                continue
            for a in sp[s]:
                for b in mp[s]:
                    pair[(a, b)] += 1
        with open(os.path.join(OUT, "cross_sp_mp.tsv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["sp_func", "mp_func", "shared_strings"])
            kept = 0
            for (a, b), n in pair.most_common():
                if n >= 2:
                    w.writerow([a, b, n])
                    kept += 1
        summary.append(f"cross pairs (>=2 shared strings): {kept}  (of {len(pair)} candidate pairs)")
    with open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
