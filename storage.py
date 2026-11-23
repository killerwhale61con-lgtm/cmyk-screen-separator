# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy verified plates to a fresh destination without replacing existing files."""
import datetime
import json
import os
import re
import shutil
import uuid
from pathlib import Path

def export_job(source, destination, stem):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not all((source/(c+'.JPEG')).is_file() for c in 'CMYK'):
        raise ValueError('保存する4枚のJPEGがそろっていません。')
    status = json.loads((source/'status.json').read_text(encoding='utf-8'))
    if status.get('error') or status.get('progress') != 100:
        raise ValueError('分解が完了していないため保存できません。')
    destination.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', stem).strip('. ') or 'image'
    name = stem[:100] + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    target = destination/name
    staging = destination/('.cmyk-saving-'+uuid.uuid4().hex)
    if target.exists():
        raise FileExistsError(str(target))
    try:
        shutil.copytree(source, staging)
        # Windows rename fails if the target already exists. No overwrite option is used.
        os.rename(staging, target)
    except Exception:
        if staging.resolve().parent == destination and staging.name.startswith('.cmyk-saving-') and staging.is_dir():
            shutil.rmtree(staging)
        raise
    return target

def write_pending(data_root, folder):
    root = Path(data_root)
    root.mkdir(parents=True, exist_ok=True)
    tmp = root/'pending.json.tmp'
    tmp.write_text(json.dumps({'folder': str(Path(folder).resolve())}), encoding='utf-8')
    os.replace(tmp, root/'pending.json')

def read_pending(data_root):
    try:
        folder = Path(json.loads((Path(data_root)/'pending.json').read_text(encoding='utf-8'))['folder']).resolve()
        if folder.parent != (Path(data_root)/'jobs').resolve():
            return None
        if all((folder/(c+'.JPEG')).is_file() for c in 'CMYK'):
            return folder
    except (OSError, ValueError, KeyError):
        pass
    return None

def clear_pending(data_root, folder):
    root, folder = Path(data_root).resolve(), Path(folder).resolve()
    if folder.parent != (root/'jobs').resolve():
        raise ValueError('作業フォルダーの範囲外は削除しません。')
    (root/'pending.json').unlink(missing_ok=True)
    if folder.is_dir():
        shutil.rmtree(folder)
