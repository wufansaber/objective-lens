"""Append only the deterministic authorized chromatic block; preserve base MF."""
import argparse,hashlib,json
from pathlib import Path
from optimize_until_stable import mf_signature
from simplify_mechanical_merit import verify_amendment
from chromatic_control import merit_block,policy


def verify_chromatic_amendment(model):
    from simplify_mechanical_merit import ANCHOR,ANCHOR_SHA,selection,reference_positions
    if hashlib.sha256(ANCHOR.read_bytes()).hexdigest()!=ANCHOR_SHA:return False
    sig=mf_signature(ANCHOR.with_suffix('.MF'))
    _,representatives,mapping,_,_=selection(sig)
    expected=[]
    for i in representatives:
        row=list(sig[i-1])
        for p in reference_positions(row[0]):
            if row[p]:row[p]=float(mapping[int(row[p])])
        expected.append(tuple(row))
    expected+=merit_block(len(expected))
    actual=mf_signature(Path(model).with_suffix('.MF'))
    return len(actual)==len(expected) and all(a[0]==b[0] and all(abs(x-y)<=1e-12*max(1.,abs(y)) for x,y in zip(a[1:],b[1:])) for a,b in zip(actual,expected))


def build(source,target):
    source=Path(source).resolve();target=Path(target).resolve()
    if target.exists():raise RuntimeError('Preserve existing files')
    assert verify_amendment(source),'Source must contain the exact authorized mechanical MF'
    sig=mf_signature(source.with_suffix('.MF'));block=merit_block(len(sig))
    lines=source.read_text(encoding='utf-16').splitlines()
    start=next(i for i,l in enumerate(lines) if l.split() and l.split()[0]==sig[0][0])
    def fmt(v):return v if isinstance(v,str) else format(v,'.17g')
    zrows=[' '.join(map(fmt,(r[0],*r[1:7],r[9],r[10],r[7],r[8]))) for r in block]
    output=lines[:start+len(sig)]+zrows+lines[start+len(sig):]
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(('\r\n'.join(output)+'\r\n').encode('utf-16'))
    mf=source.with_suffix('.MF').read_text(encoding='utf-16').splitlines()
    mf+=[' '.join(map(fmt,(*r,0.))) for r in block]
    target.with_suffix('.MF').write_bytes(('\r\n'.join(mf)+'\r\n').encode('utf-16'))
    assert verify_chromatic_amendment(target)
    assert mf_signature(target.with_suffix('.MF'))[:len(sig)]==sig
    assert output[:start]==lines[:start] and output[start+len(sig)+len(block):]==lines[start+len(sig):]
    receipt={'authorization':'User: add chromatic controls, preserve existing +/-10 pm band',
             'model':str(target),'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
             'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'base_merit_count':len(sig),
             'added_rows':len(block),'added_weighted_roots':sum(r[-1]>0 for r in block),
             'existing_merit_rows_exactly_preserved':True,'prescription_and_globals_exactly_preserved':True,
             'policy':policy(),'final_design_accepted':False}
    target.with_suffix('.chromatic_amendment.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();build(a.model,a.output)
