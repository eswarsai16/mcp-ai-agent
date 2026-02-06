import { z } from 'zod';

export const ReferenceObject = z.object({ $ref: z.string() }).passthrough();

export const SchemaObject: z.ZodTypeAny = z.object({
  type: z.enum(['string','number','integer','boolean','array','object']).optional(),
  properties: z.record(z.string(), z.lazy(() => SchemaObject)).optional(),
  items: z.lazy(() => SchemaObject).optional(),
  required: z.array(z.string()).optional(),
  enum: z.array(z.union([z.string(), z.number()])).optional(),
  format: z.string().optional(),
  pattern: z.string().optional(),
  allOf: z.array(z.lazy(() => SchemaObject)).optional(),
  oneOf: z.array(z.lazy(() => SchemaObject)).optional(),
  anyOf: z.array(z.lazy(() => SchemaObject)).optional(),
  additionalProperties: z.union([z.boolean(), z.lazy(() => SchemaObject)]).optional(),
  $ref: z.string().optional(),
}).passthrough();

export const MediaTypeObject = z.object({ schema: z.union([SchemaObject, ReferenceObject]).optional() }).passthrough();
export const RequestBodyObject = z.object({ content: z.record(z.string(), MediaTypeObject), required: z.boolean().optional() }).passthrough();
export const ResponseObject = z.object({ description: z.string().optional(), content: z.record(z.string(), MediaTypeObject).optional() }).passthrough();

export const ParameterObject = z.object({
  name: z.string(),
  in: z.enum(['path','query','header','cookie']),
  required: z.boolean().optional(),
  description: z.string().optional(),
  schema: z.union([SchemaObject, ReferenceObject]).optional(),
}).passthrough();

export const ParameterOrRef = z.union([ParameterObject, ReferenceObject]);

export const OperationObject = z.object({
  operationId: z.string(),
  parameters: z.array(ParameterOrRef).optional(),
  requestBody: z.union([RequestBodyObject, ReferenceObject]).optional(),
  responses: z.record(z.string(), z.union([ResponseObject, ReferenceObject])),
  tags: z.array(z.string()).optional(),
  summary: z.string().optional(),
}).passthrough();

export const PathItemMethods = z.object({
  get: OperationObject.optional(),
  post: OperationObject.optional(),
  put: OperationObject.optional(),
  delete: OperationObject.optional(),
  patch: OperationObject.optional(),
  head: OperationObject.optional(),
  options: OperationObject.optional(),
}).refine(obj =>
  obj.get || obj.post || obj.put || obj.delete || obj.patch || obj.head || obj.options,
  { message: 'PathItem must have at least one HTTP method operation' }
);

export const ComponentsObject = z.object({
  schemas: z.record(z.string(), z.union([SchemaObject, ReferenceObject])).optional(),
  parameters: z.record(z.string(), z.union([ParameterObject, ReferenceObject])).optional(),
}).passthrough();

export const OpenAPI3x = z.object({
  openapi: z.string().startsWith('3.'),
  info: z.object({ title: z.string(), version: z.string() }),
  servers: z.array(z.object({ url: z.string() })).optional(),
  paths: z.record(z.string(), PathItemMethods),
  components: ComponentsObject.optional(),
}).passthrough();

export type OpenAPI = z.infer<typeof OpenAPI3x>;