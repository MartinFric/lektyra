import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { type Person, personsQuery, photoUrl } from './api';
import styles from './PersonFace.module.css';

type FacePerson = Pick<Person, 'id' | 'name' | 'anonymous' | 'number' | 'photo'>;
type Size = 'xs' | 'sm' | 'md' | 'xl';

interface PersonFaceProps {
  readonly person: FacePerson;
  readonly size?: Size;
  readonly className?: string;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
}

/**
 * A person's face (ADR-015), so a name is recognised at a glance. Without a picture, or when it cannot be loaded:
 * their initials; an unnamed voice shows its number. Decorative: the name is always written next to it.
 */
export function PersonFace({ person, size = 'md', className }: PersonFaceProps) {
  const [broken, setBroken] = useState<string | null>(null); // the version that failed to load
  const photo = person.photo;
  return (
    <span
      className={[styles.face, person.anonymous ? styles.numbered : '', className ?? ''].join(' ')}
      data-size={size}
      aria-hidden="true"
    >
      {photo !== null && broken !== photo.version ? (
        <img
          className={styles.img}
          src={photoUrl(person.id, photo)}
          alt=""
          loading="lazy"
          decoding="async"
          draggable={false}
          onError={() => { setBroken(photo.version); }}
        />
      ) : person.anonymous ? (
        `#${String(person.number)}`
      ) : (
        initials(person.name)
      )}
    </span>
  );
}

/** The face of a person known only by id (a speaker's name), from the persons list the app already holds. */
export function FaceOf({ personId, size = 'sm' }: { readonly personId: number; readonly size?: Size }) {
  const persons = useQuery(personsQuery);
  const person = persons.data?.find((p) => p.id === personId);
  return person ? <PersonFace person={person} size={size} /> : null;
}
