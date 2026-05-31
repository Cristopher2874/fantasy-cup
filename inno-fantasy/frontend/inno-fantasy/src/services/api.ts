import { PipelineJob, UploadResponse } from '../types';
import { apiEndpoints } from './endpoints';

export async function uploadSkillBatch(files: File[], teamId: string): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  if (teamId.trim()) {
    formData.append('team_id', teamId.trim());
  }

  const response = await fetch(apiEndpoints.upload, {
    method: 'POST',
    body: formData,
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throw new Error(formatApiError(payload));
  }

  return payload as UploadResponse;
}

export async function fetchProgressJobs(): Promise<PipelineJob[]> {
  const response = await fetch(apiEndpoints.progress);
  const payload = await parseResponse(response);

  if (!response.ok) {
    throw new Error(formatApiError(payload));
  }

  return Array.isArray(payload.jobs) ? (payload.jobs as PipelineJob[]) : [];
}

async function parseResponse(response: Response): Promise<Record<string, unknown>> {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return { detail: text };
  }
}

function formatApiError(payload: Record<string, unknown>): string {
  const detail = payload.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map(String).join(', ');
  }
  return 'The server rejected the request.';
}
