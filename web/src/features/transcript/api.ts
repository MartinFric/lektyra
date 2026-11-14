import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest, apiSend, seg } from '@/platform/api';

export const paragraphSchema = z.object({
  start_ms: z.number().int(),
  end_ms: z.number().int(),
  label: z.string(),
  text: z.string(),
});

export const turnSchema = z.object({ start_ms: z.number().int(), end_ms: z.number().int(), label: z.string() });

export const transcriptSchema = z.object({
  variant: z.string(),
  paragraphs: z.array(paragraphSchema),
  turns: z.array(turnSchema),
  words: z.number().int(),
  unknown_words: z.number().int(),
});

export const ratingSchema = z.object({
  variant: z.string(),
  accuracy: z.number().int().min(1).max(5).nullable(),
  names_numbers: z.number().int().min(1).max(5).nullable(),
  note: z.string(),
  rated_at: z.coerce.date(),
});

export const flagKind = z.enum(['words', 'speaker', 'name_number', 'other']);

export const flagSchema = z.object({
  id: z.number().int(),
  variant: z.string(),
  at_ms: z.number().int(),
  kind: flagKind,
  note: z.string(),
});

export type Paragraph = z.infer<typeof paragraphSchema>;
export type Turn = z.infer<typeof turnSchema>;
export type Transcript = z.infer<typeof transcriptSchema>;
export type Rating = z.infer<typeof ratingSchema>;
export type FlagKind = z.infer<typeof flagKind>;
export type Flag = z.infer<typeof flagSchema>;

export const FLAG_KINDS: readonly { readonly kind: FlagKind; readonly label: string }[] = [
  { kind: 'words', label: 'Wrong words' },
  { kind: 'speaker', label: 'Wrong speaker' },
  { kind: 'name_number', label: 'Name or number' },
  { kind: 'other', label: 'Other' },
];

export function flagLabel(kind: FlagKind): string {
  return FLAG_KINDS.find((k) => k.kind === kind)?.label ?? kind;
}

export const transcriptKeys = {
  transcript: (eventId: string, variant: string) => ['transcripts', eventId, variant] as const,
  ratings: (eventId: string) => ['events', eventId, 'ratings'] as const,
  flags: (eventId: string, variant: string) => ['events', eventId, 'flags', variant] as const,
};

/** The words do not change while Martin reads: fetched once per variant. Names come from the speakers query. */
export function transcriptQuery(eventId: string, variant: string) {
  return queryOptions({
    queryKey: transcriptKeys.transcript(eventId, variant),
    queryFn: ({ signal }) =>
      apiRequest(`/events/${seg(eventId)}/transcripts/${seg(variant)}`, transcriptSchema, { signal }),
    staleTime: Infinity,
  });
}

export function ratingsQuery(eventId: string) {
  return queryOptions({
    queryKey: transcriptKeys.ratings(eventId),
    queryFn: ({ signal }) => apiRequest(`/events/${seg(eventId)}/ratings`, z.array(ratingSchema), { signal }),
  });
}

export function flagsQuery(eventId: string, variant: string) {
  return queryOptions({
    queryKey: transcriptKeys.flags(eventId, variant),
    queryFn: ({ signal }) =>
      apiRequest(`/events/${seg(eventId)}/flags?variant=${seg(variant)}`, z.array(flagSchema), { signal }),
  });
}

export interface RatingInput {
  readonly accuracy: number | null;
  readonly names_numbers: number | null;
  readonly note: string;
}

export function useRate(eventId: string, variant: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: RatingInput) =>
      apiRequest(`/events/${seg(eventId)}/ratings/${seg(variant)}`, ratingSchema, { method: 'PUT', body: input }),
    meta: { success: 'Rating saved' },
    onSettled: () => client.invalidateQueries({ queryKey: transcriptKeys.ratings(eventId) }),
  });
}

export interface FlagInput {
  readonly at_ms: number;
  readonly kind: FlagKind;
  readonly note: string;
}

export function useAddFlag(eventId: string, variant: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: FlagInput) =>
      apiRequest(`/events/${seg(eventId)}/flags`, flagSchema, { method: 'POST', body: { ...input, variant } }),
    meta: { success: 'Flag added' },
    onSettled: () => client.invalidateQueries({ queryKey: transcriptKeys.flags(eventId, variant) }),
  });
}

export function useDeleteFlag(eventId: string, variant: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (flagId: number) => apiSend(`/events/${seg(eventId)}/flags/${seg(flagId)}`, { method: 'DELETE' }),
    meta: { success: 'Flag removed' },
    onSettled: () => client.invalidateQueries({ queryKey: transcriptKeys.flags(eventId, variant) }),
  });
}
