"""Revise only verified object chief angle normalizers; preserve other MF rows."""
import math
from pathlib import Path
from optimize_until_stable import mf_signature
from formal_optical_policy import limits


def revised_signature(signature):
    result=[list(r) for r in signature];count=0
    scale=float(format(1./math.sin(math.radians(limits()['object_chief_angle_limit_deg']-1e-7)),'.13g'))
    for index,row in enumerate(signature,1):
        if row[0]!='PROB' or int(row[1])<=0:continue
        parent=signature[int(row[1])-1]
        if parent[0] not in ('REAA','REAB') or parent[1]!=0 or parent[3]!=0 or parent[4] not in (.25,.5,.75,1.):continue
        if parent[5]!=0 or parent[6]!=0:continue
        assert abs(row[3]-1./math.sin(math.radians(.009)))<abs(row[3])*1e-10
        upper,lower=signature[index:index+2]
        assert upper[0]=='OPLT' and lower[0]=='OPGT' and upper[1]==lower[1]==index
        assert upper[-2]==1. and lower[-2]==-1.
        result[index-1][3]=scale;count+=1
    assert count==20
    return [tuple(r) for r in result]


def revise(source, output):
    source=Path(source);output=Path(output)
    raw=source.read_bytes()
    lines=raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig').splitlines()
    signature=mf_signature(source);changes=[];index=0
    formal=limits()['object_chief_angle_limit_deg'];internal=formal-1e-7
    # SDK MF serialization uses 13 significant digits for this parameter.
    scale=float(format(1./math.sin(math.radians(internal)),'.13g'))
    for n,line in enumerate(lines):
        parts=line.split()
        if len(parts)<11 or parts[0]=='VERS':continue
        index+=1;row=signature[index-1]
        if row[0]!='PROB' or int(row[1])<=0:continue
        parent=signature[int(row[1])-1]
        if parent[0] not in ('REAA','REAB') or parent[1]!=0 or parent[3]!=0 or parent[4] not in (.25,.5,.75,1.):continue
        if parent[5]!=0 or parent[6]!=0:continue
        if not any(abs(row[3]-1./math.sin(math.radians(v)))<=abs(row[3])*1e-10 for v in (.009,.00999,.018,.0199999,internal)):
            raise ValueError(f'Unknown object telecentric normalization at MF row {index}')
        upper,lower=signature[index:index+2]
        assert upper[0]=='OPLT' and lower[0]=='OPGT' and upper[1]==lower[1]==index
        assert upper[-2]==1. and lower[-2]==-1.
        parts[3]=format(scale,'.16g');lines[n]=' '.join(parts)
        changes.append(dict(row=index,wave=int(parent[2]),hy=parent[4],old_scale=row[3],new_scale=scale))
    assert len(changes)==20 and index==8794
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('\n'.join(lines)+'\n',encoding='utf-16')
    revised=mf_signature(output);rows={c['row'] for c in changes}
    assert len(revised)==len(signature)
    for n,(before,after) in enumerate(zip(signature,revised),1):
        if n not in rows:assert before==after
        else:assert before[:3]==after[:3] and before[4:]==after[4:]
    return dict(formal_object_chief_limit_deg=formal,internal_guard_deg=internal,changes=changes,
        original_operand_count=8794,all_other_rows_preserved=True,original_spectral_weights_preserved=True,
        original_44_chromatic_controls_preserved=True)
