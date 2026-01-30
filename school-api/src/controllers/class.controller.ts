import { Request, Response } from 'express';
import { ClassService } from '../services/ClassService.js';

export const ClassController = {
  async list(_: Request, res: Response) {
    try {
      const rows = await ClassService.getAll();
      res.status(200).json(rows);
    } catch {
      res.status(500).json({ error: 'Failed to list classes' });
    }
  },

  async get(req: Request, res: Response) {
    try {
      const row = await ClassService.getById(req.params.id);
      if (!row) return res.status(404).json({ error: 'Class not found' });
      res.status(200).json(row);
    } catch {
      res.status(500).json({ error: 'Failed to get class' });
    }
  },

  async create(req: Request, res: Response) {
    const { class_id, class_name } = req.body;
    if (!class_id || !class_name) {
      return res
        .status(400)
        .json({ error: 'class_id and class_name are required' });
    }

    try {
      await ClassService.create({ class_id, class_name });
      res.status(201).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_DUP_ENTRY') {
        return res.status(400).json({ error: 'class_id already exists' });
      }
      res.status(500).json({ error: 'Failed to create class' });
    }
  },

  async update(req: Request, res: Response) {
    // Only class_name is supported now
    const { class_name } = req.body;

    if (class_name === undefined) {
      return res
        .status(400)
        .json({ error: 'Provide class_name to update' });
    }

    try {
      const ok = await ClassService.update(req.params.id, { class_name });
      if (!ok) return res.status(404).json({ error: 'Class not found' });
      res.status(200).json({ ok: true });
    } catch {
      res.status(500).json({ error: 'Failed to update class' });
    }
  },

  async remove(req: Request, res: Response) {
    try {
      const ok = await ClassService.remove(req.params.id);
      if (!ok) return res.status(404).json({ error: 'Class not found' });
      res.status(200).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_ROW_IS_REFERENCED_2') {
        return res
          .status(400)
          .json({ error: 'Cannot delete: referenced by students/teachers' });
      }
      res.status(500).json({ error: 'Failed to delete class' });
    }
  },
};
