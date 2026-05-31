export const apiEndpoints = {
  upload: '/upload',
  progress: '/progress',
  progressStream: (jobId: string) => `/progress/${encodeURIComponent(jobId)}/stream`,
};
