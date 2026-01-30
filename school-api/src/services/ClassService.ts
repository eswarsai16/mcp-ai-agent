import { pool } from '../config/db.js';

export const ClassService = {
  async getAll() {
    const [rows] = await pool.query(
      'SELECT class_id, class_name FROM class ORDER BY class_id'
    );
    return rows as any[];
  },

  async getById(id: string) {
    const [rows] = await pool.query(
      'SELECT class_id, class_name FROM class WHERE class_id = ?',
      [id]
    );
    return (rows as any[])[0];
  },

  async create(dto: { class_id: string; class_name: string }) {
    await pool.query(
      'INSERT INTO class (class_id, class_name) VALUES (?, ?)',
      [dto.class_id, dto.class_name]
    );
  },

  async update(id: string, dto: { class_name?: string }) {
    const fields: string[] = [];
    const values: any[] = [];

    if (dto.class_name !== undefined) {
      fields.push('class_name = ?');
      values.push(dto.class_name);
    }

    if (!fields.length) return false;

    values.push(id);
    const [res]: any = await pool.query(
      `UPDATE class SET ${fields.join(', ')} WHERE class_id = ?`,
      values
    );
    return res.affectedRows > 0;
  },

  async remove(id: string) {
    const [res]: any = await pool.query(
      'DELETE FROM class WHERE class_id = ?',
      [id]
    );
    return res.affectedRows > 0;
  },
};
