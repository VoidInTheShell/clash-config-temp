import fs from 'node:fs';
import vm from 'node:vm';


const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error('usage: node run_submod.mjs <input-yaml> <output-yaml>');
}

const root = new URL('../../', import.meta.url);
const scriptPath = new URL('sublink/sublinkpro_node_metadata_rename.js', root);
vm.runInThisContext(fs.readFileSync(scriptPath, 'utf8'), { filename: scriptPath.pathname });

const input = fs.readFileSync(inputPath, 'utf8');
fs.writeFileSync(outputPath, subMod(input, 'mihomo'), 'utf8');
