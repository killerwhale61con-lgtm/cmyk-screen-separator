# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an allowlisted, source-inclusive Windows release without personal data."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=['app.py','gallery.py','storage.py','worker.py','Start.cmd','起動.cmd',
       'README.txt','README.md','LICENSE','NOTICE','CHANGELOG.txt','PUBLISHING.txt',
       'TESTED.json','.gitignore','tools/build_release.py','tests/smoke_test.py']

def build(destination=None):
    tree=ast.parse((ROOT/'app.py').read_text(encoding='utf-8'))
    version=next(node.value.value for node in tree.body if isinstance(node,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in node.targets))
    directory=Path(destination) if destination else ROOT/'dist'
    directory.mkdir(parents=True,exist_ok=True)
    name='CMYK-Screen-Separator-'+version
    archive=directory/(name+'-windows.zip')
    for relative in FILES:
        if not (ROOT/relative).is_file():raise FileNotFoundError(relative)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for relative in FILES:
            info=zipfile.ZipInfo(name+'/'+relative,date_time=(2026,11,23,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            z.writestr(info,(ROOT/relative).read_bytes())
    checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
    (directory/'SHA256SUMS.txt').write_text(checksum+'  '+archive.name+'\n',encoding='ascii')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP integrity check failed')
        assert len(z.namelist())==len(FILES)
    print(json.dumps({'archive':archive.name,'bytes':archive.stat().st_size,'sha256':checksum,'files':len(FILES)}))
    return archive

if __name__=='__main__':build()
