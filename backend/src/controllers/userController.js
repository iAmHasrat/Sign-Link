import { asyncHandler } from '../utils/asyncHandler.js';
import { findUserById, searchUsers, updateUser } from '../models/userModel.js';

export const getProfile = asyncHandler(async (req, res) => {
  const user = await findUserById(req.user.userId);
  res.json({ user });
});

export const updateProfile = asyncHandler(async (req, res) => {
  const user = await updateUser(req.user.userId, req.body);
  res.json({ user });
});

export const findUsers = asyncHandler(async (req, res) => {
  const users = await searchUsers(req.query.q || '', req.user.userId);
  res.json({ users });
});
