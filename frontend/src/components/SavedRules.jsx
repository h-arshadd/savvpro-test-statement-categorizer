export default function SavedRules({ rules, busy, onRemove }) {
  const entries = Object.entries(rules).sort(([a], [b]) => a.localeCompare(b))
  if (entries.length === 0) return null

  return (
    <details className="panel">
      <summary style={{ cursor: 'pointer' }}>Saved rules ({entries.length})</summary>
      <p className="muted note">
        Every row from these merchants is sorted this way without asking. Remove a rule and the
        merchant goes back to being decided by the built-in rules.
      </p>
      <ul className="totals">
        {entries.map(([merchant, category]) => (
          <li key={merchant}>
            <span>
              {merchant}
              <small className="muted"> → {category}</small>
            </span>
            <button disabled={busy} onClick={() => onRemove(merchant)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
    </details>
  )
}