import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import logoUrl from '../assets/logo.svg'

type AppHeaderProps = {
  /** Right-side actions (e.g. Start new search / Log out). */
  actions?: ReactNode
}

/**
 * Persistent brand lockup + main nav for authenticated routes
 * (ARCHITECTURE.md §8.1 / §8.5 / §8.6). Logo mark + "Inroad" wordmark primary;
 * "Targeted Outreach Platform" caption always visible.
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
      <nav className="app-nav" aria-label="Main">
        <NavLink to="/" end className="app-nav-link">
          Search
        </NavLink>
        <NavLink to="/history" className="app-nav-link">
          History
        </NavLink>
      </nav>
      {actions ? (
        <div className="app-header-actions">{actions}</div>
      ) : null}
    </header>
  )
}
