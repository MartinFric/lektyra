import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest } from '@/platform/api';

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
});

export const liveSourceSchema = z.object({
  name: z.string(),
  size: z.number().int(),
  kind: z.enum(['video', 'audio']),
});

export const liveDevicesSchema = z.object({ devices: z.array(z.string()), default: z.string().nullable() });

export type LiveState = z.infer<typeof liveStateSchema>;
export type LiveSpeaker = z.infer<typeof liveSpeakerSchema>;
export type LiveTurn = z.infer<typeof liveTurnSchema>;
export type LiveSource = z.infer<typeof liveSourceSchema>;

export function isActive(status: LiveStatus): boolean {
  return status === 'loading' || status === 'running' || status === 'stopping';
}

const liveKeys = {
  state: ['live', 'state'] as const,
  sources: ['live', 'sources'] as const,
  devices: ['live', 'devices'] as const,
};

/** The session as the server sees it: polled every second while one runs, not at all otherwise. */
export const liveQuery = queryOptions({
  queryKey: liveKeys.state,
  queryFn: ({ signal }) => apiRequest('/live', liveStateSchema.nullable(), { signal }),
  refetchInterval: (query) => (query.state.data && isActive(query.state.data.status) ? 1000 : false),
  staleTime: 0,
});

export const liveSourcesQuery = queryOptions({
  queryKey: liveKeys.sources,
  queryFn: ({ signal }) => apiRequest('/live/sources', z.array(liveSourceSchema), { signal }),
});

/** The PC's sound outputs (for Orange TV in the browser). */
export const liveDevicesQuery = queryOptions({
  queryKey: liveKeys.devices,
  queryFn: ({ signal }) => apiRequest('/live/devices', liveDevicesSchema, { signal }),
});

export interface StartInput {
  readonly source: string;
  readonly title: string;
  readonly transcribe: boolean;
}

export function useStartLive() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: StartInput) => apiRequest('/live', liveStateSchema, { method: 'POST', body: input }),
    onSuccess: (state) => {
      client.setQueryData(liveKeys.state, state);
    },
    meta: { success: 'Live session started' },
  });
}

export function useStopLive() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest('/live/stop', liveStateSchema, { method: 'POST' }),
    onSuccess: (state) => {
      client.setQueryData(liveKeys.state, state);
    },
    onSettled: () => client.invalidateQueries({ queryKey: ['events'] }),
  });
}
