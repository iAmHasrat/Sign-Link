import { body } from 'express-validator';

export const registerRules = [
  body('fullName').trim().isLength({ min: 2 }).withMessage('Full name is required'),
  body('username')
    .trim()
    .isLength({ min: 3, max: 30 })
    .matches(/^[a-zA-Z0-9_]+$/)
    .withMessage('Username must be 3-30 letters, numbers, or underscores'),
  body('email').isEmail().normalizeEmail().withMessage('A valid email is required'),
  body('password').isLength({ min: 8 }).withMessage('Password must be at least 8 characters'),
  body('confirmPassword').custom((value, { req }) => value === req.body.password).withMessage('Passwords must match'),
  body('role').isIn(['Deaf', 'Hearing']).withMessage('Role must be Deaf or Hearing'),
  body('preferredLanguage').isIn(['en', 'hi', 'pa']).withMessage('Unsupported language')
];

export const loginRules = [
  body('email').isEmail().normalizeEmail().withMessage('A valid email is required'),
  body('password').notEmpty().withMessage('Password is required')
];
