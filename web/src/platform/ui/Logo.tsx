interface LogoProps {
  readonly size?: number;
}

/** Logo B: quotation corners around sound bars, the middle bar (the statement worth checking) in amber. */
export function LogoMark({ size = 32 }: LogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <path d="M22 42 V22 H42" fill="none" stroke="var(--signal)" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M98 78 V98 H78" fill="none" stroke="var(--signal)" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M38 54 v12 M50 46 v28 M70 42 v36 M82 52 v16" stroke="var(--speech)" strokeWidth="10" strokeLinecap="round" />
      <path d="M60 34 v52" stroke="var(--claim)" strokeWidth="10" strokeLinecap="round" />
    </svg>
  );
}
