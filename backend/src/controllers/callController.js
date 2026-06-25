import { asyncHandler } from '../utils/asyncHandler.js';
import { listCallHistory } from '../models/callModel.js';

export const getCallHistory = asyncHandler(async (req, res) => {
  const calls = await listCallHistory(req.user.userId);
  res.json({ calls });
});
