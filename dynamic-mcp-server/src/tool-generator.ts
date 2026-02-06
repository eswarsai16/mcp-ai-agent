import { z } from 'zod';
import type { OpenAPI } from './openapi-zod.js';
import { schemaToZod } from './schema-to-zod.js';

//Global spec-health counters
const HEALTH: any = (globalThis as any).__mcpSpecHealth ?? ((globalThis as any).__mcpSpecHealth = {
  missingOperationId: 0,
  defaultedResponse: 0,
  inferredPathParams: 0,
  unresolvedRef: 0,
  cycleGuardFallback: 0,
});

type HttpMethod = 'get'|'post'|'put'|'delete'|'patch'|'head'|'options';

export interface ToolDef {
  name: string;
  description: string;
  inputSchema: z.ZodTypeAny;
  responseSchema: z.ZodTypeAny;
  method: HttpMethod;
  path: string;
}

function deref<T = any>(maybeRef: any, spec: OpenAPI): T {
  if (maybeRef?.$ref && String(maybeRef.$ref).startsWith('#/')) {
    return maybeRef.$ref.slice(2).split('/').reduce((cur: any, seg: string) => (cur ? cur[seg] : undefined), spec as any) ?? maybeRef;
  }
  return maybeRef;
}

function extractPathParams(path: string): string[] {
  const matches = [...path.matchAll(/\{([^}]+)\}/g)];
  return matches.map(m => m[1]);
}

export function buildToolDefs(spec: OpenAPI): ToolDef[] {
  const defs: ToolDef[] = [];
  const methods: HttpMethod[] = ['get','post','put','delete','patch','head','options'];

  for (const [path, pathItem] of Object.entries(spec.paths)) {
    for (const method of methods) {
      const op: any = (pathItem as any)[method];
      if (!op) continue;

      const hadOpId = !!op.operationId;
      const name: string = op.operationId ?? `${method}_${path.replace(/[{}]/g, '_')}`;
      if (!hadOpId) {
        console.warn(`Missing operationId for ${method.toUpperCase()} ${path}; generated: ${name}`);
        HEALTH.missingOperationId++;
      }

      const description = `${method.toUpperCase()} ${path}`;

      const params = (op.parameters ?? []).map((p: any) => deref(p, spec));
      const pathParamsShape: Record<string, z.ZodTypeAny> = {};
      const queryParamsShape: Record<string, z.ZodTypeAny> = {};

      for (const p of params) {
        if (!p?.in || !p?.name) continue;
        const base = p.schema ? schemaToZod(deref(p.schema, spec), spec) : z.any();
        if (p.in === 'path') pathParamsShape[p.name] = base;
        else if (p.in === 'query') queryParamsShape[p.name] = p.required ? base : base.optional();
      }

      const routeParams = extractPathParams(path);
      for (const rp of routeParams) {
        if (!pathParamsShape[rp]) {
          console.warn(`Inferred path param "${rp}" for ${method.toUpperCase()} ${path}`);
          HEALTH.inferredPathParams++;
          pathParamsShape[rp] = z.string();
        }
      }

      let bodySchema: z.ZodTypeAny | undefined;
      const content = deref(op.requestBody, spec)?.content;
      const jsonMedia = content?.['application/json'] ?? content?.['application/*+json'];
      if (jsonMedia?.schema) bodySchema = schemaToZod(deref(jsonMedia.schema, spec), spec);

      const inputSchema = z.object({
        params: z.object(pathParamsShape).default({}),
        query: z.object(queryParamsShape).default({}),
        body: (bodySchema ?? z.any()).optional(),
      });

      const responses = op.responses ?? {};
      const pickCode = ['200', '201'];
      let respSchema: z.ZodTypeAny = z.any();
      let defaulted = true;
      for (const code of pickCode) {
        const r = deref(responses[code], spec);
        const rJson = r?.content?.['application/json'] ?? r?.content?.['application/*+json'];
        if (rJson?.schema) {
          respSchema = schemaToZod(deref(rJson.schema, spec), spec);
          defaulted = false;
          break;
        }
      }
      if (defaulted) {
        HEALTH.defaultedResponse++;
      }

      defs.push({ name, description, inputSchema, responseSchema: respSchema, method, path });
    }
  }
  return defs;
}
