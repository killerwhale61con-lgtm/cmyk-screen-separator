# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an unsigned EXE ZIP with corresponding source; never claim SAC compatibility."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.3.0-beta'

def build(output):
    output.mkdir(parents=True, exist_ok=True)
    stage = output / ('CMYK-Screen-Separator-' + VERSION)
    stage.mkdir(exist_ok=False)
    csc = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    sources = sorted((ROOT/'store/src').glob('*.cs'))
    if len(sources) != 4:
        raise RuntimeError('Unexpected native source list')
    subprocess.run([str(csc), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
                    '/out:'+str(stage/'CMYKScreenSeparator.exe'),
                    '/win32manifest:'+str(ROOT/'store/app.manifest'),
                    '/r:System.Drawing.dll', '/r:System.Windows.Forms.dll',
                    '/r:System.Web.Extensions.dll', '/r:System.Xml.Linq.dll'] + [str(p) for p in sources], check=True)
    for name in ['worker.py', 'LICENSE', 'NOTICE']:
        (stage/name).write_bytes((ROOT/name).read_bytes())
    (stage/'README.md').write_bytes((ROOT/'desktop/README.md').read_bytes())
    source_files = ['worker.py', 'LICENSE', 'NOTICE', 'desktop/README.md',
                    'desktop/build_portable.py', 'store/app.manifest'] + [p.relative_to(ROOT).as_posix() for p in sources]
    for name in source_files:
        target = stage/'source'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    report = {'version':VERSION, 'distribution':'GitHub portable EXE', 'compiled':True,
              'signed':False, 'store_account_required':False, 'launch_cmd_required':False,
              'smart_app_control':'not supported/verified; unsigned EXE may be blocked',
              'native_frontend_runtime':'not yet verified', 'store_gimp_activation':'not yet verified',
              'manual_four_plate_comparison':'not completed',
              'exe_sha256':hashlib.sha256((stage/'CMYKScreenSeparator.exe').read_bytes()).hexdigest()}
    (stage/'BUILD-REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    archive = output/(stage.name+'-windows-x64-unsigned.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
        for file in sorted(stage.rglob('*')):
            if file.is_file():
                package.write(file, stage.name+'/'+file.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise RuntimeError('ZIP integrity failure')
        assert not any(Path(n).suffix.lower() in ('.cmd','.bat','.ps1') for n in package.namelist())
        assert package.read(stage.name+'/worker.py') == (ROOT/'worker.py').read_bytes()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/'SHA256SUMS.txt').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest,'signed':False}))
    return archive

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output.resolve())
