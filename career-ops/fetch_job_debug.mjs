import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.createContext({
    viewport: { width: 1280, height: 720 }
  });
  const page = await context.newPage();
  
  try {
    console.error('[DEBUG] Navigating to URL...');
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    
    console.error('[DEBUG] Checking page title:', await page.title());
    
    // Try to dismiss cookie consent
    await page.click('[class*="cookie"], [class*="consent"], button:has-text("Accept")')
      .catch(() => null);
    
    await page.waitForTimeout(2000);
    
    // Look for main job content area
    const jobContent = await page.evaluate(() => {
      const selectors = [
        '[class*="job-description"]',
        '[class*="job-content"]',
        '[data-testid*="job"]',
        'main',
        '[role="main"]',
        '[class*="position-detail"]'
      ];
      
      for (const selector of selectors) {
        const elem = document.querySelector(selector);
        if (elem && elem.innerText.length > 100) {
          return elem.innerText;
        }
      }
      
      // Fallback to body
      return document.body.innerText;
    });
    
    console.log(jobContent);
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  } finally {
    await context.close();
    await browser.close();
  }
})();
