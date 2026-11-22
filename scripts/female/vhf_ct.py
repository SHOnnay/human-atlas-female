"""VHF CT (NLM Visible Human Project, female; via NCI Imaging Data Commons) -> NIfTI.

    python scripts/female/vhf_ct.py            (in the TotalSegmentator venv)
Downloads (idc-index) the two female CT series into work/vhf/ct/<SeriesInstanceUID>/ if missing,
converts each DICOM series to work/vhf/ct_<n>.nii.gz and prints size / spacing / origin.
Courtesy of the U.S. National Library of Medicine.
"""
import json
import sys
from pathlib import Path

import SimpleITK as sitk

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work' / 'vhf'
SERIES = {'head_to_femur': '1.3.6.1.4.1.5962.1.3.370.2.1672334394.26545',      # AXIAL 1X1 NCE, 985 slices
          'femur_to_toes': '1.3.6.1.4.1.5962.1.3.371.2.1672334394.26545'}      # 1X1 AXIAL FEMUR-TOES NCE, 749 slices


def download():
    from idc_index import index
    c = index.IDCClient()
    missing = [u for u in SERIES.values() if not (WORK / 'ct' / u).exists()]
    if missing:
        c.download_from_selection(seriesInstanceUID=missing, downloadDir=str(WORK / 'ct'), dirTemplate='%SeriesInstanceUID')


def convert():
    info = {}
    for name, uid in SERIES.items():
        out = WORK / f'ct_{name}.nii.gz'
        r = sitk.ImageSeriesReader()
        files = r.GetGDCMSeriesFileNames(str(WORK / 'ct' / uid))
        r.SetFileNames(files)
        img = r.Execute()
        sitk.WriteImage(img, str(out))
        info[name] = {'size': img.GetSize(), 'spacing': img.GetSpacing(), 'origin': img.GetOrigin(), 'direction': img.GetDirection(),
                      'files': len(files)}
        print(name, json.dumps(info[name]), flush=True)
    (WORK / 'ct_info.json').write_text(json.dumps(info, indent=1))


if __name__ == '__main__':
    WORK.mkdir(parents=True, exist_ok=True)
    download()
    convert()
