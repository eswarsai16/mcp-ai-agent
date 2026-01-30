import fs from 'fs';
import path from 'path';
import { load } from 'js-yaml';
import swaggerUi from 'swagger-ui-express';
import type { Express } from 'express';

const SPEC_CANDIDATES = [
  path.join(process.cwd(), 'swagger.yaml'),
  path.join(process.cwd(), 'swagger.json'),
  path.join(process.cwd(), 'src', 'swagger.yaml'),
  path.join(process.cwd(), 'src', 'swagger.json'),
];

function loadOpenApiSpec(): Record<string, unknown> {
  for (const filePath of SPEC_CANDIDATES) {
    if (fs.existsSync(filePath)) {
      const text = fs.readFileSync(filePath, 'utf8');
      if (filePath.endsWith('.yaml') || filePath.endsWith('.yml')) {
        return load(text) as Record<string, unknown>;
      }
      return JSON.parse(text) as Record<string, unknown>;
    }
  }
  throw new Error(
    `OpenAPI spec not found. Expected one of:\n${SPEC_CANDIDATES.map(p => ` - ${p}`).join('\n')}`
  );
}

export function setupSwagger(app: Express) {
  const spec = loadOpenApiSpec();

  app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(spec));

  app.get('/api-docs.json', (_req, res) => res.json(spec));
}
