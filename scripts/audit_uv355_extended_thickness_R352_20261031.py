"""Existing native optical review plus the authorized estimated thickness band."""
import os
from pathlib import Path
os.environ['UV355_FORMAL_POLICY_FILE']=str(Path(__file__).resolve().parents[1]/'results/uv355_height_lt15_policy_20261018/formal_policy.json')
from uv355_extended_thickness_audit_R351_20261031 import install

if __name__ == '__main__':
    install()
    from audit_uv355_field_continuation_20261012 import main
    main()
