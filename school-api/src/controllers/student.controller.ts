import { Request, Response } from 'express';
import { StudentService } from '../services/StudentService.js';

export class StudentController {
  static async list(req: Request, res: Response) {
    try {
      const includeClass = req.query.includeClass === 'true';
      const data = await StudentService.getAllStudents(includeClass);
      res.status(200).json({ data });
    } catch (err: any) {
      res.status(500).json({ error: err.message || 'Internal server error' });
    }
  }

  static async get(req: Request, res: Response) {
    try {
      const { id } = req.params;
      const includeClass = req.query.includeClass === 'true';
      const student = await StudentService.getStudentById(id, includeClass);
      if (!student) return res.status(404).json({ error: 'Not found' });
      res.status(200).json({ data: student });
    } catch (err: any) {
      res.status(500).json({ error: err.message || 'Internal server error' });
    }
  }

  static async create(req: Request, res: Response) {
    try {
      const { student_id, name, class_id } = req.body;
      if (!student_id || !name || !class_id) {
        return res.status(400).json({ error: 'student_id, name, class_id are required' });
      }
      const created = await StudentService.createStudent({ student_id, name, class_id });
      res.status(201).json({ data: created });
    } catch (err: any) {
      // Foreign key violation or duplicate PK will surface here
      res.status(500).json({ error: err.message || 'Internal server error' });
    }
  }

  static async update(req: Request, res: Response) {
    try {
      const { id } = req.params;
      const { name, class_id } = req.body;
      const updated = await StudentService.updateStudent(id, { name, class_id });
      if (!updated) return res.status(404).json({ error: 'Not found' });
      res.status(200).json({ data: updated });
    } catch (err: any) {
      res.status(500).json({ error: err.message || 'Internal server error' });
    }
  }

  static async remove(req: Request, res: Response) {
    try {
      const { id } = req.params;
      const removed = await StudentService.deleteStudent(id);
      if (!removed) return res.status(404).json({ error: 'Not found' });
      res.status(200).json({ data: removed });
    } catch (err: any) {
      res.status(500).json({ error: err.message || 'Internal server error' });
    }
  }
}

