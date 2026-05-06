import axios from 'axios';
import { InventoryItem } from '../../App';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

const client = axios.create({ baseURL: API_BASE_URL, timeout: 30_000 });

export interface ScanResult {
  items: InventoryItem[];
  total_boxes: number;
}

export async function scanImage(imageUri: string): Promise<ScanResult> {
  const formData = new FormData();
  formData.append('file', {
    uri: imageUri,
    type: 'image/jpeg',
    name: 'scan.jpg',
  } as unknown as Blob);

  const response = await client.post<ScanResult>('/api/v1/scan', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return response.data;
}
