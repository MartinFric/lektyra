import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { z } from 'zod';
import { apiRequest, apiSend, seg } from '@/platform/api';

const matchStatus = z.enum(['auto', 'suggested', 'unknown']);
export const speakerStatus = z.enum(['auto', 'suggested', 'unknown', 'confirmed', 'new']);
export type SpeakerStatus = z.infer<typeof speakerStatus>;

export const eventSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  source_url: z.string(),
  is_live: z.boolean(),
  audio_ms: z.number().int(),
  started_at: z.coerce.date(),
  speakers: z.number().int(),
  named: z.number().int(),
  transcripts: z.number().int(),
});

export const variantSchema = z.object({
  id: z.string(),
  engine: z.string(),
  language: z.string().nullable(),
  covered: z.number().int(),
  pieces: z.number().int(),
});

export const eventDetailSchema = eventSummarySchema.extend({
  complete: z.boolean().nullable(),
  has_audio: z.boolean(),
  variants: z.array(variantSchema),
  documents: z.array(z.object({ name: z.string(), size: z.number().int() })),
});

export const candidateSchema = z.object({
  person_id: z.number().int(),
  name: z.string(),
  score: z.number(),
  status: matchStatus,
  votes: z.number().int(),
});

export const speakerSchema = z.object({
  label: z.string(),
  talk_s: z.number(),
  share: z.number(),
  person_id: z.number().int().nullable(),
  person_name: z.string().nullable(),
  person_number: z.number().int().nullable(),
  person_anonymous: z.boolean().nullable(),
  status: speakerStatus,
  score: z.number().nullable(),
  candidates: z.array(candidateSchema),
  rejected: z.array(z.number().int()),
  no_profile: z.boolean(),
});

export type EventSummary = z.infer<typeof eventSummarySchema>;
export type EventDetail = z.infer<typeof eventDetailSchema>;
export type Variant = z.infer<typeof variantSchema>;
export type Candidate = z.infer<typeof candidateSchema>;
export type Speaker = z.infer<typeof speakerSchema>;

export const eventKeys = {
  all: ['events'] as const,
  list: () => ['events', 'list'] as const,
  detail: (id: string) => ['events', id, 'detail'] as const,
  speakers: (id: string) => ['events', id, 'speakers'] as const,
};

export const eventsQuery = queryOptions({
  queryKey: eventKeys.list(),
  queryFn: ({ signal }) => apiRequest('/events', z.array(eventSummarySchema), { signal }),
});

export function eventQuery(id: string) {
  return queryOptions({
    queryKey: eventKeys.detail(id),
    queryFn: ({ signal }) => apiRequest(`/events/${seg(id)}`, eventDetailSchema, { signal }),
  });
}

export function speakersQuery(id: string) {
  return queryOptions({
    queryKey: eventKeys.speakers(id),
    queryFn: ({ signal }) => apiRequest(`/events/${seg(id)}/speakers`, z.array(speakerSchema), { signal }),
  });
}

export function isComplete(v: Variant): boolean {
  return v.covered >= v.pieces;
}

/** A name changes guesses in every video (ADR-004), so every video's speakers, the persons and the map refresh. */
function useAfterNaming(): () => Promise<void> {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: eventKeys.all }),
      client.invalidateQueries({ queryKey: ['persons'] }),
      client.invalidateQueries({ queryKey: ['voices'] }),
    ]);
  };
}

interface Naming {
  readonly label: string;
  readonly personId: number;
  readonly personName: string;
}

export function useNameSpeaker(eventId: string) {
  const after = useAfterNaming();
  return useMutation({
    mutationFn: ({ label, personId }: Naming) =>
      apiSend(`/events/${seg(eventId)}/speakers/${seg(label)}/person`, { method: 'PUT', body: { person_id: personId } }),
    onSuccess: (_data, { label, personName }) => {
      toast.success(`${label} is ${personName}`, { description: 'Their voice now joins the profile; other videos are matched again.' });
    },
    onSettled: after,
  });
}

export function useUnnameSpeaker(eventId: string) {
  const after = useAfterNaming();
  return useMutation({
    mutationFn: (label: string) => apiSend(`/events/${seg(eventId)}/speakers/${seg(label)}/person`, { method: 'DELETE' }),
    meta: { success: 'Name removed, with the voice samples it gave.' },
    onSettled: after,
  });
}

export function useRejectCandidate(eventId: string) {
  const after = useAfterNaming();
  return useMutation({
    mutationFn: ({ label, personId }: Naming) =>
      apiSend(`/events/${seg(eventId)}/speakers/${seg(label)}/rejections`, { method: 'POST', body: { person_id: personId } }),
    onSuccess: (_data, { label, personName }) => {
      toast.success(`${label} is not ${personName}`, { description: 'They will not be suggested for this speaker again.' });
    },
    onSettled: after,
  });
}

const syncSchema = z.object({ events: z.number().int(), speakers: z.number().int() });

export function useSync() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest('/sync', syncSchema, { method: 'POST' }),
    onSuccess: (r) => {
      toast.success('Folders scanned', { description: `${String(r.events)} videos, ${String(r.speakers)} speakers.` });
    },
    onSettled: () => client.invalidateQueries(),
  });
}
