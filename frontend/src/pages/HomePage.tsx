import { useAuth } from '../context/AuthContext'

/** Placeholder home — real feature screens land in later frontend slices. */
export function HomePage() {
  const { logout } = useAuth()

  return (
    <main className="home-page">
      <h1>Logged in — nothing here yet</h1>
      <p>
        Auth foundation is wired. Company resolution, discovery, upload/extract,
        and generated-email screens will replace this stub.
      </p>
      <button type="button" onClick={() => void logout()}>
        Log out
      </button>
    </main>
  )
}
