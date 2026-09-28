import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1280, height: 1600 });
  
  try {
    console.error('[DEBUG] Navigating...');
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    
    console.error('[DEBUG] Waiting for frames...');
    await page.waitForTimeout(5000);
    
    // Get all frames
    const frames = page.frames();
    console.error(`[DEBUG] Found ${frames.length} frames`);
    
    // Try each frame
    for (let i = 0; i < frames.length; i++) {
      try {
        const html = await frames[i].content().catch(() => '');
        if (html.includes('Manual QA')) {
          console.error(`[DEBUG] Frame ${i} has job content - HTML length: ${html.length}`);
          // Extract text from this frame
          const text = await frames[i].evaluate(() => document.body.innerText).catch(() => '');
          console.log(text);
          process.exit(0);
        }
      } catch (e) {
        console.error(`[DEBUG] Frame ${i}: ${e.message}`);
      }
    }
    
    // If not found in frames, try main page directly
    console.error('[DEBUG] Job not found in frames, trying main page...');
    const mainText = await page.evaluate(() => document.body.innerText);
    console.log(mainText);
    
  } catch (error) {
    console.error('[ERROR]', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
