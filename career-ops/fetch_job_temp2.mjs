import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    
    // Wait longer for dynamic content and look for job-specific elements
    await page.waitForSelector('[data-testid="job-title"], [class*="job"], [class*="position"], h1', { timeout: 5000 }).catch(() => null);
    await page.waitForTimeout(3000);
    
    // Try to get the full HTML structure to debug
    const html = await page.evaluate(() => {
      return document.documentElement.outerHTML;
    });
    
    // Look for job-related text patterns
    if (html.includes('Manual QA') || html.includes('QA Engineer')) {
      console.log('Found job posting!');
      console.log(document.body.innerText);
    } else {
      console.log('Page content sample (first 2000 chars):');
      console.log(html.substring(0, 2000));
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
