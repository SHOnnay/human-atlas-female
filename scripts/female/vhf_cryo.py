"""VHF colour cryosections (NLM Visible Human Project, female, "Fullcolor - direct digital";
public via NCI Imaging Data Commons, bucket idc-open-data). Courtesy of the U.S. National Library
of Medicine.

    python scripts/female/vhf_cryo.py index                 -> work/vhf/xc_index.json (slice z per file)
    python scripts/female/vhf_cryo.py get Z0 Z1 [STEP]      -> work/vhf/xc/<z>.png for slices with z in [Z0, Z1]

Only the DICOM header (first 16 KB) of every file is read to build the index; whole slices are
downloaded only for the ranges actually used (perineum, section levels).
"""
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pydicom

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work' / 'vhf'
SERIES = '1.3.6.1.4.1.5962.1.3.0.1.1677425356.1733'


def https(u):
    return u.replace('s3://idc-open-data/', 'https://idc-open-data.s3.amazonaws.com/')


def header(u):
    req = urllib.request.Request(https(u), headers={'Range': 'bytes=0-16383'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True)
    pos = getattr(ds, 'ImagePositionPatient', None)
    return {'url': u, 'instance': int(getattr(ds, 'InstanceNumber', -1)),
            'z': float(pos[2]) if pos is not None else float(getattr(ds, 'SliceLocation', 'nan')),
            'rows': int(getattr(ds, 'Rows', 0)), 'cols': int(getattr(ds, 'Columns', 0)),
            'spacing': [float(x) for x in getattr(ds, 'PixelSpacing', [0, 0])],
            'origin': [float(x) for x in pos] if pos is not None else None}


def build_index():
    urls = json.loads((WORK / 'xc_urls.json').read_text())
    with ThreadPoolExecutor(32) as ex:
        rows = list(ex.map(header, urls))
    rows.sort(key=lambda r: r['z'])
    (WORK / 'xc_index.json').write_text(json.dumps(rows))
    z = np.array([r['z'] for r in rows])
    print('slices', len(rows), 'z range', z.min(), z.max(), 'median step', np.median(np.diff(z)), 'size', rows[0]['cols'], rows[0]['rows'], rows[0]['spacing'])


def get(z0, z1, step=1):
    from PIL import Image
    rows = [r for r in json.loads((WORK / 'xc_index.json').read_text()) if z0 <= r['z'] <= z1][::step]
    out = WORK / 'xc'
    out.mkdir(parents=True, exist_ok=True)

    def one(r):
        dst = out / f"{r['z']:.2f}.png"
        if dst.exists():
            return
        with urllib.request.urlopen(https(r['url']), timeout=300) as f:
            ds = pydicom.dcmread(io.BytesIO(f.read()), force=True)
        Image.fromarray(ds.pixel_array).save(dst)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, rows))
    print('downloaded', len(rows), 'slices', z0, z1)


if __name__ == '__main__':
    if sys.argv[1] == 'index':
        build_index()
    else:
        get(float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 1)
