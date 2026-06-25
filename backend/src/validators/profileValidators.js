import { body } from 'express-validator';

export const profileRules = [
  body('fullName').optional().trim().isLength({ min: 2 }).withMessage('Full name is too short'),
  body('role').optional().isIn(['Deaf', 'Hearing']).withMessage('Role must be Deaf or Hearing'),
  body('preferredLanguage').optional().isIn(['en', 'hi', 'pa']).withMessage('Unsupported language'),
  body('profilePicture').optional({ nullable: true }).isURL().withMessage('Profile picture must be a URL')
];
