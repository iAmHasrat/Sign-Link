import bcrypt from 'bcrypt';
import { asyncHandler } from '../utils/asyncHandler.js';
import { signToken } from '../utils/jwt.js';
import { createUser, findUserByEmail, findUserById, findUserByUsername } from '../models/userModel.js';

function authResponse(user) {
  return { token: signToken(user), user };
}

export const register = asyncHandler(async (req, res) => {
  const { fullName, username, email, password, role, preferredLanguage } = req.body;

  if (await findUserByEmail(email)) {
    return res.status(409).json({ message: 'Email is already registered' });
  }
  if (await findUserByUsername(username)) {
    return res.status(409).json({ message: 'Username is already taken' });
  }

  const passwordHash = await bcrypt.hash(password, 12);
  const user = await createUser({ fullName, username, email, passwordHash, role, preferredLanguage });
  return res.status(201).json(authResponse(user));
});

export const login = asyncHandler(async (req, res) => {
  const { email, password } = req.body;
  const userWithPassword = await findUserByEmail(email);

  if (!userWithPassword || !(await bcrypt.compare(password, userWithPassword.password_hash))) {
    return res.status(401).json({ message: 'Invalid email or password' });
  }

  const user = await findUserById(userWithPassword.user_id);
  return res.json(authResponse(user));
});

export const me = asyncHandler(async (req, res) => {
  const user = await findUserById(req.user.userId);
  return res.json({ user });
});
