import { useQuery } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Button, Dialog, Field, Icon, IconButton, QueryView, Select, Skeleton, Spinner, TextInput } from '@/platform/ui';
import { type Upload, uploadsQuery, useDeleteUpload, useUploadVideo } from './api';
import styles from './LivePage.module.css';
import type { SourceChoice } from './sourceChoice';
import { CHANNELS } from './sources';

const MEDIA = '.mp4,.webm,.m4a,.mp3,.flac,.wav,.ogg,video/mp4,video/webm,audio/*';

function bytes(n: number): string {
  return n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${String(Math.max(1, Math.round(n / 1e6)))} MB`;
}

interface OptionProps {
  readonly group: string;
  readonly on: boolean;
  readonly onPick: () => void;
  readonly icon: 'broadcast' | 'external' | 'voices' | 'video';
  readonly title: string;
  readonly hint: string;
}

function Option({ group, on, onPick, icon, title, hint }: OptionProps) {
  return (
    <label className={styles.option} data-on={on}>
      <input type="radio" name={group} checked={on} onChange={onPick} className="visually-hidden" />
      <Icon name={icon} size={18} />
      <span className={styles.optionText}>
        <strong>{title}</strong>
        <span className={styles.muted}>{hint}</span>
      </span>
    </label>
  );
}

/** Pick a source: the three live channels, a YouTube or Facebook address, this PC's sound, or an uploaded video. */
export function SourcePicker({ state, group }: { readonly state: SourceChoice; readonly group: string }) {
  const { choice, setChoice } = state;
  return (
    <fieldset className={styles.sources}>
      <legend className={styles.legend}>Source</legend>
      <div className={styles.channels}>
        {CHANNELS.map((c) => (
          <Option
            key={c.source}
            group={group}
            on={choice.kind === 'channel' && choice.source === c.source}
            onPick={() => { setChoice({ kind: 'channel', source: c.source }); }}
            icon="broadcast"
            title={c.name}
            hint={c.hint}
          />
        ))}
      </div>
      <Option
        group={group}
        on={choice.kind === 'link'}
        onPick={() => { setChoice({ kind: 'link' }); }}
        icon="external"
        title="YouTube or Facebook"
        hint="A public video or live: paste its address"
      />
      {choice.kind === 'link' ? (
        <Field label="Address" error={state.problem ?? undefined}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              autoFocus
              value={state.link}
              onChange={(e) => { state.setLink(e.target.value); }}
              placeholder="https://www.youtube.com/watch?v=… or https://www.facebook.com/…/videos/…"
            />
          )}
        </Field>
      ) : null}
      <Option
        group={group}
        on={choice.kind === 'pc'}
        onPick={() => { setChoice({ kind: 'pc' }); }}
        icon="voices"
        title="This PC's sound"
        hint="Orange TV (Markíza…) in the browser: lektyra hears what the PC plays"
      />
      {choice.kind === 'pc' ? (
        <QueryView query={state.devices} loading={<Skeleton lines={1} height={36} />}>
          {(d) =>
            d.devices.length === 0 ? (
              <p className={styles.muted}>No sound output can be listened to on this PC.</p>
            ) : (
              <Field label="Listen to" hint="The output the browser plays on (headsets often have two)">
                {({ id, describedBy }) => (
                  <Select
                    id={id}
                    aria-describedby={describedBy}
                    value={state.output ?? ''}
                    onChange={(e) => { state.setDevice(e.target.value); }}
                  >
                    {d.devices.map((name) => (
                      <option key={name} value={name}>
                        {name}
                        {name === d.default ? ' (default)' : ''}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )
          }
        </QueryView>
      ) : null}
      <Uploads group={group} state={state} />
    </fieldset>
  );
}

/** Uploaded videos: played here while lektyra hears them at the same speed, as if they were live. */
function Uploads({ group, state }: { readonly group: string; readonly state: SourceChoice }) {
  const uploads = useQuery(uploadsQuery);
  const upload = useUploadVideo();
  const remove = useDeleteUpload();
  const picker = useRef<HTMLInputElement>(null);
  const [deleting, setDeleting] = useState<Upload | null>(null);
  const { choice, setChoice } = state;

  return (
    <div className={styles.uploads}>
      <div className={styles.uploadsHead}>
        <span className={styles.legend}>Uploaded videos, played as live</span>
        <input
          ref={picker}
          type="file"
          accept={MEDIA}
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = '';
            if (!file) return;
            upload.mutate(file, { onSuccess: (u) => { setChoice({ kind: 'upload', id: u.id }); } });
          }}
        />
        <Button size="sm" icon="upload" loading={upload.isPending} onClick={() => picker.current?.click()}>
          Upload…
        </Button>
      </div>
      {upload.isPending ? (
        <p className={styles.muted} role="status">
          <Spinner size={12} /> Uploading {upload.variables.name} ({bytes(upload.variables.size)}) to lektyra…
        </p>
      ) : null}
      <QueryView query={uploads} loading={<Skeleton lines={2} height={44} />}>
        {(list) =>
          list.length === 0 ? (
            <p className={styles.muted}>
              None yet. Upload a recording, or <code>uv run lektyra fetch &lt;YouTube, Facebook or TA3 address&gt;</code>.
            </p>
          ) : (
            <div className={styles.sourceList}>
              {list.map((u) => (
                <div key={u.id} className={styles.uploadRow}>
                  <Option
                    group={group}
                    on={choice.kind === 'upload' && choice.id === u.id}
                    onPick={() => { setChoice({ kind: 'upload', id: u.id }); }}
                    icon={u.kind === 'video' ? 'video' : 'voices'}
                    title={u.name}
                    hint={`${u.kind} · ${bytes(u.size)} · ${u.added_at.toLocaleDateString('sk-SK')}`}
                  />
                  <IconButton icon="trash" label={`Delete ${u.name}`} size="sm" onClick={() => { setDeleting(u); }} />
                </div>
              ))}
            </div>
          )
        }
      </QueryView>
      {deleting ? (
        <Dialog
          title={`Delete ${deleting.name}?`}
          tone="danger"
          onClose={() => { setDeleting(null); }}
          footer={
            <>
              <Button variant="ghost" onClick={() => { setDeleting(null); }}>
                Keep
              </Button>
              <Button
                variant="danger"
                icon="trash"
                loading={remove.isPending}
                onClick={() => {
                  remove.mutate(deleting.id, {
                    onSuccess: () => {
                      if (choice.kind === 'upload' && choice.id === deleting.id) {
                        setChoice({ kind: 'channel', source: 'ta3:live' });
                      }
                      setDeleting(null);
                    },
                    onError: () => { setDeleting(null); },
                  });
                }}
              >
                Delete
              </Button>
            </>
          }
        >
          <p>
            The file goes from lektyra&apos;s storage and this PC ({bytes(deleting.size)}). Videos already made from it
            stay in Videos.
          </p>
        </Dialog>
      ) : null}
    </div>
  );
}
