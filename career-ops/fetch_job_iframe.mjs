import { chromium } from 'playwright';

const iframeUrl = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job?in_iframe=1';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1280, height: 1600 });
  
  try {
    console.error('[DEBUG] Navigating to iframe URL...');
    await page.goto(iframeUrl, { waitUntil: 'networkidle' });
    
    console.error('[DEBUG] Waiting for content...');
    await page.waitForTimeout(3000);
    
    // Get the full page text
    const text = await page.textContent('body');
    console.log(text);
    
  } catch (error) {
    console.error('[ERROR]', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
