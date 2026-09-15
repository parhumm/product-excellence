"""Wait for the destination view, never a heading left by the previous route."""
from playwright.async_api import expect

HEADINGS = {
    'overview': 'See the journey.Understand what gets in the way.',
    'missions': 'Missions', 'journeys': 'Journeys', 'new': 'New mission', 'runs': 'Runs',
    'findings': 'Findings', 'benchmark': 'Benchmark', 'compare': 'Compare releases',
    'network': 'Network & routes', 'settings': 'Settings',
}


async def open_view(page, route, base_url='http://127.0.0.1:8741'):
    await page.goto(base_url.rstrip('/') + '/#' + route)
    await expect(page.locator('h1')).to_have_text(HEADINGS[route], timeout=30000)
    await expect(page.locator('h1')).to_be_visible()
