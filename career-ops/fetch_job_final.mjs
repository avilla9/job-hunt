import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    
    // Wait for job content to load
    await page.waitForSelector('[class*="job"], [class*="position"]', { timeout: 5000 }).catch(() => null);
    await page.waitForTimeout(3000);
    
    // Extract all text content
    const content = await page.evaluate(() => {
      return document.body.innerText;
    });
    
    console.log(content);
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
