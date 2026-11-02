"""Only the three user-approved boundary amendments; no geometry changes."""
import math
from pathlib import Path
from formal_optical_policy import limits

def revised_signature(signature, acceptance=None):
    p=limits() if acceptance is None else acceptance
    if p['policy_id']!='USER_RELAX_THREE_20261017':return list(signature)
    result=[list(row) for row in signature];counts={'front':0,'image':0,'S33':0}
    front_old=1./(2*math.sin(.00045/2));image_old=1./math.sin(math.radians(.045))
    front_new=float(format(1./(2*math.sin((p['front_divergence_limit_mrad']-.001)/2000)),'.13g'))
    image_new=float(format(1./math.sin(math.radians(p['image_chief_angle_limit_deg']-.00001)),'.13g'))
    for i,row in enumerate(signature):
        if row[0]=='PROB':
            for name,old,new in [('front',front_old,front_new),('image',image_old,image_new)]:
                if abs(row[3]-old)<=abs(old)*1e-10:
                    following=signature[i+1]
                    assert following[0]=='OPLT' and following[1]==i+1 and following[9]==1.
                    result[i][3]=new;counts[name]+=1
        if row[0]=='OPLT' and row[1]>0:
            parent=signature[int(row[1])-1]
            if parent[0]=='PROB' and parent[3]==10. and parent[1]>0:
                ancestor=signature[int(parent[1])-1]
                if ancestor[0]=='TTHI' and ancestor[1]==ancestor[2]==33:
                    assert row[9]==300.
                    result[i][9]=10*p['S33_air_gap_upper_mm'];counts['S33']+=1
    assert counts=={'front':400,'image':20,'S33':1},counts
    return [tuple(row) for row in result]

def prepare(source,destination,acceptance=None):
    from optimize_until_stable import mf_signature
    from physical_prescription_audit import parse_model
    source=Path(source);destination=Path(destination)
    assert not destination.exists() and not destination.with_suffix('.MF').exists()
    old=mf_signature(source.with_suffix('.MF'));new=revised_signature(old,acceptance)
    assert len(old)==len(new)==8794 and old[-44:]==new[-44:]
    changes=[dict(row=i+1,kind=a[0],columns=[j for j in range(1,11) if a[j]!=b[j]])
        for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    assert len(changes)==421
    raw,text,surfaces=parse_model(source);lines=text.splitlines()
    starts=[]
    for i,line in enumerate(lines):
        bits=line.split()
        if len(bits)>=9 and bits[0]==old[0][0]:
            try:
                if tuple(map(float,bits[1:7]))==old[0][1:7]:starts.append(i)
            except ValueError:pass
    good=[]
    for start in starts:
        try:
            for line,row in zip(lines[start:start+8794],old):
                bits=line.split();assert bits[0]==row[0]
                actual=list(map(float,bits[1:9]));expected=list(row[1:7])+list(row[9:11])
                assert all(abs(a-b)<=1e-11*max(1.,abs(b)) for a,b in zip(actual,expected))
            assert len(lines[start:start+8794])==8794
            good.append(start)
        except (AssertionError,ValueError):pass
    assert len(good)==1,good
    start=good[0]
    for change in changes:
        i=change['row']-1;bits=lines[start+i].split()
        for column in change['columns']:
            assert column in (3,9)
            bits[3 if column==3 else 7]=format(new[i][column],'.16g')
        lines[start+i]=' '.join(bits)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(('\n'.join(lines)+'\n').encode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8'))
    mf=source.with_suffix('.MF').read_text(encoding='utf-16').splitlines()
    assert len(mf)==8795
    for change in changes:
        i=change['row'];bits=mf[i].split()
        for column in change['columns']:bits[column]=format(new[i-1][column],'.16g')
        mf[i]=' '.join(bits)
    destination.with_suffix('.MF').write_text('\n'.join(mf)+'\n',encoding='utf-16')
    assert mf_signature(destination.with_suffix('.MF'))==new
    assert parse_model(destination)[2]==surfaces
    assert all(a==b for i,(a,b) in enumerate(zip(text.splitlines(),lines)) if not any(start+c['row']-1==i for c in changes))
    return dict(source=str(source),model=str(destination),changed_MF_rows=changes,
        authorized_front_normalizers=400,authorized_image_normalizers=20,authorized_S33_upper_bound_rows=1,
        original8794_MF_rows_and_last44_chromatic_controls_preserved=True,
        embedded_and_external_MF_updated_together=True,lens_geometry_and_variable_flags_unchanged=True,
        qualified=False,FFT_checks_run=False)
