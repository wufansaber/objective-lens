"""Add measured near-axis spot ordering to the unchanged R943 native runtime."""
import numpy as np
import uv355_focal_runtime_R944_20261102 as original
from uv355_batched_boundary_and_ordering_R741_20261101 import measure

method = original.method
policy = original.policy
vector = original.vector
POINTS = [dict(method='RECT32', wave=2, radius_normalized=r, azimuth_deg=a)
          for r in (0., .005, .015625) for a in ((0.,) if not r else (0., 45.))]
LABELS = [f'nearaxis_spot_coefficient_{p["radius_normalized"]}_{p["azimuth_deg"]}' for p in POINTS[1:]]


def coefficient(airy):
    """Positive sign is exactly equivalent to Airy(r) >= Airy(axis)."""
    return np.asarray([(airy[i]**2-airy[0]**2)/(.01*p['radius_normalized']**2)
                       for i, p in enumerate(POINTS[1:], 1)])


def context(system, api, bridge, source, out, state, save, active):
    raw, apply, initial, scales, variables, template, signature, chart, points, color = original.context(
        system, api, bridge, source, out, state, save, active)

    def measure_near(y):
        active()
        apply(y)
        wf, airy = measure(system, api, bridge, POINTS)
        return coefficient(airy)

    def evaluate(y):
        value = raw(y)
        near = measure_near(y)
        value.update(optical=np.r_[value['optical'], near],
                     optical_labels=value['optical_labels']+LABELS,
                     nearaxis_spot_coefficients=near)
        state['nearaxis_spot_coefficients'] = near.tolist()
        save()
        return value

    evaluate.measure_near = measure_near
    return evaluate, apply, initial, scales, variables, template, signature, chart, points, color
