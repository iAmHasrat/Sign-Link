function trimTrailingSlash(value) {
  return value?.replace(/\/+$/, '');
}

export const API_URL = trimTrailingSlash(import.meta.env.VITE_API_URL || '/api');
export const SOCKET_URL = trimTrailingSlash(import.meta.env.VITE_SOCKET_URL || window.location.origin);
export const LANDMARK_API_URL = trimTrailingSlash(import.meta.env.VITE_LANDMARK_API_URL || '');
