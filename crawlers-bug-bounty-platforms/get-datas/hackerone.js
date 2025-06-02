const fs = require('fs');
const puppeteer = require('puppeteer');

async function getBountyValues(handle) {
  const url = `https://hackerone.com/${handle}?type=team`;
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  await page.goto(url);
  await page.waitForTimeout(4000);

  const bountyClasses = ['spec-bounty-table-low', 'spec-bounty-table-medium', 'spec-bounty-table-high', 'spec-bounty-table-critical'];
  const bountyValues = {};

  for (const tdClass of bountyClasses) {
    try {
      const tdElements = await page.$$(`td.${tdClass}`);
      if (tdElements.length > 0) {
        const tdWithSpan = await page.evaluateHandle((td) => td.querySelector('span'), tdElements[0]);
        const value = await page.evaluate((span) => span ? span.innerText : null, tdWithSpan);
        bountyValues[tdClass] = value;
      } else {
        bountyValues[tdClass] = null;
      }
    } catch (error) {
      bountyValues[tdClass] = null;
    }
  }

  await browser.close();

  return { handle, ...bountyValues };
}

async function processHandles() {
  const handlesFile = 'files/full-list.txt';
  const handles = fs.readFileSync(handlesFile, 'utf8').split('\n').filter(handle => handle.trim() !== '');

  const bountyResults = [];

  for (const handle of handles) {
    const bountyValue = await getBountyValues(handle);
    bountyResults.push(bountyValue);
  }

  return bountyResults;
}

function printOutput(results) {
  for (const result of results) {
    const { handle, 'spec-bounty-table-low': low, 'spec-bounty-table-medium': medium, 'spec-bounty-table-high': high, 'spec-bounty-table-critical': critical } = result;
    console.log(`${handle}; ${low || '0'}; ${medium || '0'}; ${high || '0'}; ${critical || '0'}`);
  }
}

processHandles()
  .then(results => {
    console.log('Program; Low; Medium; High; Critical');
    printOutput(results);
  })  
  .catch(err => console.error('Ocorreu um erro:', err));