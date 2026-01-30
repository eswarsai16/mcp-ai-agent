import express from 'express';
import { setupSwagger } from './swagger.js';

import studentRoutes from './routes/student.routes.js';
import classRoutes from './routes/class.routes.js';
import teacherRoutes from './routes/teacher.routes.js';
import subjectRoutes from './routes/subject.routes.js';
import marksRoutes from './routes/marks.routes.js';

const app = express();
app.use(express.json());

setupSwagger(app);

app.use('/api/students', studentRoutes);
app.use('/api/classes', classRoutes);
app.use('/api/teachers', teacherRoutes);
app.use('/api/subjects', subjectRoutes);
app.use('/api/marks', marksRoutes);

app.get('/health', (_req, res) => res.status(200).json({ ok: true }));
app.get('/', (_req, res) => res.send('Welcome to School API. Docs at /api-docs'));

export default app;
