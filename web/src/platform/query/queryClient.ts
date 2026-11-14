import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { type AppError, toAppError } from '@/platform/api';

declare module '@tanstack/react-query' {
  interface Register {
    defaultError: AppError;
    mutationMeta: {
      /** Shown as a success toast when the mutation succeeds. */
      readonly success?: string;
      /** The component shows the error itself (e.g. next to a form field): no toast. */
      readonly silent?: boolean;
    };
  }
}

export function notifyError(error: unknown): void {
  const e = toAppError(error);
  toast.error(e.title, { description: e.message, id: `${e.code}:${e.message}` });
}

/**
 * Errors are shown once, in one place:
 * - a query with nothing on screen yet renders its own error panel (QueryView), no toast;
 * - a query that fails while refreshing data already on screen raises a toast, and the data stays;
 * - a mutation always raises a toast unless its meta says `silent`.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (query.state.data !== undefined) notifyError(error);
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (!mutation.meta?.silent) notifyError(error);
      },
      onSuccess: (_data, _variables, _context, mutation) => {
        const message = mutation.meta?.success;
        if (message) toast.success(message);
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        retry: (count, error) => toAppError(error).retryable && count < 2,
      },
      mutations: { retry: false },
    },
  });
}
