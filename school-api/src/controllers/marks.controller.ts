import { Request, Response, NextFunction } from 'express';
import { MarksService } from '../services/MarksService.js';

export const MarksController = {
  async getByStudentAndSubject(req: Request, res: Response, next: NextFunction) {
    const { student_id, subject_id } = req.query as { student_id?: string; subject_id?: string };

    if (student_id !== undefined && subject_id !== undefined) {
      if (!student_id || !subject_id) {
        return res.status(400).json({ error: 'student_id and subject_id must be non-empty' });
      }
      try {
        const mark = await MarksService.getMarksForStudentSubject(student_id, subject_id);
        if (mark === null) {
          return res.status(404).json({ error: 'No marks found for given student_id and subject_id' });
        }
        return res.status(200).json({ student_id, subject_id, marks: mark });
      } catch {
        return res.status(500).json({ error: 'Failed to fetch marks for student & subject' });
      }
    }

    return next();
  },

  async list(_: Request, res: Response) {
    try { res.status(200).json(await MarksService.getAll()); }
    catch { res.status(500).json({ error: 'Failed to list marks' }); }
  },

  async get(req: Request, res: Response) {
    try {
      const row = await MarksService.getById(req.params.id);
      if (!row) return res.status(404).json({ error: 'Marks not found' });
      res.status(200).json(row);
    } catch { res.status(500).json({ error: 'Failed to get marks' }); }
  },

  async create(req: Request, res: Response) {
    const { marks_id, student_id, subject_id, marks } = req.body;
    if (!marks_id || !student_id || !subject_id || marks === undefined)
      return res.status(400).json({ error: 'marks_id, student_id, subject_id, marks are required' });
    const m = Number(marks);
    if (Number.isNaN(m) || m < 0 || m > 100)
      return res.status(400).json({ error: 'marks must be an integer between 0 and 100' });
    try {
      await MarksService.create({ marks_id, student_id, subject_id, marks: m });
      res.status(201).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_NO_REFERENCED_ROW_2')
        return res.status(400).json({ error: 'student_id or subject_id invalid (FK)' });
      res.status(500).json({ error: 'Failed to create marks' });
    }
  },

  async update(req: Request, res: Response) {
    const { student_id, subject_id, marks } = req.body;
    if (student_id === undefined && subject_id === undefined && marks === undefined)
      return res.status(400).json({ error: 'Provide at least one of student_id, subject_id, marks' });
    if (marks !== undefined) {
      const m = Number(marks);
      if (Number.isNaN(m) || m < 0 || m > 100)
        return res.status(400).json({ error: 'marks must be between 0 and 100' });
    }
    try {
      const ok = await MarksService.update(req.params.id, { student_id, subject_id, marks });
      if (!ok) return res.status(404).json({ error: 'Marks not found' });
      res.status(200).json({ ok: true });
    } catch (e: any) {
      if (e?.code === 'ER_NO_REFERENCED_ROW_2')
        return res.status(400).json({ error: 'student_id or subject_id invalid (FK)' });
      res.status(500).json({ error: 'Failed to update marks' });
    }
  },

  async remove(req: Request, res: Response) {
    try {
      const ok = await MarksService.remove(req.params.id);
      if (!ok) return res.status(404).json({ error: 'Marks not found' });
      res.status(200).json({ ok: true });
    } catch { res.status(500).json({ error: 'Failed to delete marks' }); }
  },

  async marksByStudent(req: Request, res: Response) {
    try { res.status(200).json(await MarksService.getMarksByStudent(req.params.studentId)); }
    catch { res.status(500).json({ error: 'Failed to fetch marks by student' }); }
  },

  async marksBySubject(req: Request, res: Response) {
    try { res.status(200).json(await MarksService.getMarksBySubject(req.params.subjectId)); }
    catch { res.status(500).json({ error: 'Failed to fetch marks by subject' }); }
  },

  async subjectAverage(req: Request, res: Response) {
    try { res.status(200).json({ subject_id: req.params.subjectId, average: await MarksService.getSubjectAverage(req.params.subjectId) }); }
    catch { res.status(500).json({ error: 'Failed to compute subject average' }); }
  },
};
