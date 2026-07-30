import type { ReactNode } from 'react';
import { Footer } from './Footer';

type SiteShellProps = { children: ReactNode };

export function SiteShell({ children }: SiteShellProps) {
  return <div className="site-shell"><a className="skip-link" href="#main-content">跳到主要内容</a>{children}<Footer /></div>;
}
