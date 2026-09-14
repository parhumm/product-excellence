"""The control map, checked in a real browser: it is the only place observe.js runs."""
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1].joinpath('engine/observe.js').read_text()

# A captcha checkbox as sites really build one: a div with a role, labelled by a sibling that
# also carries a ticking countdown. The second row is the same widget left over from a previous
# screen, still in the DOM but painted under the app, so no click could ever reach it.
PAGE = """<!doctype html><meta charset="utf-8"><body style="margin:0">
<div class="row"><div id="cb" role="checkbox" aria-checked="false" tabindex="0" style="width:24px;height:24px"><span></span></div>
<span style="display:block">I am not a robot</span><span style="display:block">expires in 117 seconds</span></div>
<div style="position:relative;height:60px">
 <div id="stale" role="checkbox" tabindex="0" style="position:absolute;top:0;left:0;width:24px;height:24px"></div>
 <div id="app" style="position:absolute;top:0;left:0;width:300px;height:60px;background:#fff"></div>
</div>
<button>Continue</button>
<a href="https://example.com/">Home</a>
<input id="phone" value="0912">
</body>"""


@pytest.mark.asyncio
async def test_a_div_built_widget_is_actionable_and_carries_its_sibling_label():
    playwright = pytest.importorskip('playwright.async_api')
    try:
        async with playwright.async_playwright() as p:
            browser = await p.chromium.launch()
            page = await (await browser.new_context()).new_page()
            await page.set_content(PAGE)
            controls = (await page.evaluate(SCRIPT))['controls']
            await browser.close()
    except Exception as e:  # no browser binary on this machine
        pytest.skip(f'chromium unavailable: {e}')

    boxes = [c for c in controls if c['role'] == 'checkbox']
    assert boxes, 'a div with role=checkbox must be actionable, or a captcha cannot be cleared'
    # The covered leftover is not offered: clicking it could only time out.
    assert len(boxes) == 1, f'a covered control must not reach the worker: {boxes}'
    # The label is the row's first line, so a countdown cannot rename the control every second.
    assert boxes[0]['text'] == 'I am not a robot'
    # The ordinary controls keep the names they always had, and only real fields report filled.
    named = {c['text']: c for c in controls}
    assert named['Continue']['tag'] == 'button' and named['Continue']['filled'] is False
    assert named['Home']['href'] == 'https://example.com/'
    field = next(c for c in controls if c['tag'] == 'input')
    assert field['filled'] is True and '0912' not in str(field), 'the flag travels, the value never does'
