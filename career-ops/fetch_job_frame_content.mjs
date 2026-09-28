import { chromium } from 'playwright';

const url = 'https://careers-en-nortal.icims.com/jobs/6340/manual-qa-engineer/job';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.setViewportSize({ width: 1280, height: 1600 });
  
  try {
    console.error('[DEBUG] Navigating to main page...');
    await page.goto(url, { waitUntil: 'networkidle' });
    
    console.error('[DEBUG] Waiting for frames to load...');
    await page.waitForTimeout(3000);
    
    // Get all frames
    const frames = page.frames();
    console.error(`[DEBUG] Found ${frames.length} frames`);
    
    // Look for job content in each frame
    for (let i = 0; i < frames.length; i++) {
      try {
        const frameText = await frames[i].textContent('body').catch(() => '');
        if (frameText && frameText.includes('Manual QA') || frameText.includes('QA Engineer') || frameText.includes('job')) {
          console.error(`[DEBUG] Found job content in frame ${i}`);
          console.log(frameText);
          break;
        }
      } catch (e) {
        // Continue to next frame
      }
    }
    
  } catch (error) {
    console.error('[ERROR]', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
