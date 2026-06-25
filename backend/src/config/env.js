import dotenv from 'dotenv';

dotenv.config();

const required = ['JWT_SECRET', 'DB_HOST', 'DB_USER', 'DB_NAME'];

for (const key of required) {
  if (!process.env[key]) {
    console.warn(`[config] Missing environment variable: ${key}`);
  }
}

const defaultFrontendUrls = [
  'http://localhost:5173',
  'https://localhost:5173',
  'http://172.16.166.159:5173',
  'https://172.16.166.159:5173'
];
const frontendUrls = (process.env.FRONTEND_URLS || process.env.FRONTEND_URL || defaultFrontendUrls.join(','))
  .split(',')
  .map((url) => url.trim())
  .filter(Boolean);

export const env = {
  nodeEnv: process.env.NODE_ENV || 'development',
  port: Number(process.env.PORT || 5000),
  host: process.env.HOST || '0.0.0.0',
  frontendUrls,
  jwtSecret: process.env.JWT_SECRET || 'dev-only-secret',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '7d',
  db: {
    host: process.env.DB_HOST || 'localhost',
    port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 'sign_link',
    connectionLimit: Number(process.env.DB_CONNECTION_LIMIT || 10)
  }
};
