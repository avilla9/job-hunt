import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1400, height: 1800 });
  
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    
    // Wait and look for JSON data embedded in page
    await page.waitForTimeout(5000);
    
    // Get the full HTML source
    const html = await page.content();
    
    // Search for job-related JSON or data
    const jsonMatch = html.match(/window\.__[A-Z_]+\s*=\s*\{[\s\S]*?\n[\s\S]*?\n\s*\}/);
    const jobDataMatch = html.match(/"(?:title|description|job|position)"[\s\S]*?\}/);
    
    // Search for "Manual QA" context
    const lines = html.split('\n');
    let jobStartIndex = -1;
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].includes('Manual QA') || lines[i].includes('QA Engineer')) {
        jobStartIndex = i - 10;
        break;
      }
    }
    
    if (jobStartIndex > 0) {
      console.error(`[DEBUG] Found job mention at line ${jobStartIndex + 10}`);
      // Print context around the match
      const context = lines.slice(Math.max(0, jobStartIndex), Math.min(lines.length, jobStartIndex + 50)).join('\n');
      console.log(context);
    } else {
      console.error('[DEBUG] Manual QA not found in initial scan, checking iframe content...');
      // Try to evaluate and print the document content
      const iframeContent = await page.evaluate(() => {
        const iframes = document.querySelectorAll('iframe');
        let content = '';
        for (let i = 0; i < iframes.length; i++) {
          try {
            const frame = iframes[i];
            if (frame.contentDocument) {
              content += `Frame ${i}:\n` + frame.contentDocument.body.innerText + '\n\n';
            }
          } catch (e) {}
        }
        return content || 'No accessible iframe content';
      });
      console.log(iframeContent);
    }
    
  } catch (error) {
    console.error('[ERROR]', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
