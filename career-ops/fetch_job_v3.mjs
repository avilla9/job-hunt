import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
  });
  
  // Set viewport
  await page.setViewportSize({ width: 1280, height: 720 });
  
  try {
    console.error('[DEBUG] Navigating...');
    await page.goto(url, { waitUntil: 'networkidle' });
    
    console.error('[DEBUG] Page loaded, waiting for content...');
    await page.waitForTimeout(2000);
    
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
