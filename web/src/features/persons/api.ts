import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest, apiSend, apiUrl, seg } from '@/platform/api';

export const PERSON_KINDS = ['politician', 'host', 'journalist', 'expert', 'official', 'audience', 'other'] as const;
export const personKind = z.enum(PERSON_KINDS);
export type PersonKind = z.infer<typeof personKind>;

export const KIND_LABELS: Record<PersonKind, string> = {
  politician: 'Politician',
  host: 'Host / moderator',
  journalist: 'Journalist',
  expert: 'Expert',
  official: 'Official',
  audience: 'Audience / public',
  other: 'Other',
};

export const personSchema = z.object({
  id: z.number().int(),
  key: z.string(),
  number: z.number().int(),
  name: z.string(),
  anonymous: z.boolean(),
  kind: personKind,
  external_ref: z.string().nullable(),
  function: z.string().nullable(),
  party: z.string().nullable(),
  public_figure: z.boolean(),
  note: z.string().nullable(),
  samples: z.number().int(),
  events: z.number().int(),
  /** A face next to the name (ADR-015): where it came from and under which licence; null = no picture yet. */
  photo: z
    .object({
      version: z.string(),
      source_url: z.string().nullable(),
      license: z.string().nullable(),
      author: z.string().nullable(),
    })
    .nullable(),
});

export type Person = z.infer<typeof personSchema>;
export type PersonPhoto = NonNullable<Person['photo']>;

/** The picture's address. It carries the version, so a new picture is a new address and the old one may be cached
 * for ever. */
export function photoUrl(personId: number, photo: PersonPhoto): string {
  return `${apiUrl(`/persons/${seg(personId)}/photo`)}?v=${encodeURIComponent(photo.version)}`;
}

/** An unnamed voice heard in more videos than this is recurring: worth naming (Martin). */
export const RECURRING_AFTER = 3;

export function isRecurring(p: Pick<Person, 'anonymous' | 'events'>): boolean {
  return p.anonymous && p.events > RECURRING_AFTER;
}

export const MAX_PHOTO_BYTES = 15_000_000;
export const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'] as const;

export interface PersonInput {
  readonly name: string;
  readonly kind: PersonKind;
  readonly external_ref: string;
  readonly function: string;
  readonly party: string;
  readonly public_figure: boolean;
  readonly note: string;
}

export const personKeys = {
  all: ['persons'] as const,
};

export const personsQuery = queryOptions({
  queryKey: personKeys.all,
  queryFn: ({ signal }) => apiRequest('/persons', z.array(personSchema), { signal }),
});

/** Who a name touches: the persons list, every video's speakers and the voice map. */
function useInvalidateNames(): () => Promise<void> {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: personKeys.all }),
      client.invalidateQueries({ queryKey: ['events'] }),
      client.invalidateQueries({ queryKey: ['voices'] }),
    ]);
  };
}

/** Create (id null) or update a person. The form shows field errors itself, so no error toast here. */
export function useSavePerson() {
  const invalidate = useInvalidateNames();
  return useMutation({
    mutationFn: ({ id, input }: { readonly id: number | null; readonly input: PersonInput }) =>
      id === null
        ? apiRequest('/persons', personSchema, { method: 'POST', body: input })
        : apiRequest(`/persons/${seg(id)}`, personSchema, { method: 'PUT', body: input }),
    meta: { silent: true },
    onSettled: invalidate,
  });
}

/** Quick create from a picker: a name only, public figure by default. Errors toast. */
export function useCreatePersonByName() {
  const invalidate = useInvalidateNames();
  return useMutation({
    mutationFn: (name: string) =>
      apiRequest('/persons', personSchema, {
        method: 'POST',
        body: {
          name,
          kind: 'other',
          external_ref: '',
          function: '',
          party: '',
          public_figure: true,
          note: '',
        } satisfies PersonInput,
      }),
    onSettled: invalidate,
  });
}

/** A picture from a file (dropped or picked). lektyra re-encodes it; the person comes back with the new version. */
export function useUploadPhoto() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { readonly id: number; readonly file: Blob }) =>
      apiRequest(`/persons/${seg(id)}/photo`, personSchema, { method: 'PUT', upload: file }),
    meta: { success: 'Picture saved' },
    onSettled: () => client.invalidateQueries({ queryKey: personKeys.all }),
  });
}

/** The picture Wikidata has for the person's knowledge link (Q…), with its licence and author. */
export function usePhotoFromWikidata() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiRequest(`/persons/${seg(id)}/photo/wikidata`, personSchema, { method: 'POST' }),
    meta: { success: 'Picture taken from Wikidata' },
    onSettled: () => client.invalidateQueries({ queryKey: personKeys.all }),
  });
}

export function useRemovePhoto() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiSend(`/persons/${seg(id)}/photo`, { method: 'DELETE' }),
    meta: { success: 'Picture removed' },
    onSettled: () => client.invalidateQueries({ queryKey: personKeys.all }),
  });
}

/** "This unnamed voice is that person": the whole voice moves to them, in every video (ADR-012). */
export function useMergeVoice() {
  const invalidate = useInvalidateNames();
  return useMutation({
    mutationFn: ({ voiceId, intoId }: { readonly voiceId: number; readonly intoId: number }) =>
      apiRequest(`/persons/${seg(voiceId)}/merge`, personSchema, { method: 'POST', body: { into: intoId } }),
    onSettled: invalidate,
  });
}

/** Forget a person: they and every voice sample of theirs are deleted (ADR-005). */
export function useForgetPerson() {
  const invalidate = useInvalidateNames();
  return useMutation({
    mutationFn: (id: number) => apiSend(`/persons/${seg(id)}`, { method: 'DELETE' }),
    meta: { success: 'Forgotten: the person and their voice samples are deleted.' },
    onSettled: invalidate,
  });
}
