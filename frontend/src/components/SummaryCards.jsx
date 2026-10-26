import { formatMoney, plural } from '../format'

function Stat({ label, value, detail, tone }) {
  return (
    <div className={`panel stat ${tone ?? ''}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {detail && <small className="muted">{detail}</small>}
    </div>
  )
}

export default function SummaryCards({ summary }) {
  const { categories, income, excluded_count, needs_review_count, needs_review_net } = summary

  return (
    <section className="summary">
      <div className="panel">
        <h2>Spending by category</h2>
        {categories.length === 0 ? (
          <p className="muted">Nothing is categorized yet.</p>
        ) : (
          <ul className="totals">
            {categories.map((c) => (
              <li key={c.category}>
                <span>
                  {c.category}
                  <small className="muted"> · {plural(c.count, 'row')}</small>
                </span>
                <strong>{formatMoney(c.total)}</strong>
              </li>
            ))}
          </ul>
        )}
        <p className="muted note">Refunds reduce the category they came from.</p>
      </div>

      <div className="stats">
        <Stat label="Income received" value={formatMoney(income)} />
        <Stat
          label="Not counted"
          value={plural(excluded_count, 'row')}
          detail="Transfers, card payments and personal charges, left out of the totals"
        />
        <Stat
          label="Needs review"
          value={plural(needs_review_count, 'row')}
          tone={needs_review_count > 0 ? 'warn' : ''}
          detail={
            needs_review_count > 0
              ? `Net ${formatMoney(needs_review_net)} out, not in the totals yet`
              : 'Everything is sorted'
          }
        />
      </div>
    </section>
  )
}