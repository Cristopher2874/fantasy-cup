export function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function statusClass(status: string) {
  if (status === 'valid' || status === 'completed') {
    return 'status-valid';
  }
  if (status === 'invalid' || status === 'failed' || status === 'missing') {
    return 'status-invalid';
  }
  if (status === 'running' || status === 'queued') {
    return 'status-working';
  }
  return 'status-neutral';
}
