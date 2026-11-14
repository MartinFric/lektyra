import { queryOptions } from '@tanstack/react-query';
import { z } from 'zod';
import { apiRequest, seg } from '@/platform/api';

const documentSchema = z.object({ name: z.string(), text: z.string() });

export function documentQuery(eventId: string, name: string) {
  return queryOptions({
    queryKey: ['documents', eventId, name] as const,
    queryFn: ({ signal }) => apiRequest(`/events/${seg(eventId)}/documents/${seg(name)}`, documentSchema, { signal }),
  });
}
