import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { MAX_UPLOADS, MAX_ZIP_BYTES } from '../data/appContent';
import { fetchProgressJobs, uploadSkillBatch } from '../services/api';
import { apiEndpoints } from '../services/endpoints';
import { FileCheck, PipelineJob, SubmitController } from '../types';

export function useSkillSubmission(): SubmitController {
  const [teamId, setTeamId] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadResponse, setUploadResponse] = useState<SubmitController['uploadResponse']>(null);
  const [progressJobs, setProgressJobs] = useState<Record<string, PipelineJob>>({});
  const [recentJobs, setRecentJobs] = useState<PipelineJob[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [streamAlerts, setStreamAlerts] = useState<Record<string, string>>({});
  const streamRefs = useRef<Record<string, EventSource>>({});

  useEffect(() => closeStreams, []);

  const fileChecks = useMemo(
    () =>
      selectedFiles.map((file): FileCheck => {
        if (!file.name.toLowerCase().endsWith('.zip')) {
          return { file, ok: false, issue: 'File must use the .zip extension.' };
        }
        if (file.size > MAX_ZIP_BYTES) {
          return { file, ok: false, issue: 'File is larger than 5 MB.' };
        }
        return { file, ok: true };
      }),
    [selectedFiles],
  );

  const hasClientIssues = fileChecks.some((check) => !check.ok);
  const acceptedResults = uploadResponse?.results.filter((result) => result.valid) ?? [];
  const rejectedResults = uploadResponse?.results.filter((result) => !result.valid) ?? [];
  const executionResults = uploadResponse?.results.filter((result) => result.execution_job_id) ?? [];

  function closeStreams() {
    Object.values(streamRefs.current).forEach((source) => source.close());
    streamRefs.current = {};
  }

  function connectToProgress(jobId: string) {
    if (streamRefs.current[jobId]) {
      return;
    }

    try {
      const source = new EventSource(apiEndpoints.progressStream(jobId));
      streamRefs.current[jobId] = source;

      source.addEventListener('progress', (event) => {
        const message = event as MessageEvent<string>;
        const job = JSON.parse(message.data) as PipelineJob;
        setProgressJobs((current) => ({ ...current, [jobId]: job }));
        setStreamAlerts((current) => {
          const next = { ...current };
          delete next[jobId];
          return next;
        });

        if (job.status === 'completed' || job.status === 'failed' || job.status === 'missing') {
          source.close();
          delete streamRefs.current[jobId];
        }
      });

      source.onerror = () => {
        source.close();
        delete streamRefs.current[jobId];
        setStreamAlerts((current) => ({
          ...current,
          [jobId]: 'Live updates paused. Refresh execution jobs to poll the server.',
        }));
      };
    } catch {
      setStreamAlerts((current) => ({
        ...current,
        [jobId]: 'This browser could not open the live progress stream.',
      }));
    }
  }

  function handleFiles(files: FileList | File[]) {
    const incoming = Array.from(files);
    const limited = incoming.slice(0, MAX_UPLOADS);
    setSelectedFiles(limited);
    setSubmitError(incoming.length > MAX_UPLOADS ? `Only the first ${MAX_UPLOADS} ZIP files were selected.` : null);
    setUploadResponse(null);
    setProgressJobs({});
    setStreamAlerts({});
    closeStreams();
  }

  function removeFile(index: number) {
    setSelectedFiles((current) => current.filter((_, currentIndex) => currentIndex !== index));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    if (selectedFiles.length === 0) {
      setSubmitError('Select at least one skill ZIP before submitting.');
      return;
    }

    if (hasClientIssues) {
      setSubmitError('Fix the file checks before sending this batch.');
      return;
    }

    setIsSubmitting(true);
    setUploadResponse(null);
    setProgressJobs({});
    setStreamAlerts({});
    closeStreams();

    try {
      const uploadPayload = await uploadSkillBatch(selectedFiles, teamId);
      setUploadResponse(uploadPayload);

      const seededJobs = uploadPayload.results.reduce<Record<string, PipelineJob>>((jobs, result) => {
        if (!result.execution_job_id) {
          return jobs;
        }

        jobs[result.execution_job_id] = {
          job_id: result.execution_job_id,
          validation_job_id: result.job_id,
          team_id: uploadPayload.team_id,
          skill_name: result.skill_name,
          filename: result.filename,
          status: result.execution_status ?? 'queued',
          stage: 'queued',
          message: 'Skill is queued for execution.',
          issues: [],
          warnings: result.warnings ?? [],
        };
        return jobs;
      }, {});
      setProgressJobs(seededJobs);
      Object.keys(seededJobs).forEach(connectToProgress);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Upload failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function refreshJobs() {
    setSubmitError(null);
    try {
      const jobs = await fetchProgressJobs();
      setRecentJobs(jobs);
      setProgressJobs((current) => {
        const next = { ...current };
        jobs.forEach((job) => {
          next[job.job_id] = job;
        });
        return next;
      });
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Could not load execution jobs.');
    }
  }

  return {
    acceptedResults,
    executionResults,
    fileChecks,
    hasClientIssues,
    isDragging,
    isSubmitting,
    progressJobs,
    recentJobs,
    rejectedResults,
    selectedFiles,
    streamAlerts,
    submitError,
    teamId,
    uploadResponse,
    handleFiles,
    handleSubmit,
    refreshJobs,
    removeFile,
    setIsDragging,
    setTeamId,
  };
}
