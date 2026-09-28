import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1280, height: 1600 });
  
  // Intercept API calls
  const apiResponses = {};
  page.on('response', response => {
    if (response.url().includes('api') || response.url().includes('json')) {
      response.text().then(text => {
        console.error(`[API] ${response.url()}`);
        if (text.length < 5000) {
          apiResponses[response.url()] = text;
        }
      }).catch(() => {});
    }
  });
  
  try {
    console.error('[DEBUG] Navigating...');
    await page.goto(url, { waitUntil: 'networkidle' });
    
    console.error('[DEBUG] Waiting for dynamic content...');
    await page.waitForTimeout(3000);
    
    // Look for job title in page
    const title = await page.evaluate(() => {
      const selectors = ['h1', '[class*="title"]', '[data-testid*="title"]', 'main h1'];
      for (const sel of selectors) {
        const elem = document.querySelector(sel);
        if (elem) return elem.textContent.trim();
      }
      return '';
    }).catch(() => '');
    
    console.error(`[DEBUG] Job title found: ${title}`);
    
    // Try to get main content area
    const content = await page.evaluate(() => {
      // Try various selectors for main content
      const selectors = [
        'main',
        '[role="main"]',
        '[class*="content"]',
        '[class*="job-detail"]',
        '[class*="listing"]'
      ];
      
      for (const sel of selectors) {
        const elem = document.querySelector(sel);
        if (elem && elem.textContent.length > 200) {
          return elem.textContent;
        }
      }
      
      // Fallback: return everything except nav/footer
      const body = document.body.innerText;
      return body;
    }).catch(() => '');
    
    console.log(content);
    
  } catch (error) {
    console.error('[ERROR]', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
