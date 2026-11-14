const PATHS = {
  play: 'M7 4.5v15l12-7.5z',
  pause: 'M7 4h3.5v16H7zM13.5 4H17v16h-3.5z',
  back: 'M11 18l-6-6 6-6M5 12h14',
  rewind: 'M12.5 8.5 9 12l3.5 3.5M9 12h7M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4',
  forward: 'M11.5 8.5 15 12l-3.5 3.5M15 12H8M20 12a8 8 0 1 1-2.4-5.7M20 4v4h-4',
  flag: 'M5 21V4m0 0h11l-2 4 2 4H5',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6 6 18',
  plus: 'M12 5v14M5 12h14',
  search: 'M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14zm9 3-4.3-4.3',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 9a7 7 0 0 1 14 0',
  users: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M16 3.5a4 4 0 0 1 0 7M18 14a6 6 0 0 1 4 7',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  video: 'M3 6h12v12H3zM15 10l6-3v10l-6-3',
  voices: 'M4 12h2M8 8v8M12 5v14M16 9v6M20 11v2',
  doc: 'M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6',
  external: 'M14 4h6v6M20 4l-9 9M18 14v6H4V6h6',
  refresh: 'M20 11a8 8 0 0 0-14.6-4.5M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5M20 20v-4h-4',
  edit: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4',
  alert: 'M12 8v5M12 16.5v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  star: 'M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 17l-5.2 2.7 1-5.9L3.5 9.7l5.9-.8z',
  chevron: 'M9 6l6 6-6 6',
  follow: 'M12 5v14M6 13l6 6 6-6',
  broadcast: 'M12 12h.01M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8',
  merge: 'M7 4v4a4 4 0 0 0 4 4h7M7 20v-4a4 4 0 0 1 4-4M15 9l3 3-3 3',
  upload: 'M12 16V4M7 9l5-5 5 5M4 16v4h16v-4',
  image: 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9.5h.01',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  tag: 'M3 12V4h8l10 10-8 8zM7.5 7.5h.01',
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps {
  readonly name: IconName;
  readonly size?: number;
  readonly filled?: boolean;
  readonly label?: string;
}

/** A line icon on a 24 px grid. Decorative unless it gets a `label`. */
export function Icon({ name, size = 18, filled = false, label }: IconProps) {
  const solid = filled || name === 'play' || name === 'pause';
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={solid ? 'currentColor' : 'none'}
      stroke={solid && name !== 'star' ? 'none' : 'currentColor'}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
