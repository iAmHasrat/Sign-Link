import http from 'http';
import { Server } from 'socket.io';
import { createApp } from './app.js';
import { env } from './config/env.js';
import { pingDatabase } from './config/db.js';
import { registerSockets } from './sockets/index.js';

const app = createApp();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: env.frontendUrls,
    credentials: true
  }
});

app.set('io', io);
registerSockets(io);

server.listen(env.port, env.host, async () => {
  try {
    await pingDatabase();
    console.log(`Sign Link API running on ${env.host}:${env.port}`);
  } catch (error) {
    console.error('API started, but database connection failed:', error.message);
  }
});
