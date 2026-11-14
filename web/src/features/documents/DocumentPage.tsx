import { useQuery } from '@tanstack/react-query';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { eventQuery } from '@/features/events/api';
import { useRequiredParam } from '@/platform/routing';
import { Card, PageHeader, QueryView, Skeleton } from '@/platform/ui';
import { documentQuery } from './api';
import styles from './DocumentPage.module.css';

/** A Markdown file next to the audio, rendered. react-markdown renders no raw HTML: what a transcript heard can
 * never become markup (HTN review #1). */
export function DocumentPage() {
  const eventId = useRequiredParam('eventId');
  const name = useRequiredParam('name');
  const event = useQuery(eventQuery(eventId));
  const doc = useQuery(documentQuery(eventId, name));
  return (
    <>
      <PageHeader back={{ to: `/videos/${encodeURIComponent(eventId)}`, label: event.data?.title ?? 'Video' }} title={name} />
      <Card className={styles.page}>
        <QueryView query={doc} loading={<Skeleton lines={12} />}>
          {(d) => (
            <article className={styles.prose}>
              <Markdown remarkPlugins={[remarkGfm]}>{d.text}</Markdown>
            </article>
          )}
        </QueryView>
      </Card>
    </>
  );
}
