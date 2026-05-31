export const apiEndpoints = {
  upload: '/upload',
  progress: '/progress',
  progressStream: (jobId: string) => `/progress/${encodeURIComponent(jobId)}/stream`,
  scores: '/scores',
  score: (jobId: string) => `/scores/${encodeURIComponent(jobId)}`,
  scoreJob: (jobId: string, force = false) =>
    `/scores/${encodeURIComponent(jobId)}/score${force ? '?force=true' : ''}`,
};
