import { useEffect, useState } from 'react'
import { analyzeStatement, fetchCategories } from './api'
import UploadPanel from './components/UploadPanel'
import SummaryCards from './components/SummaryCards'
import TransactionTable from './components/TransactionTable'
import './App.css'

export default function App() {
  const [categories, setCategories] = useState([])
  const [source, setSource] = useState(null) // the file and options of the last analysis
  const [overrides, setOverrides] = useState({}) // { rowNumber: category } chosen by the user
  const [keepRows, setKeepRows] = useState([]) // duplicates the user confirmed as real
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchCategories()
      .then(setCategories)
      .catch((e) => setError(e.message))
  }, [])

  // Nothing is saved on the server. Every change sends the same file again together with
  // the user's fixes, and the screen only updates if that succeeds.
  async function analyze(nextSource, nextOverrides, nextKeep) {
    setLoading(true)
    setError('')
    try {
      const next = await analyzeStatement(nextSource.file, {
        ...nextSource.options,
        overrides: nextOverrides,
        keepRows: nextKeep,
      })
      setSource(nextSource)
      setOverrides(nextOverrides)
      setKeepRows(nextKeep)
      setResult(next)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // A new upload starts clean: fixes belong to the file they were made on.
  function handleAnalyze(file, options) {
    setResult(null)
    analyze({ file, options }, {}, [])
  }

  function handleSetCategory(row, category) {
    analyze(source, { ...overrides, [row.row]: category }, keepRows)
  }

  function handleUndo(row) {
    const rest = { ...overrides }
    delete rest[row.row]
    analyze(source, rest, keepRows)
  }

  function handleKeep(row) {
    analyze(source, overrides, [...keepRows, row.row])
  }

  return (
    <main className="app">
      <header>
        <h1>Statement Categorizer</h1>
        <p className="muted">
          Upload a card statement. Every row is sorted by rules you can inspect, and anything
          uncertain is left for you to confirm.
        </p>
      </header>

      <UploadPanel onAnalyze={handleAnalyze} loading={loading} />

      {error && (
        <div className="callout error" role="alert">
          {error}
        </div>
      )}

      {result && result.warnings.length > 0 && (
        <div className="callout warn">
          <strong>Heads up</strong>
          <ul>
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {result ? (
        <>
          <SummaryCards summary={result.summary} />
          <TransactionTable
            rows={result.transactions}
            filename={result.filename}
            categories={categories}
            busy={loading}
            onSetCategory={handleSetCategory}
            onUndo={handleUndo}
            onKeep={handleKeep}
          />
          
        </>
      ) : (
        !loading &&
        !error && <p className="muted empty">Choose a CSV file and press Analyze to begin.</p>
      )}
    </main>
  )
}