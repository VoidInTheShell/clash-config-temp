import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { execFileSync } from 'node:child_process';

const scriptPath = new URL('../sublinkpro_node_metadata_rename.js', import.meta.url);
const source = fs.readFileSync(scriptPath, 'utf8');
const context = vm.createContext({});
vm.runInContext(source, context);
const cases = [
  ['自建', true], ['自建-Pub', true], ['自建JP', true],
  [' 自建-家宽 ', true], ['非自建', false], ['机场-自建', false], ['', false],
];
for (const [Group, expected] of cases) {
  const [node] = context.filterNode([{
    Group, Name: 'JP XHTTP', LinkName: 'JP XHTTP', LinkCountry: 'JP',
    QualityStatus: 'success', IsResidential: true,
  }], 'mihomo');
  assert.equal(node.Name.includes('__SUBLINK_SELF_NAME_'), expected, Group);
}

const originals = ['JP XHTTP', 'JP HY2', 'DE XHTTP', 'DE HY2', 'US XHTTP',
  'US HY2', '家宽 [JP] (A)+ #1 "test" \\edge', "家宽 'quoted'", 'US1-纽约-无限流量', '官网节点'];
const nodes = originals.map((name, index) => ({
  ID: index + 1, Group: '自建-Pub', Name: `${name}@remark`, LinkName: name,
  NameMode: 'link', LinkCountry: 'JP', QualityStatus: 'success', IsResidential: true,
}));
nodes.push({ ID: 100, Group: '自建', Name: 'HK中转', LinkName: 'upstream', NameMode: 'remark' });
nodes.push({ ID: 200, Group: 'airport', Name: 'airport', LinkName: 'HK', LinkCountry: 'HK', QualityStatus: 'success', IsResidential: true });
const renamed = context.filterNode(nodes, 'mihomo');
const stageNames = renamed.map(node => `${node.Name}${node.LinkCountry || '未知'} ${node.LinkName || ''}`.trim());
const input = `proxies:\n${stageNames.map(name => `  - name: ${JSON.stringify(name)}\n    type: direct`).join('\n')}
proxy-groups:
  - name: 家宽手选
    type: select
    include-all: true
    filter: 家宽
  - name: 自建节点
    type: select
    proxies: []
  - name: 自建选1
    type: select
    proxies: []
  - name: 自建选2
    type: select
    proxies: []
  - name: 自建选3
    type: select
    proxies: []
  - exclude-filter: "家宽|^\\U0001F1EF\\U0001F1F5"
    include-all: true
    name: 自动选择
    type: url-test
  - include-all: true
    name: 其他
    type: select
rules:
  - MATCH,自建节点
`;
// The production hooks run in independent VMs; no global state can be shared.
const renderContext = vm.createContext({});
vm.runInContext(source, renderContext);
const output = renderContext.subMod(input, 'mihomo');
const config = JSON.parse(execFileSync('python3', ['-c', 'import sys,yaml,json; print(json.dumps(yaml.safe_load(sys.stdin.read())))'], { input: output, encoding: 'utf8' }));
const groups = Object.fromEntries(config['proxy-groups'].map(group => [group.name, group]));
assert.deepEqual(groups['自建节点'].proxies, [...originals, 'HK中转']);
assert.equal(groups['自建节点']['include-all'], undefined);
assert.equal(groups['家宽手选'].proxies.length, 4);
for (const name of ['自建选1', '自建选2', '自建选3']) {
  assert.deepEqual(groups[name].proxies, [...originals, 'HK中转']);
  assert.equal(groups[name].type, 'select');
  assert.equal(groups[name]['include-all'], undefined);
  assert.ok(groups['家宽手选'].proxies.includes(name));
}
for (const group of [groups['自动选择'], groups['其他']]) {
  const filter = new RegExp(group['exclude-filter']);
  for (const name of [...originals, 'HK中转']) assert.ok(filter.test(name), name);
  assert.equal(filter.test('JP XHTTP suffix'), false);
}
assert.equal(config.proxies.length, nodes.length);
assert.ok(new RegExp(groups['自动选择']['exclude-filter']).test('🇭🇰 香港 家宽'));
assert.doesNotMatch(output, /__SUBLINK_SELF_NAME_|__END_SELF_NAME__/);
assert.equal(renderContext.subMod(output, 'mihomo'), output);
console.log('PASS: prefixes, source naming modes, untouched self names, residential overlap, YAML/regex escaping, separate VMs, idempotence');
