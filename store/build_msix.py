# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile a native frontend and create an unsigned Store-submission MSIX.

The output is not an end-user installer. No test certificate is generated or
installed. Partner Center identity and Microsoft Store signing are separate.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import xml.etree.ElementTree as ET
import zlib
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

def logo(path, size):
    rows = []
    colors = [(0, 175, 220), (222, 30, 126), (255, 210, 0), (30, 30, 30)]
    centers = [(.35, .35), (.65, .35), (.35, .65), (.65, .65)]
    for y in range(size):
        row = bytearray()
        for x in range(size):
            color = (246, 248, 250)
            for (cx, cy), ink in zip(centers, colors):
                if (x / size - cx)**2 + (y / size - cy)**2 <= .17**2:
                    color = ink
            row.extend(color)
        rows.append(b'\0' + row)
    def chunk(kind, content):
        return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', zlib.crc32(kind+content) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b''))

def build(identity_file, sdk, output, preview):
    identity = json.loads(identity_file.read_text(encoding='utf-8-sig'))
    required = ('IdentityName', 'Publisher', 'PublisherDisplayName', 'DisplayName', 'Version')
    if any(not identity.get(key) for key in required):
        raise ValueError('Partner Center identity fields are missing')
    placeholder = 'NotAssigned' in identity['Publisher'] or identity['IdentityName'].endswith('StorePreview')
    if placeholder and not preview:
        raise ValueError('Partner Centerの製品IDが未設定です。仮IDでの構造検証には --preview を明示してください。')
    output.mkdir(parents=True, exist_ok=True)
    stage = output/'package'
    stage.mkdir(exist_ok=False)
    assets = stage/'Assets'
    assets.mkdir()
    for size, name in [(44, 'Square44.png'), (150, 'Square150.png'), (50, 'StoreLogo.png'), (300, 'StoreListingIcon300.png')]:
        logo(assets/name, size)
    csc = Path(os.environ.get('WINDIR', r'C:\Windows'))/'Microsoft.NET'/'Framework64'/'v4.0.30319'/'csc.exe'
    sources = sorted((HERE/'src').glob('*.cs'))
    command = [str(csc), '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/define:STORE',
               '/out:'+str(stage/'CMYKScreenSeparator.exe'), '/win32manifest:'+str(HERE/'app.manifest'),
               '/r:System.Drawing.dll', '/r:System.Windows.Forms.dll', '/r:System.Web.Extensions.dll',
               '/r:System.Xml.Linq.dll'] + [str(path) for path in sources]
    subprocess.run(command, check=True)
    for name in ('worker.py', 'LICENSE', 'NOTICE'):
        (stage/name).write_bytes((REPO/name).read_bytes())
    ns = 'http://schemas.microsoft.com/appx/manifest/foundation/windows10'
    uap = 'http://schemas.microsoft.com/appx/manifest/uap/windows10'
    uap10 = 'http://schemas.microsoft.com/appx/manifest/uap/windows10/10'
    rescap = 'http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities'
    ET.register_namespace('', ns); ET.register_namespace('uap', uap); ET.register_namespace('uap10', uap10); ET.register_namespace('rescap', rescap)
    package = ET.Element('{'+ns+'}Package', {'IgnorableNamespaces':'uap uap10 rescap'})
    ET.SubElement(package,'{'+ns+'}Identity', {'Name':identity['IdentityName'],'Publisher':identity['Publisher'], 'Version':identity['Version'],'ProcessorArchitecture':'x64'})
    properties = ET.SubElement(package,'{'+ns+'}Properties')
    for key, value in [('DisplayName',identity['DisplayName']),('PublisherDisplayName',identity['PublisherDisplayName']),('Logo','Assets/StoreLogo.png')]:
        ET.SubElement(properties,'{'+ns+'}'+key).text = value
    dependencies=ET.SubElement(package,'{'+ns+'}Dependencies')
    ET.SubElement(dependencies,'{'+ns+'}TargetDeviceFamily', {'Name':'Windows.Desktop','MinVersion':'10.0.22000.0','MaxVersionTested':'10.0.26100.0'})
    resources=ET.SubElement(package,'{'+ns+'}Resources'); ET.SubElement(resources,'{'+ns+'}Resource',{'Language':'ja-jp'})
    applications=ET.SubElement(package,'{'+ns+'}Applications')
    app=ET.SubElement(applications,'{'+ns+'}Application', {'Id':'App','Executable':'CMYKScreenSeparator.exe',
        'EntryPoint':'Windows.FullTrustApplication','{'+uap10+'}RuntimeBehavior':'packagedClassicApp','{'+uap10+'}TrustLevel':'mediumIL'})
    ET.SubElement(app,'{'+uap+'}VisualElements',{'DisplayName':identity['DisplayName'],'Description':'GIMPを使って写真からCMYK網点4版を作成します。GIMP 3が必要です。',
        'BackgroundColor':'transparent','Square150x150Logo':'Assets/Square150.png','Square44x44Logo':'Assets/Square44.png'})
    caps=ET.SubElement(package,'{'+ns+'}Capabilities');ET.SubElement(caps,'{'+rescap+'}Capability',{'Name':'runFullTrust'})
    ET.ElementTree(package).write(stage/'AppxManifest.xml', encoding='utf-8', xml_declaration=True)
    choices = list(sdk.rglob('x64/makeappx.exe'))
    if not choices: raise FileNotFoundError('Microsoft Windows SDK makeappx.exe was not found')
    makeappx=sorted(choices)[-1]
    # Validate normal manifest rules. There is no /nv switch or trust-policy change.
    package_path=output/('CMYKScreenSeparator-'+identity['Version']+'-x64-'+('identity-preview' if placeholder else 'store-submission')+'.msix')
    subprocess.run([str(makeappx),'pack','/d',str(stage),'/p',str(package_path),'/o'], check=True)
    with zipfile.ZipFile(package_path) as archive:
        names = archive.namelist()
        if archive.testzip() is not None:
            raise RuntimeError('MSIX integrity check failed')
        if any(Path(name).suffix.lower() in ('.cmd', '.bat', '.ps1') for name in names):
            raise RuntimeError('A launch script was accidentally packaged')
        if archive.read('worker.py') != (REPO/'worker.py').read_bytes():
            raise RuntimeError('GIMP worker differs from source')
    report={'version':identity['Version'],'native_frontend_compiled':True,'makeappx_manifest_validation':'passed',
            'identity_assigned_by_partner_center':not placeholder,'signed':False,'end_user_installable':False,
            'store_published':False,'native_runtime_and_store_activation':'not yet verified on a Store-signed installation',
            'launch_scripts_in_package':False,'bundled_gimp':False,'gimp_processing':'existing worker.py; previous tests apply to worker, not new native frontend',
            'archive_integrity':'passed','worker_matches_source':True,'package_entries':names,
            'sha256':hashlib.sha256(package_path.read_bytes()).hexdigest()}
    (output/'BUILD-REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return package_path

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--identity',type=Path,required=True)
    parser.add_argument('--sdk',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preview',action='store_true',help='Build an identity-placeholder draft; never an end-user release')
    args=parser.parse_args()
    build(args.identity.resolve(),args.sdk.resolve(),args.output.resolve(),args.preview)
