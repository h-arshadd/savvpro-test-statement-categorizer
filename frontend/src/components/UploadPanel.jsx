import { useState } from 'react'

const SIGN_OPTIONS = [
  ['auto', 'Detect automatically'],
  ['negative_is_expense', 'Purchases are negative'],
  ['positive_is_expense', 'Purchases are positive'],
]

export default function UploadPanel({ onAnalyze, loading }) {
  const [file, setFile] = useState(null)
  const [sign, setSign] = useState('auto')
  const [dayFirst, setDayFirst] = useState(false)

  function submit(event) {
    event.preventDefault()
    if (file) onAnalyze(file, { sign, dayFirst })
  }

  return (
    <form className="panel upload" onSubmit={submit}>
      <label className="field grow">
        <span>Statement (.csv)</span>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files[0] ?? null)}
        />
      </label>
      <label className="field">
        <span>Amount signs</span>
        <select value={sign} onChange={(e) => setSign(e.target.value)}>
          {SIGN_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="check">
        <input type="checkbox" checked={dayFirst} onChange={(e) => setDayFirst(e.target.checked)} />
        <span>Dates are day/month</span>
      </label>
      <button type="submit" className="primary" disabled={!file || loading}>
        {loading ? 'Analyzing…' : 'Analyze'}
      </button>
    </form>
  )
}