import { Router } from 'express';
import { StudentController } from '../controllers/student.controller.js';

const router = Router();

router.get('/', StudentController.list);
router.post('/', StudentController.create);
router.get('/:id', StudentController.get);
router.put('/:id', StudentController.update);
router.delete('/:id', StudentController.remove);


export default router;

