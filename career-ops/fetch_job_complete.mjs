import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1400, height: 2000 });
  
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    
    // Wait longer and scroll to trigger lazy loading
    await page.waitForTimeout(4000);
    
    // Try to find and extract the main job content area
    const content = await page.evaluate(async () => {
      // Wait a bit for dynamic content
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Try multiple strategies to find job content
      let result = '';
      
      // Strategy 1: Look for common job posting containers
      const selectors = [
        '.job-description',
        '[class*="job-detail"]',
        '[data-testid*="job"]',
        '.position-details',
        '[class*="position"]',
        'main',
        '[role="main"]',
        '.content-main',
        '#job-content',
        '.job-content'
      ];
      
      for (const sel of selectors) {
        const elem = document.querySelector(sel);
        if (elem && elem.innerText.length > 200) {
          result = elem.innerText;
          break;
        }
      }
      
      // If still empty, try to extract from all visible text
      if (!result) {
        // Get all text but exclude nav/footer
        const nav = document.querySelector('nav');
        const footer = document.querySelector('footer');
        const navText = nav ? nav.innerText : '';
        const footerText = footer ? footer.innerText : '';
        const allText = document.body.innerText;
        
        // Remove nav and footer portions
        result = allText.replace(navText, '').replace(footerText, '').trim();
      }
      
      return result;
    });
    
    if (content && content.trim().length > 100) {
      console.log(content);
    } else {
      console.error('[DEBUG] Content too short, trying alternate approach...');
      // Fallback: get the page with all whitespace preserved
      const allText = await page.evaluate(() => {
        // Extract all text nodes
        const texts = [];
        const walk = document.createTreeWalker(
          document.body,
          NodeFilter.SHOW_TEXT,
          null,
          false
        );
        let node;
        while (node = walk.nextNode()) {
          const text = node.textContent.trim();
          if (text && text.length > 0) {
            texts.push(text);
          }
        }
        return texts.join('\n');
      });
      console.log(allText);
    }
    
  } catch (error) {
    console.error('[ERROR]', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
