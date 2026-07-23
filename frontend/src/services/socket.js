import { io } from 'socket.io-client';
import { SOCKET_URL } from '../config/network.js';

let socket;
let currentToken;

export function getSocket(token) {
  if (socket && currentToken !== token) {
    console.log('[Socket] Token changed, disconnecting old socket connection...');
    socket.disconnect();
    socket = null;
  }

  currentToken = token;

  if (!socket) {
    console.log('[Socket] Initializing new Socket.IO connection with URL:', SOCKET_URL);
    socket = io(SOCKET_URL, {
      autoConnect: false,
      auth: { token }
    });
  }

  socket.auth = { token };
  if (!socket.connected) {
    console.log('[Socket] Connecting socket...');
    socket.connect();
  }
  return socket;
}

export function disconnectSocket() {
  if (socket) {
    console.log('[Socket] Disconnecting socket...');
    socket.disconnect();
  }
  socket = null;
  currentToken = null;
}
