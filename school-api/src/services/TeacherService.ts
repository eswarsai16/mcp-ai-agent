import { pool } from '../config/db.js';

export const TeacherService = {
  async getAll() {
    const [rows] = await pool.query(
      `SELECT t.teacher_id, t.name, t.class_id, c.class_name
       FROM teachers t
       LEFT JOIN class c ON c.class_id = t.class_id
       ORDER BY t.teacher_id`
    );
    return rows as any[];
  },
  async getById(id: string) {
    const [rows] = await pool.query(
      `SELECT t.teacher_id, t.name, t.class_id, c.class_name
       FROM teachers t
       LEFT JOIN class c ON c.class_id = t.class_id
       WHERE t.teacher_id = ?`, [id]
    );
    return (rows as any[])[0];
  },
  async create(dto: { teacher_id: string; name: string; class_id?: string }) {
    await pool.query('INSERT INTO teachers (teacher_id, name, class_id) VALUES (?, ?, ?)',
      [dto.teacher_id, dto.name, dto.class_id ?? null]);
  },
  async update(id: string, dto: { name?: string; class_id?: string }) {
    const fields: string[] = [], values: any[] = [];
    if (dto.name !== undefined) { fields.push('name = ?'); values.push(dto.name); }
    if (dto.class_id !== undefined) { fields.push('class_id = ?'); values.push(dto.class_id || null); }
    if (!fields.length) return false;
    values.push(id);
    const [res]: any = await pool.query(`UPDATE teachers SET ${fields.join(', ')} WHERE teacher_id = ?`, values);
    return res.affectedRows > 0;
  },
  async remove(id: string) {
    const [res]: any = await pool.query('DELETE FROM teachers WHERE teacher_id = ?', [id]);
    return res.affectedRows > 0;
  },
};
