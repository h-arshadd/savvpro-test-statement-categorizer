import { useEffect, useState } from 'react'
import { analyzeStatement, deleteRule, fetchCategories, fetchRules, saveRule } from './api'
import UploadPanel from './components/UploadPanel'
import SavedRules from './components/SavedRules'
import SummaryCards from './components/SummaryCards'
import TransactionTable from './components/TransactionTable'
import './App.css'

export default function App() {
  const [categories, setCategories] = useState([])
  const [rules, setRules] = useState({}) // saved merchant rules: { MERCHANT: category }
  const [source, setSource] = useState(null) // the file and options of the last analysis
  const [keepRows, setKeepRows] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const loadRules = () => fetchRules().then(setRules)

  useEffect(() => {
    fetchCategories()
      .then(setCategories)
      .catch((e) => setError(e.message))
    loadRules().catch((e) => setError(e.message))
  }, [])

  // beforeAnalyze is a change to the saved rules. With no file loaded yet there is nothing to
  // analyze, so only the rules change.
  async function run(nextSource, nextKeep, beforeAnalyze) {
    setLoading(true)
    setError('')
    try {
      if (beforeAnalyze) await beforeAnalyze()
      if (nextSource) {
        setResult(await analyzeStatement(nextSource.file, { ...nextSource.options, keepRows: nextKeep }))
      }
    } catch (e) {
      setError(e.message)
    } finally {
      loadRules().catch(() => {}) // keep the list in step with the server
      setLoading(false)
    }
  }

  function handleAnalyze(file, options) {
    const next = { file, options }
    setSource(next)
    setKeepRows([])
    setResult(null)
    run(next, [])
  }

  // The user's fix becomes a saved rule, then the same file is analyzed again.
  function handleCategorize(row, category) {
    run(source, keepRows, () => saveRule(row.description, category))
  }

  function handleKeep(row) {
    const next = [...keepRows, row.row]
    setKeepRows(next)
    run(source, next)
  }

  // Taking a rule back: delete it, then analyze the same file again without it.
  function handleRemoveRule(merchant) {
    run(source, keepRows, () => deleteRule(merchant))
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

      <SavedRules rules={rules} busy={loading} onRemove={handleRemoveRule} />

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
            onCategorize={handleCategorize}
            onKeep={handleKeep}
          />
          <p className="muted note">
            A category you choose is saved as a rule: the same merchant is sorted that way in every
            future statement. You can remove saved rules in the list under the upload form.
          </p>
        </>
      ) : (
        !loading &&
        !error && <p className="muted empty">Choose a CSV file and press Analyze to begin.</p>
      )}
    </main>
  )
}