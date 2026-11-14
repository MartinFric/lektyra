import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { claimsQuery } from './api';
import { type ClaimFilter, DEFAULT_FILTER, filterClaims } from './filter';

/** A video's claims and what of them is shown. One state for the panel, the timeline ticks and the paragraph chips,
 * so they always agree. */
export function useClaims(eventId: string, live: boolean) {
  const query = useQuery(claimsQuery(eventId, live));
  const [filter, setFilter] = useState<ClaimFilter>(DEFAULT_FILTER);
  const all = query.data?.claims ?? [];
  const shown = filterClaims(all, filter);
  return { query, filter, setFilter, all, shown };
}

export type ClaimsState = ReturnType<typeof useClaims>;
