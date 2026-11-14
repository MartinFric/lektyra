import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { apiRequest, apiSend } from './client';
import { AppError } from './errors';

function answer(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

async function caught(promise: Promise<unknown>): Promise<AppError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof AppError) return error;
    throw error;
  }
  throw new Error('expected a failure');
}

const person = z.object({ id: z.number(), name: z.string() });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('apiRequest', () => {
  it('returns the parsed body', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(answer(200, { id: 1, name: 'A' }))));
    await expect(apiRequest('/persons/1', person)).resolves.toEqual({ id: 1, name: 'A' });
  });

  it("turns the server's error shape into an AppError with field messages", async () => {
    const body = {
      error: { code: 'invalid', message: 'Some fields are not valid.', details: [{ field: 'name', message: 'Required' }] },
    };
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(answer(422, body))));
    const error = await caught(apiRequest('/persons', person, { method: 'POST', body: {} }));
    expect(error.code).toBe('invalid');
    expect(error.status).toBe(422);
    expect(error.fieldMessage('name')).toBe('Required');
    expect(error.retryable).toBe(false);
  });

  it('says the server is not reachable when fetch itself fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))));
    const error = await caught(apiRequest('/persons', person));
    expect(error.code).toBe('network');
    expect(error.retryable).toBe(true);
  });

  it('refuses a body that does not match the schema', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(answer(200, { id: 'one' }))));
    const error = await caught(apiRequest('/persons/1', person));
    expect(error.code).toBe('contract');
    expect(error.details.map((d) => d.field)).toContain('id');
  });

  it('explains an error without the usual shape', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('oops', { status: 500 }))));
    const error = await caught(apiRequest('/persons', person));
    expect(error.code).toBe('internal');
    expect(error.message).toContain('500');
  });
});

describe('apiSend', () => {
  it('accepts an empty 204', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(null, { status: 204 }))));
    await expect(apiSend('/persons/1', { method: 'DELETE' })).resolves.toBeUndefined();
  });
});
