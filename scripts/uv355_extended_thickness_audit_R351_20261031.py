"""Apply the authorized estimated band without editing legacy audited evidence."""
from pathlib import Path
import numpy as np

from atomic_progress import read_json_retry as read
from run_uv355_multistart_campaign import sha
from physical_prescription_audit import audit as legacy_audit, parse_model, sag

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'results/uv355_authorized_extended_thickness_R350_20261031/AUTHORIZED_DERIVED_THICKNESS_POLICY.json'


def audit(path, samples=2049, acceptance=None):
    policy = read(POLICY)
    assert sha(policy['source_table']) == policy['source_table_sha256']
    report = legacy_audit(path, samples=samples, acceptance=acceptance)
    _, _, surfaces = parse_model(path)
    original_issues = list(report['issues'])
    applied = []
    for lens in report['lenses']:
        diameter = 2. * lens['radius_mm']
        if not policy['diameter_lower_exclusive_mm'] < diameter <= policy['diameter_upper_inclusive_mm']:
            continue
        assert lens['required_center_mm'] is None and lens['required_radial_min_mm'] is None
        front, rear = surfaces[lens['front']], surfaces[lens['front'] + 1]
        rr = np.linspace(0., lens['radius_mm'], samples)
        thickness = front['thickness'] + sag(rear, rr) - sag(front, rr)
        assert abs(float(thickness.min()) - lens['minimum_mm']) < 1e-11
        assert abs(float(thickness[-1]) - lens['edge_mm']) < 1e-11
        issue = f"Thickness band unavailable for S{lens['front']} diameter {diameter}"
        assert issue in report['issues']
        report['issues'].remove(issue)
        lens.update(required_center_mm=policy['minimum_center_mm'],
            required_radial_min_mm=policy['minimum_full_radial_thickness_mm'],
            passed=bool(front['thickness'] >= policy['minimum_center_mm'] - 1e-7
                and float(thickness.min()) >= policy['minimum_full_radial_thickness_mm'] - 1e-7
                and front['thickness'] <= policy['maximum_center_mm'] + 1e-7),
            estimated_band_policy_id=policy['id'], diameter_mm=diameter)
        applied.append(lens['front'])
    expected_lenses = sum(bool(s.get('glas')) for s in surfaces.values())
    report['passed'] = bool(len(report['lenses']) == expected_lenses
        and all(r['passed'] for r in report['lenses'])
        and all(r['passed'] for r in report['gaps'])
        and report.get('first_two_lens_common_contact_ring', {}).get('passed', True)
        and not report['issues'] and report['work_clearance_mm'] > 4. and report['track_mm'] <= 900.)
    report['authorized_estimated_thickness_rule'] = dict(policy=str(POLICY), policy_sha256=sha(POLICY),
        applied_lens_fronts=applied, original_issues=original_issues,
        original_rules_at_or_below80_unchanged=True,
        full_radial_thickness_calculated_from_both_actual_surface_sags=True,
        manufacturing_release_or_stress_certification=False)
    return report


def install():
    import physical_prescription_audit
    assert physical_prescription_audit.audit in (legacy_audit, audit)
    physical_prescription_audit.audit = audit
