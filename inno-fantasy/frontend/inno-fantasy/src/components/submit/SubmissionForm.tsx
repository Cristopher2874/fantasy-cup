import { FormEvent } from 'react';
import { FileDropzone } from './FileDropzone';
import { FilePreflight } from './FilePreflight';
import { FileCheck } from '../../types';

type SubmissionFormProps = {
  fileChecks: FileCheck[];
  hasClientIssues: boolean;
  isDragging: boolean;
  isSubmitting: boolean;
  selectedFiles: File[];
  submitError: string | null;
  teamId: string;
  onDrop: (files: FileList) => void;
  onFileInput: (files: FileList) => void;
  onRemoveFile: (index: number) => void;
  onSetDragging: (value: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTeamIdChange: (value: string) => void;
};

export function SubmissionForm({
  fileChecks,
  hasClientIssues,
  isDragging,
  isSubmitting,
  selectedFiles,
  submitError,
  teamId,
  onDrop,
  onFileInput,
  onRemoveFile,
  onSetDragging,
  onSubmit,
  onTeamIdChange,
}: SubmissionFormProps) {
  return (
    <form className="submission-panel" onSubmit={onSubmit}>
      <div className="field-group">
        <label htmlFor="teamId">Team ID</label>
        <input
          id="teamId"
          name="teamId"
          placeholder="optional-team-id"
          value={teamId}
          onChange={(event) => onTeamIdChange(event.target.value)}
        />
      </div>

      <FileDropzone
        isDragging={isDragging}
        onDrop={onDrop}
        onFileInput={onFileInput}
        onSetDragging={onSetDragging}
      />

      <FilePreflight
        fileChecks={fileChecks}
        hasClientIssues={hasClientIssues}
        selectedFiles={selectedFiles}
        onRemoveFile={onRemoveFile}
      />

      {submitError && <div className="alert alert-error">{submitError}</div>}

      <button className="button button-primary full-width" type="submit" disabled={isSubmitting || hasClientIssues}>
        {isSubmitting ? 'Submitting...' : 'Submit skill batch'}
      </button>
    </form>
  );
}
