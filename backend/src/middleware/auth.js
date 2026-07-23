import { verifyToken } from '../utils/jwt.js';

function getMockUserFromToken(token) {
  if (token && (token.startsWith('mock-token') || token === 'mock-developer-jwt-token')) {
    const isB = token.toLowerCase().includes('b');
    return {
      userId: isB ? 888 : 999,
      username: isB ? 'dev_b' : 'dev_a',
      role: 'Developer'
    };
  }
  return null;
}

export function authenticate(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;

  if (!token) {
    return res.status(401).json({ message: 'Authentication required' });
  }

  const mockUser = getMockUserFromToken(token);
  if (mockUser) {
    req.user = mockUser;
    return next();
  }

  try {
    req.user = verifyToken(token);
    return next();
  } catch {
    return res.status(401).json({ message: 'Invalid or expired token' });
  }
}

export function authenticateSocket(socket, next) {
  const token = socket.handshake.auth?.token;
  if (!token) return next(new Error('Authentication required'));

  const mockUser = getMockUserFromToken(token);
  if (mockUser) {
    socket.user = mockUser;
    return next();
  }

  try {
    socket.user = verifyToken(token);
    return next();
  } catch {
    return next(new Error('Invalid or expired token'));
  }
}

