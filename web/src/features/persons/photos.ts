import { MAX_PHOTO_BYTES, PHOTO_TYPES, type PersonPhoto } from './api';

/** Why a file cannot be a picture, said before it is sent; null when it can. The server checks again. */
export function photoProblem(file: Pick<File, 'type' | 'size'>): string | null {
  if (!PHOTO_TYPES.some((t) => t === file.type)) return 'Use a JPEG, PNG, WebP or GIF picture.';
  if (file.size > MAX_PHOTO_BYTES) return 'The picture is larger than 15 MB. Use a smaller one.';
  return null;
}

export interface Credit {
  /** Where it came from, as a person would say it. */
  readonly source: string;
  readonly href: string | null;
  /** Licence and author, as the source states them. */
  readonly terms: string;
}

/** The credit line under a picture: source, licence, author. */
export function photoCredit(photo: PersonPhoto): Credit {
  const terms = [photo.license ?? 'licence unknown, local use only', photo.author ? `by ${photo.author}` : null]
    .filter(Boolean)
    .join(' · ');
  if (photo.source_url === null) return { source: 'Uploaded by you', href: null, terms: '' };
  let host = photo.source_url;
  try {
    host = new URL(photo.source_url).hostname.replace(/^www\./, '');
  } catch {
    // not a URL: show it as it is
  }
  const source = host.endsWith('wikimedia.org') ? 'Wikimedia Commons' : host;
  return { source, href: photo.source_url.startsWith('https://') ? photo.source_url : null, terms };
}
