# School API

A backend application for managing school data, built with **Node.js**, **Express**, **TypeScript**, and **MySQL**. It provides RESTful APIs for students, classes, teachers, subjects, and marks, supporting full CRUD operations and designed for modular scalability.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Folder Structure](#folder-structure)
- [Database Structure](#database-structure)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)
- [How to Run](#how-to-run)
- [Next Steps](#next-steps)
- [Notes](#notes)

---

## Project Overview
The **School API** manages a school database (`School_DB`) with modules for students, classes, teachers, subjects, and marks. It is built for extensibility and clean separation of concerns, using controllers and services for business logic and database operations.

---

## Folder Structure
```
school-api/
├── package.json         # Project dependencies and scripts
├── tsconfig.json        # TypeScript configuration
├── .env                 # Environment variables
├── src/
│   ├── server.ts        # Server entry point
│   ├── app.ts           # Express app setup
│   ├── config/db.ts     # MySQL connection pool
│   ├── routes/          # API route definitions
│   ├── controllers/     # Request handlers
│   ├── services/        # Business logic
├── dist/                # Compiled JS output
```

---

## Database Structure
- **class**: `class_id` (PK), `class_name`, `num_students`
- **teachers**: `teacher_id` (PK), `name`, `class_id` (FK)
- **students**: `student_id` (PK), `name`, `class_id` (FK)
- **subject**: `subject_id` (PK), `subject_name`, `teacher_id` (FK)
- **marks**: `marks_id` (PK), `student_id` (FK), `subject_id` (FK), `marks`

---

## API Endpoints
### Student Endpoints
- `GET /api/students` – List all students
- `GET /api/students/:id` – Get student by ID
- `POST /api/students` – Create student
- `PUT /api/students/:id` – Update student
- `DELETE /api/students/:id` – Delete student

### Class Endpoints
- `GET /api/classes` – List all classes
- `GET /api/classes/:id` – Get class by ID
- `POST /api/classes` – Create class
- `PUT /api/classes/:id` – Update class
- `DELETE /api/classes/:id` – Delete class

### Teacher Endpoints
- `GET /api/teachers` – List all teachers
- `GET /api/teachers/:id` – Get teacher by ID
- `POST /api/teachers` – Create teacher
- `PUT /api/teachers/:id` – Update teacher
- `DELETE /api/teachers/:id` – Delete teacher

### Subject Endpoints
- `GET /api/subjects` – List all subjects
- `GET /api/subjects/:id` – Get subject by ID
- `POST /api/subjects` – Create subject
- `PUT /api/subjects/:id` – Update subject
- `DELETE /api/subjects/:id` – Delete subject
- `GET /api/subjects/:id/students` – List students in a subject

### Marks Endpoints
- `GET /api/marks` – List all marks
- `GET /api/marks/:id` – Get marks by ID
- `POST /api/marks` – Add marks
- `PUT /api/marks/:id` – Update marks
- `DELETE /api/marks/:id` – Delete marks
- `GET /api/marks?student_id=...&subject_id=...` – Get marks for a student in a subject
- `GET /api/marks/by-student/:studentId` – All marks for a student
- `GET /api/marks/by-subject/:subjectId` – All marks for a subject
- `GET /api/marks/by-subject/:subjectId/average` – Average marks for a subject

### Health Check
- `GET /health` – Verify server status

---

## Environment Variables
```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=Eswar@1224
DB_DATABASE=School_DB
DB_PORT=3306
PORT=3000
```

---

## How to Run
1. Install dependencies:
```bash
npm install
```
2. Start the server in development mode:
```bash
npm run dev
```
3. Access the API:
- Health check: `GET http://localhost:3000/health`
- Example: `GET http://localhost:3000/api/students`

---

## Next Steps
- Add validation middleware (e.g., `express-validator`)
- Write unit tests for services and controllers
- Document the API using Swagger or Postman
- Implement pagination, filtering, and sorting

---

## Notes
- The endpoint `GET /api/marks?student_id=...&subject_id=...` allows direct fetching of a student's marks for a specific subject using query parameters.
- Swagger UI is available at `/api-docs` for interactive API documentation.
- The project is modular and ready for further extension.
