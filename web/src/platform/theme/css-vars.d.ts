import 'react';

/** CSS custom properties components set inline. Declared here, so `style` stays typed without casts. */
declare module 'react' {
  interface CSSProperties {
    '--voice'?: string;
  }
}
