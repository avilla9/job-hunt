import fetch from 'node-fetch';

async function tryApiEndpoints() {
  const jobId = '6340';
  const endpoints = [
    `https://careers-en-nortal.icims.com/api/jobs/${jobId}`,
    `https://careers-en-nortal.icims.com/api/job/${jobId}`,
    `https://icims.com/api/jobs/${jobId}`,
    `https://careers-en-nortal.icims.com/api/openings/${jobId}`
  ];
  
  for (const endpoint of endpoints) {
    try {
      console.error(`[DEBUG] Trying: ${endpoint}`);
      const response = await fetch(endpoint, {
        headers: {
          'User-Agent': 'Mozilla/5.0',
          'Accept': 'application/json'
        },
        timeout: 5000
      });
      
      if (response.ok) {
        const data = await response.json();
        console.error(`[SUCCESS] Got data from ${endpoint}`);
        console.log(JSON.stringify(data, null, 2));
        return;
      }
    } catch (e) {
      console.error(`[FAIL] ${endpoint}: ${e.message}`);
    }
  }
  
  console.error('[ERROR] No API endpoint worked');
}

tryApiEndpoints();
