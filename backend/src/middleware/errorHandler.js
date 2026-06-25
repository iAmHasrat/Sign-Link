import { env } from '../config/env.js';

export function notFound(req, res) {
  res.status(404).json({ message: `Route not found: ${req.method} ${req.originalUrl}` });
}

export function errorHandler(error, req, res, next) {
  const status = error.status || 500;

  if (env.nodeEnv !== 'test') {
    console.error(error);
  }

  res.status(status).json({
    message: status === 500 ? 'Internal server error' : error.message,
    ...(env.nodeEnv === 'development' ? { stack: error.stack } : {})
  });
}
