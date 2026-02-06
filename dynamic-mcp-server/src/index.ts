import 'dotenv/config';
import express, { Request, Response } from 'express';
import cors, { CorsOptions } from 'cors';
import { z } from 'zod';
import { loadSpec } from './load-spec.js';
import { buildToolDefs } from './tool-generator.js';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';

const PORT = Number(process.env.PORT ?? 4000);

const SCHOOL_API_BASE = process.env.SCHOOL_API_BASE ?? 'http://localhost:3000';
const ENABLE_JSON_RESPONSE = (process.env.ENABLE_JSON_RESPONSE ?? 'true') === 'true';
const ALLOWED_ORIGINS: string[] = (process.env.ALLOWED_ORIGINS ?? '').split(',').map(s => s.trim()).filter(Boolean);
const ALLOWED_HOSTS: string[] = (process.env.ALLOWED_HOSTS ?? '').split(',').map(s => s.trim()).filter(Boolean);

const server = new McpServer(
  { name: 'dynamic-mcp-server', version: '1.0.0' },
  { capabilities: { tools: { listChanged: false }, logging: {} } }
);

type HttpMethod = 'get'|'post'|'put'|'delete'|'patch'|'head'|'options';

// Proxy
async function callAPI(method: HttpMethod, path: string, input: any) {
  let url = SCHOOL_API_BASE + path.replace(/\{([^\}]+)\}/g, (_m, k) => encodeURIComponent(input?.params?.[k] ?? ''));
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(input?.query ?? {})) if (v !== undefined && v !== null) q.append(k, String(v));
  if ([...q.keys()].length) url += `?${q.toString()}`;
  const hasBody = method === 'post' || method === 'put' || method === 'patch';
  const init: RequestInit = {
    method: method.toUpperCase(),
    headers: { 'Content-Type': 'application/json' },
    ...(hasBody ? { body: JSON.stringify(input?.body ?? {}) } : {})
  };
  const resp = await fetch(url, init);
  const text = await resp.text();
  try { return JSON.parse(text); } catch { return text; }
}

const SPEC_PATH = process.env.SWAGGER_SCHEMA_PATH ?? '../school-api/swagger-schema.json';
const spec = loadSpec(SPEC_PATH);
const defs = buildToolDefs(spec);
console.log(`Loaded OpenAPI ${spec.openapi ?? 'unknown'}; registering ${defs.length} tool(s).`);

for (const def of defs) {
  const shape = (def.inputSchema as z.ZodObject<any>).shape;
  server.tool(
    def.name,
    def.description ?? `${def.method.toUpperCase()} ${def.path}`,
    shape,
    async (args: any) => {
      const parsed = (def.inputSchema as z.ZodObject<any>).parse(args);
      const result = await callAPI(def.method as any, def.path, parsed);
      const text = typeof result === 'string' ? result : JSON.stringify(result);
      const structured =
        Array.isArray(result) ? { items: result } :
        result && typeof result === 'object' ? result :
        { text: String(result) };
      return { content: [{ type: 'text' as const, text }], structuredContent: structured };
    }
  );
}

const app = express();
app.use(express.json());
const corsOptions: CorsOptions = {
  origin: (origin, cb) => {
    if (!origin || ALLOWED_ORIGINS.length === 0 || ALLOWED_ORIGINS.includes(origin)) cb(null, true);
    else cb(new Error('Origin not allowed'));
  }
};
app.use(cors(corsOptions));
const hostAllowed = (hostname: string) => ALLOWED_HOSTS.length === 0 || ALLOWED_HOSTS.includes(hostname);

app.post('/mcp', async (req: Request, res: Response) => {
  if (!hostAllowed(req.hostname)) { res.status(403).json({ error: 'Host not allowed' }); return; }
  const transport = new StreamableHTTPServerTransport({
    enableJsonResponse: ENABLE_JSON_RESPONSE,
    ...(ALLOWED_ORIGINS.length ? { allowedOrigins: ALLOWED_ORIGINS } : {}),
    ...(ALLOWED_HOSTS.length ? { allowedHosts: ALLOWED_HOSTS } : {}),
  });
  res.on('close', () => { transport.close().catch(() => {}); });
  await server.connect(transport as any);
  await transport.handleRequest(req, res, req.body);
});

app.delete('/mcp', async (_req: Request, res: Response) => { res.status(204).end(); });
app.get('/health', (_req, res) => res.json({ ok: true }));

//Expose /spec-health with counters gathered in global
app.get('/spec-health', (_req, res) => {
  const health = (globalThis as any).__mcpSpecHealth ?? {};
  res.json({ ok: true, health });
});

app.listen(PORT, () => { console.log(`✅ Dynamic MCP Server listening at http://localhost:${PORT}/mcp`); });
