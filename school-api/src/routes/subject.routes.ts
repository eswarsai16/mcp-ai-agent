import { Router } from 'express';
import { SubjectController } from '../controllers/subject.controller.js';

const router = Router();

router.get('/', SubjectController.list);
router.post('/', SubjectController.create);
router.get('/:id', SubjectController.get);
router.put('/:id', SubjectController.update);
router.delete('/:id', SubjectController.remove);

router.get('/:id/students', SubjectController.studentsBySubject);

export default router;
