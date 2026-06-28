type ResumeFn = (
  threadId: string,
  decision: 'approve' | 'reject' | 'edit',
  editedArgs?: Record<string, unknown>
) => void;

let resumeHandler: ResumeFn | null = null;

export function registerWsResumeHandler(fn: ResumeFn) {
  resumeHandler = fn;
}

export function wsResume(
  threadId: string,
  decision: 'approve' | 'reject' | 'edit',
  editedArgs?: Record<string, unknown>
) {
  resumeHandler?.(threadId, decision, editedArgs);
}
