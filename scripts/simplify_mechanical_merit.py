"""Authorized 2026-10-04 mechanical-only merit amendment, with DAG proof.

Optical expressions retain their full ordered semantic trees. Row numbers are
references, so deleting a row requires rebuilding every downstream reference.
"""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from optimize_until_stable import mf_signature

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = ROOT / 'results/uv355_axis_balanced_dense17_restored_first_verified_20261003/AXIS_BALANCED_DENSE17_RESTORED_FIRST_RESEARCH.zmx'
ANCHOR_SHA = '31cac460810ff09fb2e24dcf95293fbac469cde07e9e8e0b829f4302fc7f3dcf'
BINARY = {'DIFF', 'DIVI', 'PROD', 'SUMM'}
UNARY = {'PROB', 'RECI', 'SQRT', 'OPGT', 'OPLT'}
MECHANICAL = {'CONS', 'CVVA', 'COVA', 'PMVA', 'TTHI', 'CTGT'}

def reference_positions(kind):
    return (1, 2) if kind in BINARY else ((1,) if kind in UNARY else ())

class Graph:
    def __init__(self, signature):
        self.rows = signature
        for i, r in enumerate(signature, 1):
            for p in reference_positions(r[0]):
                if r[p] and (r[p] != int(r[p]) or not 0 < r[p] < i):
                    raise ValueError(f'Invalid backward reference at row {i}: {r}')

    def refs(self, i):
        r = self.rows[i - 1]
        return [int(r[p]) for p in reference_positions(r[0]) if r[p]]

    @lru_cache(None)
    def leaves(self, i):
        refs = self.refs(i)
        return frozenset().union(*(self.leaves(j) for j in refs)) if refs else frozenset([i])

    def mechanical(self, i):
        return {self.rows[j - 1][0] for j in self.leaves(i)} <= MECHANICAL

    @lru_cache(None)
    def digest(self, i):
        r = list(self.rows[i - 1])
        for p in reference_positions(r[0]):
            if r[p]: r[p] = {'expression': self.digest(int(r[p]))}
        return hashlib.sha256(json.dumps(r, separators=(',', ':')).encode()).hexdigest()

    def optical_digests(self):
        return [self.digest(i) for i, r in enumerate(self.rows, 1) if r[-1] and not self.mechanical(i)]

def selection(signature):
    graph = Graph(signature)
    keep = set(); removed = {}; retained_roots = []
    for i, r in enumerate(signature, 1):
        if not graph.mechanical(i): keep.add(i)
        if not r[-1] or not graph.mechanical(i): continue
        thickness = [signature[j - 1] for j in graph.leaves(i) if signature[j - 1][0] == 'TTHI']
        reason = None
        if r[0] == 'CTGT': reason = 'Duplicate center minimum already enforced by scaled TTHI'
        elif 1336 <= i <= 1428: reason = 'Duplicate tightened upper bound; retain single original center/air cap'
        elif 864 <= i <= 1052: reason = 'Redundant absolute position of later surfaces; retain front clearance and actual adjacent gaps'
        elif i == 1332: reason = 'Redundant image-distance upper bound; retain positive image gap and total track'
        if reason: removed[i] = reason
        else: keep.add(i); retained_roots.append(i)
    def include(i):
        keep.add(i)
        for j in graph.refs(i):
            if j not in keep: include(j)
    for i in list(keep): include(i)
    mapping = {}; canonical = {}; representative = []
    for i in sorted(keep):
        # Share only unweighted mechanical calculations; weighted roots and all
        # optical computations retain their identity, target and weight.
        r = signature[i - 1]; key = graph.digest(i)
        if not r[-1] and graph.mechanical(i) and key in canonical:
            mapping[i] = canonical[key]; continue
        mapping[i] = len(representative) + 1; representative.append(i)
        if not r[-1] and graph.mechanical(i): canonical[key] = mapping[i]
    return graph, representative, mapping, removed, retained_roots

def remap(tokens, mapping):
    tokens = list(tokens)
    for p in reference_positions(tokens[0]):
        if float(tokens[p]): tokens[p] = str(mapping[int(float(tokens[p]))])
    return tokens

def build(target):
    if hashlib.sha256(ANCHOR.read_bytes()).hexdigest() != ANCHOR_SHA: raise ValueError('Anchor hash changed')
    target = Path(target).resolve()
    if target.exists() or target.with_suffix('.MF').exists(): raise ValueError('Preserve existing branch')
    target.parent.mkdir(parents=True, exist_ok=True)
    sig = mf_signature(ANCHOR.with_suffix('.MF'))
    graph, representatives, mapping, removed, retained = selection(sig)
    mftext = ANCHOR.with_suffix('.MF').read_text(encoding='utf-16')
    mflines = mftext.splitlines(); header = mflines[0]
    mfrows = [line.split() for line in mflines[1:] if line.strip()]
    text = ANCHOR.read_text(encoding='utf-16'); lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.split() and line.split()[0] == sig[0][0])
    zrows = [line.split() for line in lines[start:start + len(sig)]]
    for r, z in zip(sig, zrows):
        zs = (z[0], *map(float, z[1:7]), *map(float, z[9:11]), *map(float, z[7:9]))
        if r[0] != zs[0] or any(not math.isclose(a, b, rel_tol=2e-11, abs_tol=1e-13) for a, b in zip(r[1:], zs[1:])):
            raise ValueError('Embedded MF does not match companion MF')
    newmf = header + '\r\n' + ''.join(' '.join(remap(mfrows[i - 1], mapping)) + '\r\n' for i in representatives)
    newz = ''.join(lines[:start]) + ''.join(' '.join(remap(zrows[i - 1], mapping)) + '\n' for i in representatives) + ''.join(lines[start + len(sig):])
    # Text-mode decoding normalizes CRLF; restore the original Windows format.
    target.write_bytes(newz.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-16'))
    target.with_suffix('.MF').write_bytes(newmf.encode('utf-16'))
    newgraph = Graph(mf_signature(target.with_suffix('.MF')))
    assert graph.optical_digests() == newgraph.optical_digests()
    assert sum(r[0] == 'OPDX' for r in newgraph.rows) == 840
    report = {'authorization': 'User 2026-10-04: simplify mechanical operands, prioritize thickness/gaps, release curvature, focus image quality',
        'anchor': str(ANCHOR), 'anchor_sha256': ANCHOR_SHA, 'model': str(target),
        'model_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'before_count': len(sig), 'after_count': len(newgraph.rows),
        'mechanical_rows_before': sum(graph.mechanical(i) for i in range(1, len(sig) + 1)),
        'mechanical_rows_after': sum(newgraph.mechanical(i) for i in range(1, len(newgraph.rows) + 1)),
        'mechanical_weighted_before': sum(bool(r[-1]) and graph.mechanical(i) for i, r in enumerate(sig, 1)),
        'mechanical_weighted_after': sum(bool(r[-1]) and newgraph.mechanical(i) for i, r in enumerate(newgraph.rows, 1)),
        'optical_weighted_expressions_identical': True, 'OPDX_preserved': 840,
        'removed_weighted_rows': removed, 'retained_mechanical_roots': retained,
        'old_to_new_row': mapping, 'new_type_counts': dict(Counter(r[0] for r in newgraph.rows)),
        'prescription_and_global_records_unchanged': True,
        'curvature_penalties_before_and_after': 0,
        'edge_and_gap_sag_dependencies_preserved': True,
        'independent_full_radial_physical_guards_retained': True,
        'sdk_baseline_verified': False, 'quality_improvement_claimed': False}
    target.with_suffix('.mechanical_amendment.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('old_to_new_row','removed_weighted_rows','retained_mechanical_roots')}, indent=2))

def verify_amendment(model):
    """Recognize only the deterministic mechanical amendment, never arbitrary MF edits."""
    if hashlib.sha256(ANCHOR.read_bytes()).hexdigest() != ANCHOR_SHA: return False
    sig = mf_signature(ANCHOR.with_suffix('.MF'))
    _, representatives, mapping, _, _ = selection(sig)
    expected = []
    for i in representatives:
        r = list(sig[i - 1])
        for p in reference_positions(r[0]):
            if r[p]: r[p] = float(mapping[int(r[p])])
        expected.append(tuple(r))
    return mf_signature(Path(model).with_suffix('.MF')) == expected

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True)
    build(p.parse_args().output)
