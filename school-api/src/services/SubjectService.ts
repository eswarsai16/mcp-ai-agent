import { pool } from '../config/db.js';

export const SubjectService = {
  async getAll() {
    const [rows] = await pool.query(
      `SELECT s.subject_id, s.subject_name, s.teacher_id, t.name AS teacher_name
       FROM subject s
       LEFT JOIN teachers t ON t.teacher_id = s.teacher_id
       ORDER BY s.subject_id`
    );
    return rows as any[];
  },
  async getById(id: string) {
    const [rows] = await pool.query(
      `SELECT s.subject_id, s.subject_name, s.teacher_id, t.name AS teacher_name
       FROM subject s
       LEFT JOIN teachers t ON t.teacher_id = s.teacher_id
       WHERE s.subject_id = ?`, [id]
    );
    return (rows as any[])[0];
  },
  async create(dto: { subject_id: string; subject_name: string; teacher_id?: string }) {
    await pool.query('INSERT INTO subject (subject_id, subject_name, teacher_id) VALUES (?, ?, ?)',
      [dto.subject_id, dto.subject_name, dto.teacher_id ?? null]);
  },
  async update(id: string, dto: { subject_name?: string; teacher_id?: string }) {
    const fields: string[] = [], values: any[] = [];
    if (dto.subject_name !== undefined) { fields.push('subject_name = ?'); values.push(dto.subject_name); }
    if (dto.teacher_id !== undefined) { fields.push('teacher_id = ?'); values.push(dto.teacher_id || null); }
    if (!fields.length) return false;
    values.push(id);
    const [res]: any = await pool.query(`UPDATE subject SET ${fields.join(', ')} WHERE subject_id = ?`, values);
    return res.affectedRows > 0;
  },
  async remove(id: string) {
    const [res]: any = await pool.query('DELETE FROM subject WHERE subject_id = ?', [id]);
    return res.affectedRows > 0;
  },
  async getStudentsBySubject(subject_id: string) {
    const [rows] = await pool.query(
      `SELECT DISTINCT st.student_id, st.name, st.class_id, c.class_name
       FROM marks m
       JOIN students st ON st.student_id = m.student_id
       LEFT JOIN class c ON c.class_id = st.class_id
       WHERE m.subject_id = ?
       ORDER BY st.student_id`, [subject_id]
    );
    return rows as any[];
  },
};
