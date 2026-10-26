import { STATUS_LABEL } from './format'

const COLUMNS = ['Row', 'Date', 'Description', 'Amount', 'Status', 'Category', 'Suggestion', 'Reason']

// A text cell starting with = + - @ can run as a formula when the file is opened in Excel.
// A leading apostrophe stops that. Amounts skip this on purpose: "-59.99" is a number.
function safeText(value) {
  const text = String(value ?? '')
  return /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
}

function escapeCell(text) {
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

// Amounts are decimal strings from the API and are written exactly as received.
export function buildCsv(rows) {
  const lines = [COLUMNS.join(',')]
  for (const r of rows) {
    const cells = [
      r.row,
      r.date ?? '',
      safeText(r.description),
      r.amount,
      STATUS_LABEL[r.status] ?? r.status,
      safeText(r.category),
      safeText(r.suggestion),
      safeText(r.reason),
    ]
    lines.push(cells.map((c) => escapeCell(String(c))).join(','))
  }
  return lines.join('\r\n')
}

export function exportFilename(uploadedName) {
  const base = (uploadedName || 'statement').replace(/\.[^.]+$/, '')
  return `${base}-categorized.csv`
}

export function downloadCsv(filename, csv) {
  // The BOM makes Excel read the file as UTF-8.
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}