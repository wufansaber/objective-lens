"""Display curves on the project 0..200 lp/mm band, with 25 lp/mm native points."""
from pathlib import Path
import measure_uv355_visual_MTF_curves_R947_20261102 as original

source=Path(original.__file__).read_text(encoding='utf-8-sig')
edits={'np.arange(0.,351.,10.)':'np.arange(0.,201.,25.)',
       'xlim=(0,350)':'xlim=(0,200)'}
for old,new in edits.items():
    assert source.count(old)==1
    source=source.replace(old,new)
exec(compile(source,str(Path(__file__)),'exec'),globals())
