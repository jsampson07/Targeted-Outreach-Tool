import type { ReactNode } from 'react'

import logoUrl from '../assets/logo.svg'

type AppHeaderProps = {
  /** Right-side actions (e.g. Start new search / Log out on the home route). */
  actions?: ReactNode
}

/**
 * Persistent brand lockup for the logged-in home route (ARCHITECTURE.md §8.1).
 * Logo mark + "Inroad" wordmark primary; "Targeted Outreach Platform" caption
 * always visible beside/beneath — not login-only.
 */
export function AppHeader({ actions }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div className="app-brand">
        <img
          className="app-brand-mark"
          src={logoUrl}
          alt=""
          width={36}
          height={36}
        />
        <div className="app-brand-text">
          <span className="app-brand-wordmark">Inroad</span>
          <span className="app-brand-caption">Targeted Outreach Platform</span>
        </div>
      </div>
      {actions ? (
        <div className="app-header-actions">{actions}</div>
      ) : null}
    </header>
  )
}
