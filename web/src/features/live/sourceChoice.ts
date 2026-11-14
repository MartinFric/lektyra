import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { liveDevicesQuery } from './api';
import { linkProblem } from './sources';

export type Choice =
  | { readonly kind: 'channel'; readonly source: string }
  | { readonly kind: 'link' }
  | { readonly kind: 'pc' }
  | { readonly kind: 'upload'; readonly id: string };

/** What to listen to, as one source string ('' while the choice is incomplete). State for SourcePicker. */
export function useSourceChoice() {
  const [choice, setChoice] = useState<Choice>({ kind: 'channel', source: 'ta3:live' });
  const [link, setLink] = useState('');
  const [device, setDevice] = useState<string | null>(null);
  const devices = useQuery({ ...liveDevicesQuery, enabled: choice.kind === 'pc' });
  const output = device ?? devices.data?.default ?? null;
  const problem = choice.kind === 'link' && link.trim() ? linkProblem(link) : null;
  const source =
    choice.kind === 'channel'
      ? choice.source
      : choice.kind === 'upload'
        ? `upload:${choice.id}`
        : choice.kind === 'pc'
          ? output
            ? `pc:sound:${output}`
            : ''
          : link.trim() && !problem
            ? link.trim()
            : '';
  return { choice, setChoice, link, setLink, devices, output, setDevice, source, problem };
}

export type SourceChoice = ReturnType<typeof useSourceChoice>;

/** Tell the user why nothing starts when the choice is incomplete. */
export function sourceHint(state: SourceChoice): string | null {
  if (state.source) return null;
  if (state.choice.kind === 'link') return state.problem ?? 'Paste a YouTube or Facebook address.';
  if (state.choice.kind === 'pc') return 'Pick a sound output.';
  return null;
}

export function notifyMissing(state: SourceChoice): boolean {
  const hint = sourceHint(state);
  if (hint) toast.error(hint);
  return hint !== null;
}
