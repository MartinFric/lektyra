import { queryOptions } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest, seg } from '@/platform/api';
import { speakerStatus } from '@/features/events/api';

export const voicePointSchema = z.object({
  event_id: z.string(),
  event_title: z.string(),
  label: z.string(),
  talk_s: z.number(),
  person_id: z.number().int().nullable(),
  person_name: z.string().nullable(),
  person_anonymous: z.boolean().nullable(),
  status: speakerStatus,
  x: z.number(),
  y: z.number(),
  nearest: z.array(z.object({ event_id: z.string(), label: z.string(), similarity: z.number() })),
});

export type VoicePoint = z.infer<typeof voicePointSchema>;

export const voicesQuery = queryOptions({
  queryKey: ['voices'] as const,
  queryFn: ({ signal }) => apiRequest('/voices', z.array(voicePointSchema), { signal }),
});

export const clipSchema = z.object({
  event_id: z.string(),
  event_title: z.string(),
  label: z.string(),
  start_ms: z.number().int(),
  end_ms: z.number().int(),
});

export type Clip = z.infer<typeof clipSchema>;

/** A voice's clearest passages across videos (newest first). */
export function personClipsQuery(personId: number) {
  return queryOptions({
    queryKey: ['clips', 'person', personId] as const,
    queryFn: ({ signal }) => apiRequest(`/persons/${seg(personId)}/clips`, z.array(clipSchema), { signal }),
    staleTime: 0,
  });
}

/** One speaker's clearest passages in one video. */
export function speakerClipsQuery(eventId: string, label: string) {
  return queryOptions({
    queryKey: ['clips', 'speaker', eventId, label] as const,
    queryFn: ({ signal }) =>
      apiRequest(`/events/${seg(eventId)}/speakers/${seg(label)}/clips`, z.array(clipSchema), { signal }),
  });
}
