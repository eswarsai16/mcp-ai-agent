import { z } from 'zod';
import type { OpenAPI } from './openapi-zod.js';

// Global spec-health counters (write-safe if undefined)
const HEALTH: any = (globalThis as any).__mcpSpecHealth ?? ((globalThis as any).__mcpSpecHealth = {
  missingOperationId: 0,
  defaultedResponse: 0,
  inferredPathParams: 0,
  unresolvedRef: 0,
  cycleGuardFallback: 0,
});

function resolveRef(spec: OpenAPI, ref: string): any {
  if (!ref.startsWith('#/')) return undefined;
  const path = ref.slice(2).split('/');
  let cur: any = spec as any;
  for (const seg of path) { if (cur == null) return undefined; cur = cur[seg]; }
  return cur;
}

function mergeAllOf(all: any[], spec: OpenAPI): any {
  const target: any = { type: 'object', properties: {}, required: [] };
  for (const part of all) {
    const node = part?.$ref ? resolveRef(spec, part.$ref) : part;
    if (!node) continue;
    if (node.properties) Object.assign(target.properties, node.properties);
    if (Array.isArray(node.required)) target.required = Array.from(new Set([...target.required, ...node.required]));
  }
  return target;
}

// Add depth guard + seenRefs cache to break cycles
const MAX_DEPTH = 32; 

export function schemaToZod(schema: unknown, spec: OpenAPI, seenRefs: Set<string> = new Set(), depth = 0): z.ZodTypeAny {
  if (!schema || typeof schema !== 'object') return z.any();
  if (depth > MAX_DEPTH) {
    console.warn('schemaToZod: depth exceeded; falling back to z.any()');
    HEALTH.cycleGuardFallback++;
    return z.any();
  }

  const s = schema as any;

  if (s.$ref) {
    const ref = String(s.$ref);
    if (seenRefs.has(ref)) {
      console.warn(`schemaToZod: circular $ref "${ref}"; fallback z.any()`);
      HEALTH.cycleGuardFallback++;
      return z.any();
    }
    seenRefs.add(ref);
    const resolved = resolveRef(spec, ref);
    if (!resolved) {
      console.warn(`schemaToZod: unresolved $ref "${ref}"; fallback z.any()`);
      HEALTH.unresolvedRef++;
      return z.any();
    }
    return schemaToZod(resolved, spec, seenRefs, depth + 1);
  }

  if (Array.isArray(s.allOf) && s.allOf.length) {
    return schemaToZod(mergeAllOf(s.allOf, spec), spec, seenRefs, depth + 1);
  }

  //Guard unions against cycles; if any child forces fallback, still union the rest or fallback to z.any
  if (Array.isArray(s.oneOf) && s.oneOf.length) {
    const members = s.oneOf.map((m: any) => schemaToZod(m, spec, new Set(seenRefs), depth + 1));
    try { return members.length === 1 ? members[0] : z.union(members as [z.ZodTypeAny, z.ZodTypeAny, ...z.ZodTypeAny[]]); }
    catch { HEALTH.cycleGuardFallback++; return z.any(); }
  }
  if (Array.isArray(s.anyOf) && s.anyOf.length) {
    const members = s.anyOf.map((m: any) => schemaToZod(m, spec, new Set(seenRefs), depth + 1));
    try { return members.length === 1 ? members[0] : z.union(members as [z.ZodTypeAny, z.ZodTypeAny, ...z.ZodTypeAny[]]); }
    catch { HEALTH.cycleGuardFallback++; return z.any(); }
  }

  switch (s.type) {
    case 'string': {
      let str = z.string();
      if (s.pattern) { try { str = str.regex(new RegExp(s.pattern)); } catch { /* ignore bad regex */ } }
      return s.enum ? z.enum(s.enum as [string, ...string[]]) : str;
    }
    case 'integer': return z.number().int();
    case 'number': return z.number();
    case 'boolean': return z.boolean();
    case 'array': return z.array(schemaToZod(s.items ?? {}, spec, seenRefs, depth + 1));
    case 'object': {
      const props = s.properties ?? {};
      const required = new Set(s.required ?? []);
      const shape: Record<string, z.ZodTypeAny> = {};
      for (const [key, val] of Object.entries(props)) {
        const zodField = schemaToZod(val as any, spec, seenRefs, depth + 1);
        shape[key] = required.has(key) ? zodField : zodField.optional();
      }
      if (s.additionalProperties) {
        const ap = typeof s.additionalProperties === 'boolean' ? z.any() : schemaToZod(s.additionalProperties, spec, seenRefs, depth + 1);
        return z.object(shape).catchall(ap);
      }
      return z.object(shape);
    }
    default: return z.any();
  }
}
