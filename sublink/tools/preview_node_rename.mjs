import fs from 'node:fs';
import vm from 'node:vm';


const root = new URL('../../', import.meta.url);
const scriptPath = new URL('sublink/sublinkpro_node_metadata_rename.js', root);
const script = fs.readFileSync(scriptPath, 'utf8');
vm.runInThisContext(script, { filename: scriptPath.pathname });

const nodes = JSON.parse(fs.readFileSync(0, 'utf8'));
const countryNames = {
  AU: '澳大利亚',
  GB: '英国',
  HK: '香港',
  IN: '印度',
  JP: '日本',
  KR: '韩国',
  MY: '马来西亚',
  SG: '新加坡',
  TR: '土耳其',
  TW: '台湾',
  US: '美国'
};

const renamed = filterNode(nodes, 'mihomo');
const names = renamed.map((node) => {
  const countryName = countryNames[node.LinkCountry] || node.LinkCountry || '未知';
  return `${node.Name}${countryName}${node.LinkName ? ` ${node.LinkName}` : ''}`.trim();
});

const samples = (predicate, limit = 6) => names.filter(predicate).slice(0, limit);
const result = {
  inputCount: nodes.length,
  outputCount: renamed.length,
  removedInfoNodes: nodes.length - renamed.length,
  nameFallbackExamples: {
    regionalFlag: fallbackCountryFromName('🇹🇼 台湾专线 0.5x'),
    chineseName: fallbackCountryFromName('香港专线 1.5x'),
    englishName: fallbackCountryFromName('US Premium 01')
  },
  uniqueNames: new Set(names).size === names.length,
  duplicateFlagCount: names.filter((name) => /^[🇦-🇿]{2}\s+[🇦-🇿]{2}/u.test(name)).length,
  airportSemanticCount: names.filter((name) => /(高速|专线|直连|BGP|CTCU|CMCU|住宅IP)/i.test(name)).length,
  regionCounts: {
    US: names.filter((name) => name.startsWith('🇺🇸')).length,
    HK: names.filter((name) => name.startsWith('🇭🇰')).length,
    SG: names.filter((name) => name.startsWith('🇸🇬')).length,
    JP: names.filter((name) => name.startsWith('🇯🇵')).length,
    other: names.filter((name) => !/^(?:🇺🇸|🇭🇰|🇸🇬|🇯🇵)/u.test(name)).length
  },
  featureCounts: {
    homeBroadband: names.filter((name) => /(?:^|\s)家宽(?:\s|$)/.test(name)).length,
    rate: names.filter((name) => /(?:^|\s)(?:0\.1x|0\.5x|1\.5x)(?:\s|$)/i.test(name)).length,
    allAI: names.filter((name) => /(?:^|\s)AI(?:\s|$)/.test(name)).length,
    Claude: names.filter((name) => /(?:^|\s)(?:AI|Claude)(?:\s|$)/.test(name)).length,
    Gemini: names.filter((name) => /(?:^|\s)(?:AI|Gemini)(?:\s|$)/.test(name)).length,
    OpenAI: names.filter((name) => /(?:^|\s)(?:AI|OpenAI)(?:\s|$)/.test(name)).length,
    Netflix: names.filter((name) => /(?:^|\s)Netflix(?:\s|$)/.test(name)).length,
    selfBuilt: names.filter((name) => /(?:^|\s)自建(?:\s|$)/.test(name)).length
  },
  samples: {
    Taiwan: samples((name) => name.startsWith('🇹🇼')),
    HongKong: samples((name) => name.startsWith('🇭🇰')),
    homeBroadband: samples((name) => /(?:^|\s)家宽(?:\s|$)/.test(name), names.length),
    allAI: samples((name) => /(?:^|\s)AI(?:\s|$)/.test(name)),
    partialAI: samples((name) => !/(?:^|\s)AI(?:\s|$)/.test(name) && /(?:^|\s)(?:Claude|Gemini|OpenAI)(?:\s|$)/.test(name)),
    Netflix: samples((name) => /(?:^|\s)Netflix(?:\s|$)/.test(name)),
    rate: samples((name) => /(?:^|\s)(?:0\.1x|0\.5x|1\.5x)(?:\s|$)/i.test(name)),
    selfBuilt: samples((name) => /(?:^|\s)自建(?:\s|$)/.test(name))
  }
};

console.log(JSON.stringify(result, null, 2));
