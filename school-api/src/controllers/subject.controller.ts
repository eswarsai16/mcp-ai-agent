import { Request, Response } from 'express';
import { SubjectService } from '../services/SubjectService.js';

export const SubjectController = {
  async list(_: Request, res: Response) {
    try { res.status(200).json(await SubjectService.getAll()); }
    catch { res.status(500).json({ error: 'Failed to list subjects' }); }
  },

  async get(req: Request, res: Response) {
    try {
      const row = await SubjectService.getById(req.params.id);
      if (!row) return res.status(404).json({ error: 'Subject not found' });
      res.status(200).json(row);
    } catch { res.status(500).json({ error: 'Failed to get subject' }); }
  },

  async create(req: Request, res: Response) {
    const { subject_id, subject_name, teacher_id } = req.body;
    if (!subject_id || !subject_name)
      return res.status(400).json({ error: 'subject_id and subject_name are required' });
    try {
      await SubjectService.create({ subject_id, subject_name, teacher_id });
      res.status(201).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_NO_REFERENCED_ROW_2')
        return res.status(400).json({ error: 'teacher_id must reference an existing teacher' });
      res.status(500).json({ error: 'Failed to create subject' });
    }
  },

  async update(req: Request, res: Response) {
    const { subject_name, teacher_id } = req.body;
    if (subject_name === undefined && teacher_id === undefined)
      return res.status(400).json({ error: 'Provide subject_name or teacher_id' });
    try {
      const ok = await SubjectService.update(req.params.id, { subject_name, teacher_id });
      if (!ok) return res.status(404).json({ error: 'Subject not found' });
      res.status(200).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_NO_REFERENCED_ROW_2')
        return res.status(400).json({ error: 'teacher_id must reference an existing teacher' });
      res.status(500).json({ error: 'Failed to update subject' });
    }
  },

  async remove(req: Request, res: Response) {
    try {
      const ok = await SubjectService.remove(req.params.id);
      if (!ok) return res.status(404).json({ error: 'Subject not found' });
      res.status(200).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_ROW_IS_REFERENCED_2')
        return res.status(400).json({ error: 'Cannot delete: referenced by marks' });
      res.status(500).json({ error: 'Failed to delete subject' });
    }
  },

  async studentsBySubject(req: Request, res: Response) {
    try { res.status(200).json(await SubjectService.getStudentsBySubject(req.params.id)); }
    catch { res.status(500).json({ error: 'Failed to fetch students for subject' }); }
  },
};
