const axios = require('axios');
const fs = require('fs');

const baseURL = 'https://bugcrowd.com';
const targetGroupsEndpoint = '/target_groups';

const headers = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0',
  'Accept': '*/*',
  'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
  'Accept-Encoding': 'gzip, deflate, br',
  'Referer': 'https://bugcrowd.com/ifood-og',
  'x-csrf-token': '{DEFINIR_O_TOKEN_AQUI',
  'DNT': '1',
  'Connection': 'keep-alive',
  'Cookie': 'DEFINIR_O_COOKIE_AQUI'
};

function fetchBountyValues(programName) {
  const url = `${baseURL}${programName}${targetGroupsEndpoint}`;

  axios.get(url, { headers })
    .then(response => {
      const responseObject = response.data;
      const groups = responseObject.groups;

      for (const group of groups) {
        const rewardRanges = group.reward_range;
        console.log(`${programName}; ${rewardRanges[4].min}; ${rewardRanges[3].min}; ${rewardRanges[2].min}; ${rewardRanges[1].min}`);
      }
      console.log('\n');
    })
    .catch(error => {
      // console.log(error);
    });
}

fs.readFile('programs.txt', 'utf8', (err, data) => {
  if (err) {
    return;
  }

  const programNames = data.trim().split('\n');

  for (const programName of programNames) {
    fetchBountyValues(programName);
  }
});