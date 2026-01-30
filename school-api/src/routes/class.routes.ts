import { Router } from 'express';
import { ClassController } from '../controllers/class.controller.js';

const router = Router();

router.get('/', ClassController.list);
router.post('/', ClassController.create);
router.get('/:id', ClassController.get);
router.put('/:id', ClassController.update);
router.delete('/:id', ClassController.remove);

export default router;
