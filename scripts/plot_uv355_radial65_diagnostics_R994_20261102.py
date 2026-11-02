"""Render the final 1025-point native diagnostics with the established plotter."""
from pathlib import Path
import plot_uv355_field_diagnostics_R949_20261102 as original

source = Path(original.__file__).read_text(encoding='utf-8-sig')
old = "data['field_count']==513"
assert source.count(old) == 1
source = source.replace(old, "data['field_count'] in (513,1025)")
exec(compile(source, str(Path(__file__)), 'exec'), globals())
