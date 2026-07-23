import os from 'os';
import { env } from '../config/env.js';

const allowedHosts = new Set(['localhost', '127.0.0.1']);
const allowedOrigins = new Set(env.frontendUrls || []);

try {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === 'IPv4') {
        allowedHosts.add(iface.address);
      }
    }
  }
} catch (e) {
  console.error('[CORS] Failed to load network interfaces:', e);
}

export function isLocalOrigin(origin) {
  if (!origin) return true;
  if (allowedOrigins.has(origin)) return true;
  try {
    const url = new URL(origin);
    const hostname = url.hostname;
    if (hostname.endsWith('.loca.lt') || hostname.endsWith('.ngrok-free.app') || hostname.endsWith('.ngrok.io')) return true;
    return allowedHosts.has(hostname);
  } catch {
    return true; // fallback allow in dev
  }
}

