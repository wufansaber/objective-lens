"""Explicit 4 mm field/MF amendment; retain the original 3 mm validator."""
from pathlib import Path
from optimize_until_stable import mf_signature
from physical_prescription_audit import parse_model
from prepare_uv355_4mm_20261005 import DRAFT, SEED, CHANGES, sha


def verify_merit(model):
    from add_chromatic_merit import verify_chromatic_amendment
    assert sha(SEED)=='6efd3fee418ee94207a3cbb5ee9f134ff9f9a057589f5662872a950655ca86c8'
    if not verify_chromatic_amendment(SEED): return False
    expected=mf_signature(SEED.with_suffix('.MF'))
    expected=[list(r) for r in expected]
    for row,(old,new) in CHANGES.items():
        if expected[row-1][9]!=old:return False
        expected[row-1][9]=new
    actual=mf_signature(Path(model).with_suffix('.MF'))
    legacy=[tuple(r) for r in expected]
    if actual==legacy:return True
    from object_telecentric_policy import revised_signature
    # Only the exact 20 chief-angle normalizer amendment is authorized.
    # The original qualified 3 mm and old 4 mm merit signatures remain valid.
    revised=revised_signature(legacy)
    if actual==revised:return True
    from uv355_three_limit_merit_20261017 import revised_signature as three_limit_signature
    current=three_limit_signature(revised)
    if actual==current:return True
    from formal_optical_policy import limits
    if limits().get('policy_revision_id')=='USER_HEIGHT_LT15_20261018':
        from uv355_height15_merit_revision_20261018 import revised_signature as height_signature
        return actual==height_signature(current)
    return False


def invariants(model):
    _,text,surfaces=parse_model(model)
    _,source_text,original=parse_model(SEED)
    def records(txt,key): return [line.split()[1:] for line in txt.splitlines() if line.startswith(key+' ')]
    keys=('FTYP','XFLN','FWGN','VDXN','VDYN','VCXN','VCYN','VANN','WAVM','OBNA','RAIM','GCAT')
    checks={key:records(text,key)==records(source_text,key) for key in keys}
    checks['4mm_YFLN']=records(text,'YFLN')==[['0','0.5','1','1.5','2']]
    checks['authorized_MF_4mm_targets_only']=verify_merit(model)
    aspheres=[sn for sn,s in surfaces.items() if s.get('type')=='EVENASPH']
    checks['aspheres_original']=aspheres==[2,10,20,22]
    checks['original_A2']=all(surfaces[sn]['parameters'].get(1,0.)==original[sn]['parameters'].get(1,0.) for sn in aspheres)
    checks['higher_than_A10_zero']=all(v==0. for sn in aspheres for k,v in surfaces[sn]['parameters'].items() if k>5)
    checks['materials_original']={sn:s.get('glas') for sn,s in surfaces.items() if s.get('glas')}=={sn:s.get('glas') for sn,s in original.items() if s.get('glas')}
    checks['types_original']={sn:s.get('type') for sn,s in surfaces.items()}=={sn:s.get('type') for sn,s in original.items()}
    return {'model':str(model),'sha256':sha(model),'checks':checks,'static_invariants_pass':all(checks.values()),'full_4mm_design_accepted':False}
