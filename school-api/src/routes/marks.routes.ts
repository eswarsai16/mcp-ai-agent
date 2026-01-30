import { Router } from 'express';
import { MarksController } from '../controllers/marks.controller.js';

const router = Router();

router.get('/', MarksController.getByStudentAndSubject);
router.get('/', MarksController.list); 

router.post('/', MarksController.create);
router.get('/:id', MarksController.get);
router.put('/:id', MarksController.update);
router.delete('/:id', MarksController.remove);

router.get('/by-student/:studentId', MarksController.marksByStudent);
router.get('/by-subject/:subjectId', MarksController.marksBySubject);
router.get('/by-subject/:subjectId/average', MarksController.subjectAverage);

export default router;
