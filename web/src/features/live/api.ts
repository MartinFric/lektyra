import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest, apiSend, apiUrl, seg } from '@/platform/api';

export const liveStatus = z.enum(['loading', 'running', 'stopping', 'finished', 'failed']);
export type LiveStatus = z.infer<typeof liveStatus>;

const liveSpeakerSchema = z.object({
  label: z.string(),
  windows: z.number().int(),
  talk_s: z.number(),
  last_ms: z.number().int(),
  listed: z.boolean(),
});

const liveTurnSchema = z.object({ start_ms: z.number().int(), end_ms: z.number().int(), label: z.string() });

export const liveStateSchema = z.object({
  id: z.string(),
  status: liveStatus,
  message: z.string(),
  source: z.string(),
  title: z.string().nullable(),
  event_id: z.string().nullable(),
  is_live: z.boolean().nullable(),
  duration_s: z.number().nullable(),
  media: z.boolean(),
  started_at: z.coerce.date(),
  position_ms: z.number().int(),
  current: z.string().nullable(),
  speakers: z.array(liveSpeakerSchema),
  turns: z.array(liveTurnSchema),
  pieces: z.number().int(),
  transcribe: z.boolean(),
  transcribed: z.number().int(),
  stt_errors: z.number().int(),
  variant: z.string().nullable(),
  cost_usd: z.number(),
  claims: z.number().int(),
  claims_minutes: z.number().int(),
  claims_error: z.string().nullable(),
});

export const uploadSchema = z.object({
  id: z.string(),
  name: z.string(),
  size: z.number().int(),
  kind: z.enum(['video', 'audio']),
  added_at: z.coerce.date(),
});

export const runStatus = z.enum(['scheduled', 'running', 'done', 'failed', 'missed', 'cancelled']);

export const runSchema = z.object({
  id: z.string(),
  source: z.string(),
  title: z.string(),
  starts_at: z.coerce.date(),
  ends_at: z.coerce.date(),
  transcribe: z.boolean(),
  status: runStatus,
  session_id: z.string().nullable(),
  event_id: z.string().nullable(),
  message: z.string().nullable(),
});

export const liveDevicesSchema = z.object({ devices: z.array(z.string()), default: z.string().nullable() });

export type LiveState = z.infer<typeof liveStateSchema>;
export type LiveSpeaker = z.infer<typeof liveSpeakerSchema>;
export type LiveTurn = z.infer<typeof liveTurnSchema>;
export type Upload = z.infer<typeof uploadSchema>;
export type Run = z.infer<typeof runSchema>;
export type RunStatus = z.infer<typeof runStatus>;

export function isActive(status: LiveStatus): boolean {
  return status === 'loading' || status === 'running' || status === 'stopping';
}

const liveKeys = {
  sessions: ['live', 'sessions'] as const,
  devices: ['live', 'devices'] as const,
  uploads: ['live', 'uploads'] as const,
  schedule: ['live', 'schedule'] as const,
};

/** Every session of this server, running ones first. Polled every second while one runs; every few seconds
 * otherwise, so a scheduled run that starts on its own appears. */
export const liveSessionsQuery = queryOptions({
  queryKey: liveKeys.sessions,
  queryFn: ({ signal }) => apiRequest('/live/sessions', z.array(liveStateSchema), { signal }),
  refetchInterval: (query) => ((query.state.data ?? []).some((s) => isActive(s.status)) ? 1000 : 4000),
  staleTime: 0,
});

/** The PC's sound outputs (for Orange TV in the browser). */
export const liveDevicesQuery = queryOptions({
  queryKey: liveKeys.devices,
  queryFn: ({ signal }) => apiRequest('/live/devices', liveDevicesSchema, { signal }),
});

export const uploadsQuery = queryOptions({
  queryKey: liveKeys.uploads,
  queryFn: ({ signal }) => apiRequest('/uploads', z.array(uploadSchema), { signal }),
});

export const scheduleQuery = queryOptions({
  queryKey: liveKeys.schedule,
  queryFn: ({ signal }) => apiRequest('/schedule', z.array(runSchema), { signal }),
  refetchInterval: 5000,
});

/** The video a session plays next to lektyra (an uploaded one). */
export function mediaUrl(sessionId: string): string {
  return apiUrl(`/live/${seg(sessionId)}/media`);
}

export interface StartInput {
  readonly source: string;
  readonly title: string;
  readonly transcribe: boolean;
}

export function useStartLive() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: StartInput) => apiRequest('/live', liveStateSchema, { method: 'POST', body: input }),
    onSettled: () => client.invalidateQueries({ queryKey: liveKeys.sessions }),
    meta: { success: 'Live session started' },
  });
}

export function useStopLive() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiRequest(`/live/${seg(sessionId)}/stop`, liveStateSchema, { method: 'POST' }),
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: liveKeys.sessions }),
        client.invalidateQueries({ queryKey: ['events'] }),
      ]);
    },
  });
}

/** Upload a recording to play as live. lektyra keeps it in its MinIO until it is deleted. */
export function useUploadVideo() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      apiRequest(`/uploads?name=${encodeURIComponent(file.name)}`, uploadSchema, { method: 'PUT', upload: file }),
    onSettled: () => client.invalidateQueries({ queryKey: liveKeys.uploads }),
    meta: { success: 'Uploaded: ready to play as live' },
  });
}

export function useDeleteUpload() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiSend(`/uploads/${seg(id)}`, { method: 'DELETE' }),
    onSettled: () => client.invalidateQueries({ queryKey: liveKeys.uploads }),
    meta: { success: 'Deleted from lektyra' },
  });
}

export interface RunInput {
  readonly source: string;
  readonly title: string;
  readonly starts_at: string;
  readonly ends_at: string;
  readonly transcribe: boolean;
}

export function useAddRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: RunInput) => apiRequest('/schedule', runSchema, { method: 'POST', body: input }),
    meta: { silent: true }, // the dialog shows what is wrong next to the fields
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: liveKeys.schedule }),
        client.invalidateQueries({ queryKey: liveKeys.sessions }),
      ]);
    },
  });
}

export function useCancelRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest(`/schedule/${seg(id)}/cancel`, runSchema, { method: 'POST' }),
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: liveKeys.schedule }),
        client.invalidateQueries({ queryKey: liveKeys.sessions }),
      ]);
    },
  });
}
