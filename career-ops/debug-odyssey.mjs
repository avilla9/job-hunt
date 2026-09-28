import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    console.log('Navigating to Odyssey jobs page...');
    await page.goto('https://jobs.ashbyhq.com/odyssey', { 
      waitUntil: 'domcontentloaded',
      timeout: 30000 
    });

    // Wait a bit more for dynamic content
    await page.waitForTimeout(3000);

    // Get page title
    const title = await page.title();
    console.log('Page title:', title);

    // Get all text content
    const pageText = await page.evaluate(() => {
      return document.body.innerText;
    });

    console.log('\n=== PAGE CONTENT (first 3000 chars) ===');
    console.log(pageText.substring(0, 3000));

    // Get all links
    const allLinks = await page.$$eval('a', elements => {
      return elements
        .map(el => ({
          text: el.textContent?.trim(),
          href: el.href
        }))
        .filter(j => j.text && j.text.length > 0 && j.text.length < 200);
    });

    console.log('\n=== ALL LINKS ===');
    allLinks.slice(0, 30).forEach(link => {
      console.log(`${link.text} -> ${link.href}`);
    });

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
