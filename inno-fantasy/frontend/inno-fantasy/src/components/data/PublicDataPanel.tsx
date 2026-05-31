import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchPublicDataIndex } from '../../services/api';
import { PublicDataIndex } from '../../types';
import { formatTimestamp } from '../../utils/formatters';

export function PublicDataPanel() {
  const [index, setIndex] = useState<PublicDataIndex | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPublicData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setIndex(await fetchPublicDataIndex());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load public data.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPublicData();
  }, [loadPublicData]);

  const manifest = index?.manifest;
  const expectedFiles = useMemo(() => Object.values(manifest?.files ?? {}), [manifest?.files]);
  const missingFiles = expectedFiles.filter((fileName) => !index?.files.includes(fileName));
  const statusLabel = index?.available ? (missingFiles.length > 0 ? 'partial' : 'ready') : 'missing';

  return (
    <aside className="data-panel" aria-label="Public data readiness">
      <div className="panel-heading">
        <h2>Public data</h2>
        <span className={`status-pill ${index?.available && missingFiles.length === 0 ? 'status-valid' : 'status-warning'}`}>
          {isLoading ? 'loading' : statusLabel}
        </span>
      </div>

      {manifest ? (
        <dl className="data-meta">
          <div>
            <dt>Matchday</dt>
            <dd>{manifest.matchday_id ?? 'n/a'}</dd>
          </div>
          <div>
            <dt>Date</dt>
            <dd>{manifest.match_date ?? 'n/a'}</dd>
          </div>
          <div>
            <dt>Generated</dt>
            <dd>{manifest.generated_at ? formatTimestamp(manifest.generated_at) : 'n/a'}</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>{manifest.source?.provider ?? 'n/a'}</dd>
          </div>
        </dl>
      ) : (
        <p className="muted-text">No public matchday manifest is available yet.</p>
      )}

      {index && (
        <div className="file-chip-row">
          {index.files.map((fileName) => (
            <span key={fileName}>{fileName}</span>
          ))}
        </div>
      )}

      {missingFiles.length > 0 && (
        <div className="alert alert-warning">Missing public files: {missingFiles.join(', ')}</div>
      )}
      {error && <div className="alert alert-warning">{error}</div>}

      <button className="text-button data-refresh" type="button" onClick={loadPublicData} disabled={isLoading}>
        Refresh public data
      </button>
    </aside>
  );
}
