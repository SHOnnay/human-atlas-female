"""Headless-browser verification: screenshots, body switching, leak check, WebMCP tools.

    npm run dev            # serves http://localhost:3016
    python scripts/verify-browser.py [--base http://localhost:3016]

Writes docs/screenshots/*.png and work/browser-report.json. Uses Playwright + headless Chromium
(software WebGL via SwiftShader); this is not a physical-device test.
"""
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / 'docs' / 'screenshots'
ARGS = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
# Fake WebMCP host: records tools the page registers so they can be called from the test.
MCP_SHIM = """
window.__tools = {};
document.modelContext = {registerTool(tool, opts){ window.__tools[tool.name] = tool;
  opts && opts.signal && opts.signal.addEventListener('abort', () => { if (window.__tools[tool.name] === tool) delete window.__tools[tool.name]; }); }};
"""


def wait_loaded(page, timeout=240):
    page.wait_for_selector('.identity-meta', timeout=60000)
    t0 = time.time()
    while time.time() - t0 < timeout:
        state = page.evaluate("() => ({loading: !!document.querySelector('.loading:not(.error)'), error: document.querySelector('.loading.error')?.innerText || null, canvas: !!document.querySelector('.scene canvas')})")
        if state['error']:
            raise RuntimeError(state['error'])
        if not state['loading'] and state['canvas']:
            page.wait_for_timeout(1200)
            return time.time() - t0
        page.wait_for_timeout(500)
    raise TimeoutError('anatomy did not finish loading')


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f'{name}.png'))
    print('screenshot', name, flush=True)


def search(page, text):
    page.keyboard.press('Escape')
    page.click('.top-actions button[aria-label="Search anatomy"]')
    page.fill('.search-panel input', text)
    page.wait_for_timeout(600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://localhost:3016')
    ap.add_argument('--switches', type=int, default=10)
    a = ap.parse_args()
    report = {'console_errors': [], 'checks': {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=ARGS)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
        ctx.add_init_script(MCP_SHIM)
        page = ctx.new_page()
        page.on('console', lambda m: report['console_errors'].append(m.text) if m.type in ('error', 'warning') and 'favicon' not in m.text else None)

        # 1. Male default (unchanged behaviour).
        page.goto(f'{a.base}/?body=male')
        report['checks']['male_load_s'] = wait_loaded(page)
        report['checks']['male_caption'] = page.inner_text('.scene-caption')
        report['checks']['male_meta'] = page.inner_text('.identity-meta')
        shot(page, '01-male-default')

        # 2. Selection carry-over: Heart (shared) survives the switch to female.
        search(page, 'heart')
        page.click('.anatomy-search-results [data-slot=combobox-item] >> text=/^heart$/i')
        page.wait_for_timeout(800)
        page.click('.body-toggle [aria-label="Female anatomy"]')
        report['checks']['female_load_s'] = wait_loaded(page)
        page.wait_for_timeout(800)
        report['checks']['heart_kept_after_switch'] = page.inner_text('.structure-title') if page.query_selector('.detail-sheet') else None
        report['checks']['url_after_switch'] = page.url
        report['checks']['localStorage'] = page.evaluate("() => { try { return localStorage.getItem('human-atlas:body') } catch (e) { return 'unavailable' } }")
        page.click('.detail-sheet button:has-text("Clear selection")')
        page.wait_for_timeout(500)

        # 3. Female default view.
        page.click('nav.view-controls button[aria-label="Reset view and layers"]')
        page.wait_for_timeout(1500)
        report['checks']['female_caption'] = page.inner_text('.scene-caption')
        report['checks']['female_meta'] = page.inner_text('.identity-meta')
        shot(page, '02-female-default')

        # 4. Search result for "uterus".
        search(page, 'uterus')
        report['checks']['uterus_search_results'] = page.eval_on_selector_all('.anatomy-search-results [data-slot=combobox-item] .search-result-name', 'els => els.map(e => e.textContent)')[:12]
        shot(page, '06-female-search-uterus')
        page.keyboard.press('Escape')

        # 5. Reproductive system only, then an isolated uterus with its details panel.
        page.click('.system-name:has-text("Reproductive")')
        page.click('nav.view-controls button[aria-label="front view"]')
        page.wait_for_timeout(1500)
        shot(page, '03-female-reproductive-system')
        search(page, 'uterus')
        page.click('.anatomy-search-results [data-slot=combobox-item] >> text=/^uterus$/i')
        page.wait_for_timeout(700)
        page.click('.detail-sheet button:has-text("Isolate structure")')
        page.wait_for_timeout(2000)
        shot(page, '03b-female-uterus-isolated')
        page.click('.detail-sheet button:has-text("Clear selection")')

        # 6. Approximate badge on a generated structure (clitoris).
        search(page, 'clitoris')
        page.click('.anatomy-search-results [data-slot=combobox-item] >> text=/^clitoris$/i')
        page.wait_for_timeout(800)
        report['checks']['clitoris_badge'] = page.inner_text('.accuracy-badge') if page.query_selector('.accuracy-badge') else None
        page.click('.detail-sheet button:has-text("Isolate structure")')
        page.wait_for_timeout(2000)
        shot(page, '07-female-clitoris-approximate-badge')
        page.click('.detail-sheet button:has-text("Clear selection")')

        # 7. Skeleton preset (pelvis visible), front and three-quarter.
        page.click('.layer-presets button:has-text("Skeleton")')
        page.click('nav.view-controls button[aria-label="front view"]')
        page.wait_for_timeout(1500)
        shot(page, '04-female-skeleton-front')
        page.click('nav.view-controls button[aria-label="three-quarter view"]')
        page.wait_for_timeout(1500)
        shot(page, '04b-female-skeleton-three-quarter')

        # 8. Exploded inventory, all systems.
        page.click('.layer-presets button:has-text("All")')
        page.focus('.explode-control input[type=range]')
        page.keyboard.press('End')
        page.wait_for_timeout(4000)
        report['checks']['exploded_caption'] = page.inner_text('.scene-caption')
        shot(page, '05-female-exploded')
        page.keyboard.press('Home')
        page.wait_for_timeout(1500)

        # 9. Female-only selection clears with a toast when switching back to male.
        search(page, 'uterus')
        page.click('.anatomy-search-results [data-slot=combobox-item] >> text=/^uterus$/i')
        page.wait_for_timeout(500)
        page.click('.body-toggle [aria-label="Male anatomy"]')
        wait_loaded(page)
        page.wait_for_timeout(300)
        toasts = page.eval_on_selector_all('[data-slot=toast]', 'els => els.map(e => e.innerText)')
        report['checks']['toast_after_switch'] = toasts
        report['checks']['selection_after_uterus_switch'] = bool(page.query_selector('.detail-sheet'))
        shot(page, '08-toast-selection-cleared')

        # 10. WebMCP tools with the body parameter.
        tools = page.evaluate('() => Object.keys(window.__tools)')
        res = page.evaluate("async () => await window.__tools.find_anatomy.execute({query: 'ovary', body: 'female'})")
        report['checks']['webmcp_tools'] = tools
        report['checks']['webmcp_find_female_from_male'] = res[:3]
        report['checks']['webmcp_find_male_uterus'] = page.evaluate("async () => await window.__tools.find_anatomy.execute({query: 'uterus'})")
        out = page.evaluate("async (id) => await window.__tools.inspect_anatomical_structure.execute({id, body: 'female'})", res[0]['id'])
        wait_loaded(page)
        page.wait_for_timeout(800)
        report['checks']['webmcp_inspect_switches_body'] = {'result': out, 'title': page.inner_text('.structure-title') if page.query_selector('.detail-sheet') else None, 'url': page.url}
        page.close()

        # 11. Leak check: switch bodies N times with ?debug and read renderer.info after each load.
        page = ctx.new_page()
        page.on('console', lambda m: report['console_errors'].append(m.text) if m.type in ('error', 'warning') and 'favicon' not in m.text else None)
        cdp = ctx.new_cdp_session(page)
        cdp.send('Performance.enable')
        page.goto(f'{a.base}/?body=male&debug')
        wait_loaded(page)
        samples = []
        for i in range(a.switches + 1):
            if i:
                target = 'Female' if i % 2 else 'Male'
                page.click(f'.body-toggle [aria-label="{target} anatomy"]')
                wait_loaded(page)
            cdp.send('HeapProfiler.collectGarbage')
            page.wait_for_timeout(400)
            info = page.evaluate("() => { const r = window.__atlasRenderer; return r ? {geometries: r.info.memory.geometries, textures: r.info.memory.textures, programs: (r.info.programs||[]).length, calls: r.info.render.calls, parts: r.parts} : null }")
            heap = {m['name']: m['value'] for m in cdp.send('Performance.getMetrics')['metrics'] if m['name'] in ('JSHeapUsedSize', 'Nodes', 'JSEventListeners')}
            canvases = page.evaluate("() => document.querySelectorAll('canvas').length")
            samples.append({'switch': i, 'body': page.evaluate("() => document.querySelector('main').dataset.body"), **(info or {}), **heap, 'canvases': canvases})
            print('sample', samples[-1], flush=True)
        report['leak_samples'] = samples
        page.close()

        # 12. Mobile viewport (390×844), female default and male default.
        m = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        page = m.new_page()
        page.goto(f'{a.base}/?body=female')
        wait_loaded(page)
        shot(page, '09-mobile-female')
        boxes = page.evaluate("() => Object.fromEntries(['.identity', '.body-toggle', '.view-controls', '.top-actions', '.bottom-dock'].map(s => { const r = document.querySelector(s).getBoundingClientRect(); return [s, [r.left, r.top, r.right, r.bottom]]; }))")
        report['checks']['mobile_layout_boxes'] = boxes
        page.goto(f'{a.base}/?body=male')
        wait_loaded(page)
        shot(page, '10-mobile-male')
        page = m.new_page()
        page.set_viewport_size({'width': 320, 'height': 568})
        page.goto(f'{a.base}/?body=female')
        wait_loaded(page)
        shot(page, '11-mobile-320-female')
        browser.close()
    (ROOT / 'work').mkdir(exist_ok=True)
    (ROOT / 'work' / 'browser-report.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report['checks'], indent=1))


if __name__ == '__main__':
    main()
