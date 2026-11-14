import { QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { RouterProvider } from 'react-router';
import { Toaster } from 'sonner';
import { ReelProvider } from '@/features/voices/Reel';
import { createQueryClient } from '@/platform/query/queryClient';
import { router } from './router';

export function App() {
  const [client] = useState(createQueryClient);
  return (
    <QueryClientProvider client={client}>
      <ReelProvider>
        <RouterProvider router={router} />
      </ReelProvider>
      <Toaster
        position="bottom-right"
        richColors
        closeButton
        toastOptions={{ style: { fontFamily: 'var(--font-ui)', fontSize: 'var(--text-md)' } }}
      />
    </QueryClientProvider>
  );
}
