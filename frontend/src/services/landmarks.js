import axios from 'axios';
import { LANDMARK_API_URL } from '../config/network.js';

export const landmarkApi = axios.create({
  baseURL: LANDMARK_API_URL
});

export async function detectLandmarks(image, config = {}) {
  const { data } = await landmarkApi.post('/api/landmarks', { image }, config);
  return data;
}
