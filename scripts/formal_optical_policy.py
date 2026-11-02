"""Current user-authored wavefront acceptance limits, separate from optimization."""
import json
import os
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
POLICY_ENV='UV355_FORMAL_POLICY_FILE'

def legacy_limits():
    value=json.loads((ROOT/'formal_optical_limits.json').read_text(encoding='utf-8'))
    value.update(front_divergence_limit_mrad=.5,image_chief_angle_limit_deg=.05,
        S33_air_gap_upper_mm=30.,policy_id='legacy_20261007')
    return value

@lru_cache(maxsize=8)
def _read(path):
    base=legacy_limits()
    if not path:return base
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    authorized={'front_divergence_limit_mrad':1.,'image_chief_angle_limit_deg':.08,'S33_air_gap_upper_mm':32.}
    assert value['policy_id']=='USER_RELAX_THREE_20261017'
    assert all(value[k]==v for k,v in authorized.items())
    if 'image_height_error_limit_mm' in value:
        assert value.get('policy_revision_id')=='USER_HEIGHT_LT15_20261018'
        assert value['image_height_error_limit_mm']==.015
        assert value['image_height_error_strict_upper_bound'] is True
    for key in ('full_field_rms_wfe_limit_waves','on_axis_rms_wfe_limit_waves',
                'optimization_target_waves','optimization_target_is_acceptance_requirement',
                'object_chief_angle_limit_deg'):
        assert value[key]==base[key],(key,'Unapproved change')
    return value

def limits():
    # Opt in per process, so live old controllers retain their original rules.
    return dict(_read(os.environ.get(POLICY_ENV,'')))

def review_limits(review):
    # An old completed review is never silently reinterpreted using new limits.
    value=legacy_limits();value.update(review.get('formal_optical_limits_at_launch',{}))
    return value


def image_height_limit(policy=None):
    value=limits() if policy is None else policy
    return float(value.get('image_height_error_limit_mm',.01))


def image_height_pass(error_mm,policy=None):
    value=limits() if policy is None else policy
    limit=image_height_limit(value)
    return abs(error_mm)<limit if value.get('image_height_error_strict_upper_bound',False) else abs(error_mm)<=limit

def air_cap(surface, policy=None):
    policy=limits() if policy is None else policy
    return float(policy['S33_air_gap_upper_mm']) if surface==33 else 80. if surface in (10,12,24) else 30.
