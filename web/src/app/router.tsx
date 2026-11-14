import { createBrowserRouter, Navigate } from 'react-router';
import { DocumentPage } from '@/features/documents/DocumentPage';
import { EventPage } from '@/features/events/EventPage';
import { EventsPage } from '@/features/events/EventsPage';
import { PersonsPage } from '@/features/persons/PersonsPage';
import { TranscriptPage } from '@/features/transcript/TranscriptPage';
import { VoicesPage } from '@/features/voices/VoicesPage';
import { AppShell } from './AppShell';
import { NotFoundPage, RouteError } from './RouteError';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Navigate to="/videos" replace /> },
      { path: 'videos', element: <EventsPage /> },
      { path: 'videos/:eventId', element: <EventPage /> },
      { path: 'videos/:eventId/transcripts/:variant', element: <TranscriptPage /> },
      { path: 'videos/:eventId/documents/:name', element: <DocumentPage /> },
      { path: 'persons', element: <PersonsPage /> },
      { path: 'voices', element: <VoicesPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
