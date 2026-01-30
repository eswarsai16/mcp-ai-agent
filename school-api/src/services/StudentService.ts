import { pool } from '../config/db.js';

export type StudentCreate = {
  student_id: string;
  name: string;      
  class_id: string;     
};

export type StudentUpdate = {
  name?: string;
  class_id?: string;
};

export class StudentService {
  static async getAllStudents(includeClass = false) {
    const sql = includeClass
      ? `SELECT s.student_id, s.name, s.class_id,
                c.class_name, c.num_students
         FROM students s
         LEFT JOIN class c ON c.class_id = s.class_id
         ORDER BY s.student_id`
      : `SELECT student_id, name, class_id FROM students ORDER BY student_id`;

    const [rows] = await pool.query(sql);
    return rows;
  }

  // Get one student by ID
  static async getStudentById(student_id: string, includeClass = false) {
    const sql = includeClass
      ? `SELECT s.student_id, s.name, s.class_id,
                c.class_name, c.num_students
         FROM students s
         LEFT JOIN class c ON c.class_id = s.class_id
         WHERE s.student_id = ?`
      : `SELECT student_id, name, class_id FROM students WHERE student_id = ?`;

    const [rows] = await pool.query(sql, [student_id]);
    if (Array.isArray(rows) && rows.length) return rows[0];
    return null;
  }

  // Create a student (FK is enforced by MySQL)
  static async createStudent(data: StudentCreate) {
    const insertSql =
      `INSERT INTO students (student_id, name, class_id) VALUES (?, ?, ?)`;
    await pool.query(insertSql, [data.student_id, data.name, data.class_id]);
    return this.getStudentById(data.student_id);
  }

  // Update a student (name and/or class_id)
  static async updateStudent(student_id: string, data: StudentUpdate) {
    const fields: string[] = [];
    const values: any[] = [];

    if (typeof data.name === 'string') {
      fields.push('name = ?');
      values.push(data.name);
    }
    if (typeof data.class_id === 'string') {
      fields.push('class_id = ?');
      values.push(data.class_id);
    }

    if (!fields.length) return this.getStudentById(student_id);

    const sql = `UPDATE students SET ${fields.join(', ')} WHERE student_id = ?`;
    values.push(student_id);
    await pool.query(sql, values);
    return this.getStudentById(student_id);
  }

  // Delete a student
  static async deleteStudent(student_id: string) {
    const existing = await this.getStudentById(student_id);
    if (!existing) return null;
    await pool.query(`DELETE FROM students WHERE student_id = ?`, [student_id]);
    return existing;
  }
}

