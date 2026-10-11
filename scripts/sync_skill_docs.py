"""Synchronize self-contained skill/package references from the maintained docs."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
check='--check' in sys.argv
for dest in (root/'lowpoly_workshop/references',root/'skills/lowpoly-workshop/references'):
    if not check:dest.mkdir(parents=True,exist_ok=True)
    for source in (root/'docs').rglob('*'):
        if not source.is_file() or source.suffix not in ('.md','.png','.json'):continue
        target=dest/source.relative_to(root/'docs')
        if not check:target.parent.mkdir(parents=True,exist_ok=True)
        if check:
            if not target.exists() or target.read_bytes()!=source.read_bytes():raise SystemExit('Stale reference: '+str(target))
        else:target.write_bytes(source.read_bytes())
for source in ('LICENSE','THIRD_PARTY_NOTICES.md','PROVENANCE.json'):
    target=root/'lowpoly_workshop/notices'/source
    if check:
        if target.read_bytes()!=(root/source).read_bytes():raise SystemExit('Stale notice: '+source)
    else:target.write_bytes((root/source).read_bytes())
print('Reference and notice copies match')
