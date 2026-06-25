import axios from 'axios';
import { API_URL } from '../config/network.js';
import { storage } from '../utils/storage.js';

export const api = axios.create({
  baseURL: API_URL
});

api.interceptors.request.use((config) => {
  const token = storage.get('sign-link-token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      storage.remove('sign-link-token');
      storage.remove('sign-link-user');
    }
    return Promise.reject(error);
  }
);
