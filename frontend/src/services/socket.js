import { io } from 'socket.io-client';
import { SOCKET_URL } from '../config/network.js';

let socket;

export function getSocket(token) {
  if (!socket) {
    socket = io(SOCKET_URL, {
      autoConnect: false,
      auth: { token }
    });
  }
  socket.auth = { token };
  if (!socket.connected) socket.connect();
  return socket;
}

export function disconnectSocket() {
  if (socket) socket.disconnect();
  socket = null;
}
