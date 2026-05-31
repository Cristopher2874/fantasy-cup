export const apiEndpoints = {
  upload: 'upload',
  progress: 'progress',
  progressStream: (jobId: string) => `progress/${encodeURIComponent(jobId)}/stream`,
  publicData: 'public-data',
  publicDataFile: (fileName: string) => `public-data/files/${encodeURIComponent(fileName)}`,
  scores: 'scores',
  score: (jobId: string) => `scores/${encodeURIComponent(jobId)}`,
  scoreJob: (jobId: string, force = false) =>
    `scores/${encodeURIComponent(jobId)}/score${force ? '?force=true' : ''}`,
};
