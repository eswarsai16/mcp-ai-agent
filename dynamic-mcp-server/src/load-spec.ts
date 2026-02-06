import fs from 'node:fs';
import path from 'node:path';
import { OpenAPI3x, type OpenAPI } from './openapi-zod.js';

function preClean(raw: string): string {
  let txt = raw.replace(/^\uFEFF/, '');
  txt = txt.replace(/\/\*[\s\S]*?\*\//g, '');
  txt = txt.replace(/(^|[^:])\/\/.*$/gm, '$1');
  txt = txt.replace(/,\s*([}\]])/g, '$1');
  return txt;
}

// Helper
const HTTP_METHODS = ['get','post','put','delete','patch','head','options'] as const;
function formatIssuePath(pathArr: (string|number)[]): string {
  if (!Array.isArray(pathArr) || pathArr.length === 0) return '(root)';
  return pathArr.map(k => `[${String(k)}]`).join('');
}

export function listMissingOperationIds(json: any): string[] {
  const out: string[] = [];
  const paths = json?.paths;
  if (!paths || typeof paths !== 'object') return out;
  for (const [p, item] of Object.entries(paths)) {
    if (!item || typeof item !== 'object') continue;
    for (const m of HTTP_METHODS) {
      const op = (item as any)[m];
      if (!op) continue;
      const id = op?.operationId;
      if (typeof id !== 'string' || id.trim().length === 0) out.push(`${m.toUpperCase()} ${p}`);
    }
  }
  return out;
}

export function loadSpec(specPath: string): OpenAPI {
  const abs = path.resolve(specPath);
  if (!fs.existsSync(abs)) throw new Error(`OpenAPI spec not found at: ${abs}`);

  const raw = fs.readFileSync(abs, 'utf-8');
  let json: any;
  try { json = JSON.parse(preClean(raw)); }
  catch (err) { throw new Error(`Spec file is not valid JSON: ${abs}. ${(err as Error).message}`); }

  const missingOpIds = listMissingOperationIds(json);
  if (missingOpIds.length) {
    console.warn(`Missing operationId for ${missingOpIds.length} operation(s):`);
    for (const s of missingOpIds) console.warn(` - ${s}`);
  }

  const version = typeof json?.openapi === 'string' ? json.openapi : 'unknown';
  if (!String(version).startsWith('3.')) console.warn(`Note: openapi="${version}". Loader targets OpenAPI 3.x; continuing...`);

  const parsed = OpenAPI3x.safeParse(json);
  if (!parsed.success) {
    console.error('OpenAPI validation failed. Details:');
    for (const issue of parsed.error.issues) {
      const pathArray = issue.path.filter((p): p is string|number => typeof p === 'string' || typeof p === 'number');
      console.error(` • ${formatIssuePath(pathArray)}: ${issue.message}`);
    }
    throw new Error('OpenAPI spec validation failed.');
  }
  return parsed.data;
}

export default loadSpec;
