import { Router } from 'express';
import { TeacherController } from '../controllers/teacher.controller.js';

const router = Router();

router.get('/', TeacherController.list);
router.post('/', TeacherController.create);
router.get('/:id', TeacherController.get);
router.put('/:id', TeacherController.update);
router.delete('/:id', TeacherController.remove);

export default router;
