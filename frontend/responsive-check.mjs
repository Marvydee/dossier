import { chromium } from 'playwright';
import fs from 'node:fs';

const BASE = 'http://127.0.0.1:3000';
const OUT_DIR = '/tmp/responsive-shots';
fs.mkdirSync(OUT_DIR, { recursive: true });

const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 800 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
];

const PUBLIC_PAGES = ['/', '/pricing', '/login', '/signup', '/verify-email'];
const AUTH_PAGES = ['/dashboard', '/generate', '/billing'];

const EMAIL = process.argv[2];
const PASSWORD = process.argv[3];

async function checkOverflow(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    return {
      scrollWidth: doc.scrollWidth,
      clientWidth: doc.clientWidth,
      overflowing: doc.scrollWidth > doc.clientWidth + 1, // +1 tolerance for rounding
    };
  });
}

async function run() {
  const browser = await chromium.launch();
  const results = [];

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();

    for (const path of PUBLIC_PAGES) {
      await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
      const overflow = await checkOverflow(page);
      const filename = `${vp.name}${path.replace(/\//g, '_') || '_home'}.png`;
      await page.screenshot({ path: `${OUT_DIR}/${filename}`, fullPage: true });
      results.push({ viewport: vp.name, path, ...overflow, screenshot: filename });
    }

    await context.close();
  }

  // Authenticated pages: log in once per viewport (fresh context each time)
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();

    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    await page.fill('input[type="email"]', EMAIL);
    await page.fill('input[type="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(`${BASE}/dashboard`, { timeout: 15000 });

    for (const path of AUTH_PAGES) {
      await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
      const overflow = await checkOverflow(page);
      const filename = `${vp.name}${path.replace(/\//g, '_')}.png`;
      await page.screenshot({ path: `${OUT_DIR}/${filename}`, fullPage: true });
      results.push({ viewport: vp.name, path, ...overflow, screenshot: filename });
    }

    // Also check the mobile nav menu specifically on the dashboard
    if (vp.name === 'mobile') {
      try {
        await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
        await page.waitForTimeout(500);
        const menuButton = page.locator('button[aria-label="Toggle menu"]');
        await menuButton.waitFor({ state: 'visible', timeout: 5000 });
        await menuButton.click();
        await page.waitForTimeout(200);
        await page.screenshot({ path: `${OUT_DIR}/mobile_nav_open.png`, fullPage: true });
      } catch (e) {
        console.log('MOBILE NAV MENU CHECK FAILED:', e.message);
      }
    }

    await context.close();
  }

  await browser.close();

  console.log(JSON.stringify(results, null, 2));

  const overflowing = results.filter((r) => r.overflowing);
  if (overflowing.length > 0) {
    console.log('\n=== HORIZONTAL OVERFLOW DETECTED ===');
    for (const r of overflowing) {
      console.log(`${r.viewport} ${r.path}: scrollWidth=${r.scrollWidth} clientWidth=${r.clientWidth}`);
    }
    process.exitCode = 1;
  } else {
    console.log('\n=== NO HORIZONTAL OVERFLOW ON ANY PAGE/VIEWPORT ===');
  }
}

run();
