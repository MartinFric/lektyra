import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/platform/ui';
import { PHOTO_TYPES, type Person, usePhotoFromWikidata, useRemovePhoto, useUploadPhoto } from './api';
import { PersonFace } from './PersonFace';
import { photoCredit, photoProblem } from './photos';
import styles from './PhotoField.module.css';

const WIKIDATA = /^Q[1-9][0-9]*$/;

/**
 * A named person's picture (ADR-015): drop a file on it, pick one, or take the one Wikidata has for their saved
 * knowledge link. lektyra keeps a small copy without metadata, with where it came from.
 */
export function PhotoField({ person }: { readonly person: Person }) {
  const upload = useUploadPhoto();
  const wikidata = usePhotoFromWikidata();
  const remove = useRemovePhoto();
  const picker = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const busy = upload.isPending || wikidata.isPending || remove.isPending;
  const linked = person.external_ref !== null && WIKIDATA.test(person.external_ref);
  const credit = person.photo ? photoCredit(person.photo) : null;

  const send = (file: File | undefined) => {
    if (file === undefined) return;
    const problem = photoProblem(file);
    if (problem) {
      toast.error(problem);
      return;
    }
    upload.mutate({ id: person.id, file });
  };

  return (
    <div
      className={styles.field}
      data-dragging={dragging || undefined}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => { setDragging(false); }}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        send(e.dataTransfer.files[0]);
      }}
    >
      <PersonFace person={person} size="xl" />
      <div className={styles.side}>
        <div className={styles.actions}>
          <input
            ref={picker}
            type="file"
            accept={PHOTO_TYPES.join(',')}
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = ''; // the same file again is a new choice
              send(file);
            }}
          />
          <Button size="sm" icon="upload" loading={upload.isPending} disabled={busy} onClick={() => picker.current?.click()}>
            {person.photo ? 'Replace picture' : 'Upload picture'}
          </Button>
          {linked ? (
            <Button
              size="sm"
              icon="image"
              loading={wikidata.isPending}
              disabled={busy}
              onClick={() => { wikidata.mutate(person.id); }}
              title={`The picture Wikidata has for ${person.external_ref ?? ''}`}
            >
              From Wikidata
            </Button>
          ) : null}
          {person.photo ? (
            <Button
              size="sm"
              variant="ghost"
              icon="trash"
              loading={remove.isPending}
              disabled={busy}
              onClick={() => { remove.mutate(person.id); }}
            >
              Remove
            </Button>
          ) : null}
        </div>
        {credit ? (
          <p className={styles.credit}>
            {credit.href ? (
              <a href={credit.href} target="_blank" rel="noreferrer">
                {credit.source}
              </a>
            ) : (
              credit.source
            )}
            {credit.terms ? ` · ${credit.terms}` : null}
          </p>
        ) : (
          <p className={styles.credit}>
            {dragging ? 'Drop it here.' : 'Drop a picture here or upload one (JPEG, PNG, WebP, GIF).'}
            {linked ? ' Or take the one Wikidata has.' : ' A Wikidata id as knowledge link offers its picture too.'}
          </p>
        )}
      </div>
    </div>
  );
}
