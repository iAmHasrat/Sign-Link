import bcrypt from 'bcrypt';
import { asyncHandler } from '../utils/asyncHandler.js';
import { signToken } from '../utils/jwt.js';
import { createUser, findUserByEmail, findUserById, findUserByUsername } from '../models/userModel.js';

function authResponse(user) {
  return { token: signToken(user), user };
}

export const register = asyncHandler(async (req, res) => {
  const { fullName, username, email, password, role, preferredLanguage } = req.body;

  const existingEmail = await findUserByEmail(email);
  if (existingEmail) {
    return res.status(409).json({ message: 'Email is already registered' });
  }
  const existingUsername = await findUserByUsername(username);
  if (existingUsername) {
    return res.status(409).json({ message: 'Username is already taken' });
  }

  const passwordHash = await bcrypt.hash(password, 12);
  const user = await createUser({ fullName, username, email, passwordHash, role, preferredLanguage });
  return res.status(201).json(authResponse(user));
});

export const login = asyncHandler(async (req, res) => {
  const { email, password } = req.body;

  // findUserByEmail returns the full record including password_hash
  const { getUsers } = await import('../config/db.js');
  const userWithHash = getUsers().find(u => u.email.toLowerCase() === email?.toLowerCase());

  if (!userWithHash) {
    return res.status(401).json({ message: 'Invalid email or password' });
  }

  const match = await bcrypt.compare(password, userWithHash.password_hash);
  if (!match) {
    return res.status(401).json({ message: 'Invalid email or password' });
  }

  const user = await findUserById(userWithHash.user_id);
  return res.json(authResponse(user));
});

export const me = asyncHandler(async (req, res) => {
  const user = await findUserById(req.user.userId);
  return res.json({ user });
});
