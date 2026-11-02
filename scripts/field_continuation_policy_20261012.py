"""Explicit field continuation only; final 4 mm requirements stay unchanged."""
import re
from pathlib import Path
from physical_prescription_audit import parse_model
from optimize_until_stable import mf_signature
from prepare_uv355_4mm_20261005 import SEED, DRAFT, sha
from object_telecentric_policy import revised_signature, revise


def radius(model):
    text = parse_model(model)[1]
    row = next(line for line in text.splitlines() if line.startswith('YFLN '))
    values = list(map(float, row.split()[1:]))
    assert len(values) == 5 and values[0] == 0
    extent = values[-1]
    assert any(abs(extent - x) < 1e-12 for x in (1.5, 1.6, 1.7, 1.8, 1.9, 2.0))
    assert all(abs(v - extent*i/4) < 1e-12 for i, v in enumerate(values))
    return extent


def expected_merit(extent):
    rows = [list(r) for r in revised_signature(mf_signature(DRAFT.with_suffix('.MF')))]
    for index, target in ((861, -500*extent-1), (862, -500*extent+1),
                          (865, -1000*extent-1), (866, -1000*extent+1)):
        rows[index-1][9] = target
    return [tuple(r) for r in rows]


def invariants(model):
    _, text, surfaces = parse_model(model)
    _, original_text, original = parse_model(SEED)
    def records(txt, key):
        return [line.split()[1:] for line in txt.splitlines() if line.startswith(key+' ')]
    extent = radius(model)
    keys = ('FTYP','XFLN','FWGN','VDXN','VDYN','VCXN','VCYN','VANN','WAVM','OBNA','RAIM','GCAT')
    checks = {key: records(text,key)==records(original_text,key) for key in keys}
    actual=mf_signature(Path(model).with_suffix('.MF'));expected=expected_merit(extent)
    from uv355_three_limit_merit_20261017 import revised_signature as three_limit_signature
    checks['authorized_field_merit_only'] = actual==expected or actual==three_limit_signature(expected)
    from formal_optical_policy import limits as current_formal_limits
    if current_formal_limits().get('policy_revision_id')=='USER_HEIGHT_LT15_20261018':
        from uv355_height15_merit_revision_20261018 import revised_signature as height_signature
        checks['authorized_field_merit_only'] = checks['authorized_field_merit_only'] or actual==height_signature(three_limit_signature(expected))
    aspheres = [sn for sn,s in surfaces.items() if s.get('type')=='EVENASPH']
    checks.update(aspheres_original=aspheres==[2,10,20,22],
        original_A2=all(surfaces[sn]['parameters'].get(1,0.)==original[sn]['parameters'].get(1,0.) for sn in aspheres),
        higher_than_A10_zero=all(v==0. for sn in aspheres for k,v in surfaces[sn]['parameters'].items() if k>5),
        materials_original={sn:s.get('glas') for sn,s in surfaces.items() if s.get('glas')}=={sn:s.get('glas') for sn,s in original.items() if s.get('glas')},
        types_original={sn:s.get('type') for sn,s in surfaces.items()}=={sn:s.get('type') for sn,s in original.items()})
    return dict(model=str(model),sha256=sha(model),checks=checks,static_invariants_pass=all(checks.values()),
        object_circle_diameter_mm=2*extent,full_4mm_design_accepted=False,
        intermediate_field_only=extent<2.,original_4mm_hard_limits_unchanged=True)


def prepare(source, destination, extent):
    source, destination = Path(source), Path(destination)
    assert not destination.exists() and not destination.with_suffix('.MF').exists()
    old_radius = radius(source)
    assert old_radius <= extent <= 2.
    raw,text,surfaces = parse_model(source)
    text = re.sub(r'(?m)^YFLN [^\r\n]*', 'YFLN '+' '.join(format(extent*i/4,'.15g') for i in range(5)), text)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(text.encode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8'))
    revise(source.with_suffix('.MF'),destination.with_suffix('.MF'))
    rows = destination.with_suffix('.MF').read_text(encoding='utf-16').splitlines()
    desired = expected_merit(extent)
    index = 0
    for n,line in enumerate(rows):
        parts=line.split()
        if len(parts)<11 or parts[0]=='VERS':continue
        index+=1
        if index in (861,862,865,866):
            parts[9]=format(desired[index-1][9],'.15g');rows[n]=' '.join(parts)
    destination.with_suffix('.MF').write_text('\n'.join(rows)+'\n',encoding='utf-16')
    # Keep the saved lens's embedded merit function consistent with its sidecar.
    # OpticStudio LoadFile reads the embedded rows before any explicit MF load.
    old_merit=mf_signature(source.with_suffix('.MF'))
    new_merit=mf_signature(destination.with_suffix('.MF'))
    lines=text.splitlines();starts=[]
    for start,line in enumerate(lines):
        parts=line.split()
        if len(parts)<9 or parts[0]!=old_merit[0][0]:continue
        try:
            if len(lines[start:start+len(old_merit)])!=len(old_merit):continue
            for saved,old in zip(lines[start:start+len(old_merit)],old_merit):
                bits=saved.split();assert bits[0]==old[0]
                actual=list(map(float,bits[1:9]));expected=list(old[1:7])+list(old[9:11])
                assert len(actual)==8 and all(abs(a-b)<=1e-11*max(1.,abs(b)) for a,b in zip(actual,expected))
            starts.append(start)
        except (AssertionError,ValueError):continue
    assert len(starts)==1,('Embedded source MF does not match sidecar',starts)
    start=starts[0];changed=[]
    for i,(old,new) in enumerate(zip(old_merit,new_merit)):
        if old==new:continue
        columns=[j for j in range(11) if old[j]!=new[j]]
        assert set(columns)<=set((3,9)),(i+1,columns)
        bits=lines[start+i].split()
        for column in columns:bits[3 if column==3 else 7]=format(new[column],'.16g')
        lines[start+i]=' '.join(bits);changed.append(i+1)
    destination.write_bytes(('\n'.join(lines)+'\n').encode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8'))
    assert parse_model(destination)[2] == surfaces
    assert invariants(destination)['static_invariants_pass']
    return dict(source=str(source),source_sha256=sha(source),model=str(destination),sha256=sha(destination),
        previous_diameter_mm=2*old_radius,diameter_mm=2*extent,geometry_unchanged=True,
        embedded_and_external_MF_updated_together=True,embedded_MF_changed_rows=changed,
        preserved_MF_rows=8794,preserved_chromatic_rows=44,qualified=False,FFT_checks_run=False)
