import { z } from 'zod';

/** Every failure the UI can meet, in one shape: the server's codes plus what only the browser sees. */
export type ErrorCode =
  | 'not_found'
  | 'conflict'
  | 'invalid'
  | 'unavailable'
  | 'internal'
  | 'network'
  | 'contract';

export interface FieldError {
  readonly field: string;
  readonly message: string;
}

const TITLES: Record<ErrorCode, string> = {
  not_found: 'Not found',
  conflict: 'Already there',
  invalid: 'Check the form',
  unavailable: 'Database not reachable',
  internal: 'Server error',
  network: 'Server not reachable',
  contract: 'Unexpected answer',
};

export class AppError extends Error {
  readonly code: ErrorCode;
  readonly status: number | null;
  readonly details: readonly FieldError[];

  constructor(code: ErrorCode, message: string, status: number | null = null, details: readonly FieldError[] = []) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /** A short heading for a toast or an error panel. */
  get title(): string {
    return TITLES[this.code];
  }

  /** Worth asking again: the network or the database may come back; a 404 or a bad form will not. */
  get retryable(): boolean {
    return this.code === 'network' || this.code === 'unavailable';
  }

  /** The message for one form field, if the server named it. */
  fieldMessage(field: string): string | undefined {
    return this.details.find((d) => d.field === field)?.message;
  }
}

export const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.enum(['not_found', 'conflict', 'invalid', 'unavailable', 'internal']),
    message: z.string(),
    details: z.array(z.object({ field: z.string(), message: z.string() })).nullable().optional(),
  }),
});

/** Anything thrown → AppError. Code that catches calls this instead of guessing what it caught. */
export function toAppError(error: unknown): AppError {
  if (error instanceof AppError) return error;
  if (error instanceof Error) return new AppError('internal', error.message);
  return new AppError('internal', 'Something went wrong.');
}
