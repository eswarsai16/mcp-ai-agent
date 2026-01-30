import { Request, Response } from 'express';
import { TeacherService } from '../services/TeacherService.js';

export const TeacherController = {
  async list(_: Request, res: Response) {
    try { res.status(200).json(await TeacherService.getAll()); }
    catch { res.status(500).json({ error: 'Failed to list teachers' }); }
  },

  async get(req: Request, res: Response) {
    try {
      const row = await TeacherService.getById(req.params.id);
      if (!row) return res.status(404).json({ error: 'Teacher not found' });
      res.status(200).json(row);
    } catch { res.status(500).json({ error: 'Failed to get teacher' }); }
  },

  async create(req: Request, res: Response) {
    const { teacher_id, name, class_id } = req.body;
    if (!teacher_id || !name)
      return res.status(400).json({ error: 'teacher_id and name are required' });
    try {
      await TeacherService.create({ teacher_id, name, class_id });
      res.status(201).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_NO_REFERENCED_ROW_2')
        return res.status(400).json({ error: 'class_id must reference an existing class' });
      res.status(500).json({ error: 'Failed to create teacher' });
    }
  },

  async update(req: Request, res: Response) {
    const { name, class_id } = req.body;
    if (name === undefined && class_id === undefined)
      return res.status(400).json({ error: 'Provide name or class_id' });
    try {
      const ok = await TeacherService.update(req.params.id, { name, class_id });
      if (!ok) return res.status(404).json({ error: 'Teacher not found' });
      res.status(200).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_NO_REFERENCED_ROW_2')
        return res.status(400).json({ error: 'class_id must reference an existing class' });
      res.status(500).json({ error: 'Failed to update teacher' });
    }
  },

  async remove(req: Request, res: Response) {
    try {
      const ok = await TeacherService.remove(req.params.id);
      if (!ok) return res.status(404).json({ error: 'Teacher not found' });
      res.status(200).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_ROW_IS_REFERENCED_2')
        return res.status(400).json({ error: 'Cannot delete: referenced by subjects' });
      res.status(500).json({ error: 'Failed to delete teacher' });
    }
  },
};
