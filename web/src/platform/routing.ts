import { useParams } from 'react-router';
import { AppError } from '@/platform/api';

/** A route parameter the page cannot live without; a missing one is a not-found page, not `undefined` later. */
export function useRequiredParam(name: string): string {
  const value = useParams()[name];
  if (!value) throw new AppError('not_found', `This address is missing its ${name}.`);
  return value;
}
