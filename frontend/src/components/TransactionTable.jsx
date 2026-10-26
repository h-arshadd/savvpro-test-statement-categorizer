import { useState } from 'react'
import { formatMoney, STATUS_LABEL } from '../format'
import { buildCsv, downloadCsv, exportFilename } from '../exportCsv'

const FILTERS = [
  ['all', 'All'],
  ['needs_review', 'Needs review'],
  ['categorized', 'Categorized'],
  ['excluded', 'Not spending'],
]

function Action({ row, categories, busy, onCategorize, onKeep }) {
  if (row.status !== 'needs_review') return <span>{row.category}</span>

  if (row.duplicate_of) {
    return (
      <div className="actions">
        <button disabled={busy} onClick={() => onKeep(row)}>
          It&apos;s a real charge
        </button>
      </div>
    )
  }

  return (
    <div className="actions">
      {row.suggestion && (
        <button className="suggest" disabled={busy} onClick={() => onCategorize(row, row.suggestion)}>
          Use {row.suggestion}
        </button>
      )}
      <select
        aria-label={`Choose a category for ${row.description}`}
        value=""
        disabled={busy}
        onChange={(e) => e.target.value && onCategorize(row, e.target.value)}
      >
        <option value="">Choose category…</option>
        {categories.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </div>
  )
}

export default function TransactionTable({ rows, filename, categories, busy, onCategorize, onKeep }) {
  const [filter, setFilter] = useState('all')
  const countFor = (key) => (key === 'all' ? rows.length : rows.filter((r) => r.status === key).length)
  const visible = filter === 'all' ? rows : rows.filter((r) => r.status === filter)

  // Exports every row, not just the filtered view.
  const handleExport = () => downloadCsv(exportFilename(filename), buildCsv(rows))

  return (
    <section className="panel">
      <div className="table-head">
        <h2>Transactions</h2>
        <div className="filters" role="group" aria-label="Filter rows">
          {FILTERS.map(([key, label]) => (
            <button
              key={key}
              className={filter === key ? 'chip active' : 'chip'}
              onClick={() => setFilter(key)}
            >
              {label} ({countFor(key)})
            </button>
          ))}
        </div>
        <button onClick={handleExport} disabled={rows.length === 0}>
          Download CSV
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th className="num">Amount</th>
              <th>Status</th>
              <th>Category</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.row}>
                <td className="nowrap">{row.date ?? '—'}</td>
                <td title={`Merchant: ${row.merchant}`}>{row.description}</td>
                <td className={`num nowrap ${row.amount.startsWith('-') ? 'out' : 'in'}`}>
                  {formatMoney(row.amount)}
                </td>
                <td>
                  <span className={`badge ${row.status}`}>{STATUS_LABEL[row.status]}</span>
                </td>
                <td>
                  <Action
                    row={row}
                    categories={categories}
                    busy={busy}
                    onCategorize={onCategorize}
                    onKeep={onKeep}
                  />
                </td>
                <td className="muted why">{row.reason}</td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="muted empty">
                  No rows in this view.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}