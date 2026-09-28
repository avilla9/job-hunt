import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    // Target the two most relevant roles
    const roles = [
      { 
        name: 'Sr. Full Stack Software Engineer',
        url: 'https://jobs.ashbyhq.com/odyssey/4a947f92-00a1-4da9-b2bd-061865bd208c'
      },
      {
        name: 'Founding Security Engineer',
        url: 'https://jobs.ashbyhq.com/odyssey/68b8890a-2bad-4d09-96c6-292dd63b9c03'
      },
      {
        name: 'Full Stack Engineer',
        url: 'https://jobs.ashbyhq.com/odyssey/5158a3e1-ddde-4253-a895-a82a9ab2e2d4'
      }
    ];

    for (const role of roles) {
      console.log(`\n${'='.repeat(80)}`);
      console.log(`ROLE: ${role.name}`);
      console.log(`URL: ${role.url}`);
      console.log(`${'='.repeat(80)}\n`);

      await page.goto(role.url, { 
        waitUntil: 'networkidle',
        timeout: 30000 
      });

      // Wait for content to load
      await page.waitForTimeout(1000);

      // Extract full job description
      const jobContent = await page.evaluate(() => {
        // Get all main content
        const body = document.body;
        return body.innerText;
      });

      console.log(jobContent);
      console.log('\n');
    }

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
})();
