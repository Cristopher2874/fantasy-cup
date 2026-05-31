import { FileCheck } from '../../types';
import { formatFileSize } from '../../utils/formatters';

type FilePreflightProps = {
  fileChecks: FileCheck[];
  hasClientIssues: boolean;
  selectedFiles: File[];
  onRemoveFile: (index: number) => void;
};

export function FilePreflight({ fileChecks, hasClientIssues, selectedFiles, onRemoveFile }: FilePreflightProps) {
  return (
    <div className="preflight">
      <div className="panel-heading">
        <h2>Preflight checks</h2>
        <span className={hasClientIssues ? 'status-pill status-invalid' : 'status-pill status-valid'}>
          {selectedFiles.length === 0 ? 'Waiting' : hasClientIssues ? 'Needs attention' : 'Ready'}
        </span>
      </div>

      {selectedFiles.length === 0 ? (
        <p className="muted-text">No ZIP files selected.</p>
      ) : (
        <ul className="file-list">
          {fileChecks.map((check, index) => (
            <li key={`${check.file.name}-${check.file.lastModified}`}>
              <div>
                <strong>{check.file.name}</strong>
                <span>{formatFileSize(check.file.size)}</span>
                {check.issue && <p>{check.issue}</p>}
              </div>
              <button className="text-button" type="button" onClick={() => onRemoveFile(index)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
