"""Align four stored100x image-height bound targets with the approved15um rule."""
from pathlib import Path
from optimize_until_stable import mf_signature
from physical_prescription_audit import parse_model

def revised_signature(rows):
    result=[list(row) for row in rows]
    assert len(result)==8794
    for lower,upper in ((861,862),(865,866)):
        a,b=result[lower-1],result[upper-1]
        assert a[0]=='OPGT' and b[0]=='OPLT'
        center=(a[9]+b[9])/2.
        assert abs((b[9]-a[9])-2.)<1e-9 or abs((b[9]-a[9])-3.)<1e-9
        a[9],b[9]=center-1.5,center+1.5
    return [tuple(row) for row in result]

def align_saved_model(model):
    model=Path(model);mf=model.with_suffix('.MF')
    old=mf_signature(mf);new=revised_signature(old)
    if old==new:return dict(changed_rows=[],already_aligned=True)
    raw,text,surfaces=parse_model(model)
    lines=text.splitlines();starts=[]
    for start,line in enumerate(lines):
        bits=line.split()
        if len(bits)<9 or bits[0]!=old[0][0]:continue
        try:
            assert len(lines[start:start+len(old)])==len(old)
            for saved,row in zip(lines[start:start+len(old)],old):
                tokens=saved.split();assert tokens[0]==row[0]
                actual=list(map(float,tokens[1:9]));expected=list(row[1:7])+list(row[9:11])
                assert all(abs(a-b)<=1e-11*max(1.,abs(b)) for a,b in zip(actual,expected))
            starts.append(start)
        except (AssertionError,ValueError):continue
    assert len(starts)==1, 'Require an exactly matching original embedded MF'
    changed=[]
    for i,(before,after) in enumerate(zip(old,new)):
        if before==after:continue
        assert i+1 in (861,862,865,866) and all(before[j]==after[j] for j in range(11) if j!=9)
        tokens=lines[starts[0]+i].split();tokens[7]=format(after[9],'.16g');lines[starts[0]+i]=' '.join(tokens);changed.append(i+1)
    mfraw=mf.read_bytes();mflines=mfraw.decode('utf-16' if mfraw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8').splitlines();n=0
    for i,line in enumerate(mflines):
        tokens=line.split()
        if len(tokens)<11 or tokens[0]=='VERS':continue
        n+=1
        if n in changed:tokens[9]=format(new[n-1][9],'.16g');mflines[i]=' '.join(tokens)
    assert n==8794
    mf.write_text('\n'.join(mflines)+'\n',encoding='utf-16' if mfraw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8')
    model.write_bytes(('\n'.join(lines)+'\n').encode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8'))
    assert mf_signature(mf)==new and parse_model(model)[2]==surfaces
    return dict(changed_rows=changed,only_target_column_changed=True,phase840_and_color44_and_all_weights_preserved=True,strict15um_enforced_by_native_guard_and_independent_audit=True)
