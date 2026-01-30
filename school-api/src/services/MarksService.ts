import { pool } from '../config/db.js';

export const MarksService = {
  async getAll() {
    const [rows] = await pool.query(
      `SELECT m.marks_id, m.student_id, st.name AS student_name,
              m.subject_id, sb.subject_name, m.marks
       FROM marks m
       JOIN students st ON st.student_id = m.student_id
       JOIN subject sb ON sb.subject_id = m.subject_id
       ORDER BY m.marks_id`
    );
    return rows as any[];
  },
  
  async getById(id: string) {
    const [rows] = await pool.query(
      `SELECT m.marks_id, m.student_id, st.name AS student_name,
              m.subject_id, sb.subject_name, m.marks
       FROM marks m
       JOIN students st ON st.student_id = m.student_id
       JOIN subject sb ON sb.subject_id = m.subject_id
       WHERE m.marks_id = ?`, [id]
    );
    return (rows as any[])[0];
  },
  async create(dto: { marks_id: string; student_id: string; subject_id: string; marks: number }) {
    await pool.query('INSERT INTO marks (marks_id, student_id, subject_id, marks) VALUES (?, ?, ?, ?)',
      [dto.marks_id, dto.student_id, dto.subject_id, dto.marks]);
  },
  async update(id: string, dto: { student_id?: string; subject_id?: string; marks?: number }) {
    const fields: string[] = [], values: any[] = [];
    if (dto.student_id !== undefined) { fields.push('student_id = ?'); values.push(dto.student_id); }
    if (dto.subject_id !== undefined) { fields.push('subject_id = ?'); values.push(dto.subject_id); }
    if (dto.marks !== undefined) { fields.push('marks = ?'); values.push(dto.marks); }
    if (!fields.length) return false;
    values.push(id);
    const [res]: any = await pool.query(`UPDATE marks SET ${fields.join(', ')} WHERE marks_id = ?`, values);
    return res.affectedRows > 0;
  },
  async remove(id: string) {
    const [res]: any = await pool.query('DELETE FROM marks WHERE marks_id = ?', [id]);
    return res.affectedRows > 0;
  },
  async getMarksByStudent(student_id: string) {
    const [rows] = await pool.query(
      `SELECT m.marks_id, m.subject_id, sb.subject_name, m.marks
       FROM marks m
       JOIN subject sb ON sb.subject_id = m.subject_id
       WHERE m.student_id = ?
       ORDER BY sb.subject_name`, [student_id]
    );
    return rows as any[];
  },
  async getMarksBySubject(subject_id: string) {
    const [rows] = await pool.query(
      `SELECT m.marks_id, m.student_id, st.name AS student_name, m.marks
       FROM marks m
       JOIN students st ON st.student_id = m.student_id
       WHERE m.subject_id = ?
       ORDER BY st.name`, [subject_id]
    );
    return rows as any[];
  },
  async getSubjectAverage(subject_id: string) {
    const [rows] = await pool.query(`SELECT AVG(marks) AS avg_marks FROM marks WHERE subject_id = ?`, [subject_id]);
    const r = (rows as any[])[0];
    return r?.avg_marks ?? null;
  },
  
  async getMarksForStudentSubject(student_id: string, subject_id: string) {
      const [rows] = await pool.query(
        `SELECT m.marks
        FROM marks m
        WHERE m.student_id = ? AND m.subject_id = ?
        LIMIT 1`,
        [student_id, subject_id]
      );
      const r = (rows as any[])[0];
      return r?.marks ?? null;
    },

};

