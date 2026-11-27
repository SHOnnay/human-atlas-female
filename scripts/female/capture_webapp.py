"""Acceptance B: the same views as the Blender composites, captured from the running web app.

    npm run dev  (or any server)            then
    python scripts/female/capture_webapp.py [--base http://localhost:3000]
    -> docs/screenshots/webapp/<category>_<view>.png  (male left, female right, same camera)

Uses the app's ?debug capture API (app/scene.tsx: __atlasRenderer.camera / filter / opacity) in
headless Chromium (Playwright). Categories, framing and views come from compare_renders.py, so a
web-app image and its Blender composite show the same parts from the same direction.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import compare_renders as cr  # noqa: E402
import meshlib as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs' / 'screenshots' / 'webapp'
# Blender view directions (Z-up, anterior = -Y) -> atlas (y-up, anterior = +z): (bx, bz, -by).
DIRS_B = {'front': (0, -1, 0), 'back': (0, 1, 0), 'side': (1, 0, 0), 'oblique': (0.75, -1, 0.15), 'below': (0, -0.35, -1),
          'palm': (-1, -0.25, 0), 'dorsum': (1, 0.25, 0), 'palm_r': (1, -0.25, 0), 'dorsum_r': (-1, 0.25, 0)}


def atlas_dir(v):
    d = np.array([v[0], v[2], -v[1]], float)
    return d / np.linalg.norm(d)


def members(path):
    atlas, M = ml.load_package(path)
    cr.set_hands(atlas, M)
    out = {}
    for p in atlas['parts']:
        for cat in cr.categories(p, M[p['id']]['pos'].mean(0)):
            out.setdefault(cat, []).append(p['name'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://localhost:3000')
    ap.add_argument('--only', default=None, help='comma-separated categories')
    a = ap.parse_args()
    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright
    jobs = json.loads((Path(tempfile.gettempdir()) / 'ha-compare' / 'jobs.json').read_text())
    if a.only:
        jobs = [j for j in jobs if j['cat'] in a.only.split(',')]
    names = {'male': members(ROOT / 'public/models/atlas.json'), 'female': members(ROOT / 'public/models/female/atlas.json')}
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.gettempdir()) / 'ha-webapp'
    tmp.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        for body in ('male', 'female'):
            page = browser.new_page(viewport={'width': 700, 'height': 900})
            page.goto(f'{a.base}/?body={body}&debug')
            page.wait_for_function('window.__atlasRenderer && window.__atlasRenderer.ready()', timeout=600000)
            page.evaluate("""() => { const c = document.querySelector('canvas');
                document.querySelectorAll('body *').forEach(e => { if (!e.contains(c) && e !== c) e.style.visibility = 'hidden'; }); }""")
            for job in jobs:
                fr = job.get('frames', {}).get(body, [job['lo'], job['hi']])
                lo, hi = np.array(fr[0]), np.array(fr[1])
                centre, size = (lo + hi) / 2, float(np.max(hi - lo))
                page.evaluate('([n]) => window.__atlasRenderer.filter(n, null)', [names[body].get(job['cat'], [])])
                for sys_ in ('integumentary', 'adipose', 'subcutaneous'):
                    page.evaluate('([s, v]) => window.__atlasRenderer.opacity(s, v)', [sys_, job.get('alpha', {}).get(sys_, 0.35 if (body == 'female' and sys_ in ('adipose', 'subcutaneous')) else 1.0)])
                for v in job['views']:
                    d = atlas_dir(DIRS_B[v])
                    vf = job.get('view_frames', {}).get(body, {}).get(v)
                    if vf:
                        centre, size = np.array(vf[0]), float(vf[1])
                    pos = centre + d * size * 8
                    page.evaluate('([t, p, h]) => window.__atlasRenderer.camera(t, p, h)', [centre.tolist(), pos.tolist(), size * 1.08])
                    page.wait_for_timeout(400)
                    page.screenshot(path=str(tmp / f"{body}_{job['cat']}_{v}.png"))
            page.close()
        browser.close()
    made = []
    for job in jobs:
        for v in job['views']:
            a_, b_ = (Image.open(tmp / f"{s}_{job['cat']}_{v}.png").convert('RGB') for s in ('male', 'female'))
            img = Image.new('RGB', (a_.width + b_.width, a_.height + 36), (245, 246, 247))
            img.paste(a_, (0, 36)); img.paste(b_, (a_.width, 36))
            d = ImageDraw.Draw(img)
            d.text((12, 10), f"WEB APP · MALE · {job['cat']} · {v}", fill=(40, 50, 60))
            d.text((a_.width + 12, 10), f"WEB APP · FEMALE · {job['cat']} · {v}", fill=(40, 50, 60))
            img.save(OUT / f"{job['cat']}_{v}.png"); made.append(f"{job['cat']}_{v}.png")
    print('\n'.join(made))


if __name__ == '__main__':
    main()
