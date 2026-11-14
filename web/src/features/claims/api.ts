import { queryOptions } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest, seg } from '@/platform/api';

/** A checkable claim from the claims loop (spike-plan §8): what was said, the lekton, where it can be checked.
 * Not checked yet: no verdicts here. */
export const claimSchema = z.object({
  id: z.string(),
  speaker: z.string(),
  at_ms: z.number().int(),
  quote: z.string(),
  lekton: z.string(),
  kind: z.string(),
  entities: z.array(z.string()),
  numbers: z.array(z.string()),
  sources: z.array(z.string()),
  worth: z.number(),
  status: z.string(),
  links: z.array(z.tuple([z.string(), z.string()])),
});

export const claimsViewSchema = z.object({
  model: z.string().nullable(),
  stage: z.enum(['none', 'live', 'final']),
  minutes: z.number().int(),
  claims: z.array(claimSchema),
  /** Claims said by a host, left out (K60). */
  hidden_host: z.number().int(),
});

export type Claim = z.infer<typeof claimSchema>;
export type ClaimsView = z.infer<typeof claimsViewSchema>;

/** A video's claims. While it is live they grow every minute: asked again every 10 s. */
export function claimsQuery(eventId: string, live: boolean) {
  return queryOptions({
    queryKey: ['events', eventId, 'claims'] as const,
    queryFn: ({ signal }) => apiRequest(`/events/${seg(eventId)}/claims`, claimsViewSchema, { signal }),
    refetchInterval: live ? 10_000 : false,
  });
}

export const KIND_LABELS: Readonly<Record<string, string>> = {
  number: 'number',
  money: 'money',
  contract: 'contract',
  company: 'company',
  vote: 'vote',
  law: 'law',
  date: 'date',
  quote: 'quote',
  promise: 'promise',
  other: 'other',
};

export const SOURCE_LABELS: Readonly<Record<string, string>> = {
  crz: 'CRZ',
  ministry_invoices: 'ministry invoices',
  nrsr: 'NR SR',
  finstat: 'FinStat',
  budget: 'budget',
  statistics: 'statistics',
  eu_funds: 'EU funds',
  media: 'media',
  other: 'other',
};
