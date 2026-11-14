import type { z } from 'zod';
import { AppError, errorEnvelopeSchema } from './errors';

/**
 * The one way the UI talks to the server. It never returns unchecked data: a success body is parsed with the
 * caller's zod schema, and every failure (an HTTP error, an unreachable server, a body that does not match)
 * becomes an AppError with a message written for a person.
 */
export const API_BASE = '/api';

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE';

export interface RequestOptions {
  readonly method?: Method;
  /** Sent as JSON. */
  readonly body?: unknown;
  /** A file sent as it is, with its own content type (a picture). */
  readonly upload?: Blob;
  readonly signal?: AbortSignal;
}

const UNREACHABLE = 'The lektyra server is not reachable. Is `lektyra ui` running?';

async function send(path: string, { method = 'GET', body, upload, signal }: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const init: RequestInit = { method, headers };
  if (upload !== undefined) {
    headers['Content-Type'] = upload.type || 'application/octet-stream';
    init.body = upload;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  if (signal) init.signal = signal;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new AppError('network', UNREACHABLE);
  }
  if (!response.ok) throw await failure(response);
  return response;
}

async function failure(response: Response): Promise<AppError> {
  const raw: unknown = await response.json().catch(() => null);
  const parsed = errorEnvelopeSchema.safeParse(raw);
  if (parsed.success) {
    const { code, message, details } = parsed.data.error;
    return new AppError(code, message, response.status, details ?? []);
  }
  if (response.status === 502 || response.status === 503 || response.status === 504) {
    return new AppError('network', UNREACHABLE, response.status);
  }
  return new AppError('internal', `The server answered ${response.status} without an explanation.`, response.status);
}

/** A request whose answer is JSON, checked against `schema`. */
export async function apiRequest<S extends z.ZodType>(
  path: string,
  schema: S,
  options: RequestOptions = {},
): Promise<z.output<S>> {
  const response = await send(path, options);
  const raw: unknown = await response.json().catch(() => undefined);
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    console.error(`Contract mismatch on ${options.method ?? 'GET'} ${path}`, parsed.error.issues);
    throw new AppError(
      'contract',
      'The server sent data this UI does not understand. Rebuild the UI (npm run build) and reload.',
      response.status,
      parsed.error.issues.map((i) => ({ field: i.path.map(String).join('.'), message: i.message })),
    );
  }
  return parsed.data;
}

/** A request that answers with no body (204). */
export async function apiSend(path: string, options: RequestOptions): Promise<void> {
  await send(path, options);
}

/** A URL the browser loads itself (audio). Same base, so it works behind the dev proxy too. */
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

/** One path segment, safe in a URL (variants contain `@`). */
export function seg(value: string | number): string {
  return encodeURIComponent(String(value));
}
