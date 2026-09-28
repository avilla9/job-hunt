import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    console.log('Navigating to Odyssey jobs page...');
    await page.goto('https://jobs.ashbyhq.com/odyssey', { 
      waitUntil: 'networkidle',
      timeout: 30000 
    });

    // Wait for job listings to appear
    await page.waitForSelector('a[href*="jobs.ashbyhq.com"]', { timeout: 10000 }).catch(() => {});

    // Get all job links
    const jobLinks = await page.$$eval('a[href*="jobs.ashbyhq.com"]', elements => {
      return elements
        .map(el => ({
          text: el.textContent?.trim(),
          href: el.href
        }))
        .filter(j => j.text && j.text.length > 0 && (
          j.text.includes('Full Stack Engineer') || 
          j.text.includes('Senior Full Stack') ||
          j.text.includes('Founding Security Engineer')
        ));
    });

    console.log('Found job listings:', jobLinks);

    if (jobLinks.length > 0) {
      // Extract Senior Full Stack Engineer first if available
      let targetJob = jobLinks.find(j => j.text.includes('Senior Full Stack')) || 
                      jobLinks.find(j => j.text.includes('Full Stack Engineer')) ||
                      jobLinks[0];
      
      console.log(`\nNavigating to: ${targetJob.text} (${targetJob.href})`);
      await page.goto(targetJob.href, { waitUntil: 'networkidle', timeout: 30000 });

      // Extract job description
      const jobContent = await page.evaluate(() => {
        // Try multiple selectors for job content
        const mainContent = 
          document.querySelector('[class*="job-description"]') ||
          document.querySelector('[class*="JobDescription"]') ||
          document.querySelector('main') ||
          document.querySelector('[role="main"]') ||
          document.querySelector('article') ||
          document.body;

        if (mainContent) {
          return mainContent.innerText;
        }
        return document.body.innerText;
      });

      console.log('\n=== FULL JOB DESCRIPTION ===\n');
      console.log(jobContent);
    } else {
      console.log('No Full Stack Engineer jobs found');
    }
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
