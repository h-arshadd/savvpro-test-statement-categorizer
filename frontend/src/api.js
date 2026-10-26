async function request(url, options) {
  let res
  try {
    res = await fetch(url, options)
  } catch {
    throw new Error('Cannot reach the server. Is the backend running on port 8000?')
  }
  if (!res.ok) {
    let message = `Request failed (${res.status}).`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d) => d.msg).join('; ')
    } catch {
      // keep the generic message
    }
    throw new Error(message)
  }
  return res.json()
}

// overrides: { [rowNumber]: category } the user chose. Nothing is stored on the server,
// so the same file is sent again together with the user's fixes.
export function analyzeStatement(file, { sign, dayFirst, keepRows, overrides }) {
  const params = new URLSearchParams({ sign })
  if (dayFirst) params.set('day_first', 'true')
  keepRows.forEach((row) => params.append('keep_rows', String(row)))
  const form = new FormData()
  form.append('file', file)
  form.append('overrides', JSON.stringify(overrides))
  return request(`/api/statements?${params}`, { method: 'POST', body: form })
}

export function fetchCategories() {
  return request('/api/categories')
}