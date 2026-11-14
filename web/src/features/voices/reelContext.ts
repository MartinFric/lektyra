import { createContext, useContext } from 'react';
import type { Clip } from './api';

export interface ReelState {
  /** Which button's reel is playing (or loading), e.g. `person:12` or `speaker:<event>/S2`. */
  readonly active: string | null;
  readonly loading: boolean;
  readonly clip: Clip | null;
  readonly index: number;
  readonly count: number;
  readonly play: (key: string, load: () => Promise<readonly Clip[]>) => void;
  readonly stop: () => void;
}

export const ReelContext = createContext<ReelState | null>(null);

export function useReel(): ReelState {
  const reel = useContext(ReelContext);
  if (!reel) throw new Error('useReel needs <ReelProvider> above it (app/App.tsx)');
  return reel;
}
