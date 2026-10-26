// Amounts arrive as decimal strings. Format them as text so money never goes through floats.
export function formatMoney(value) {
  const text = String(value)
  const negative = text.startsWith('-')
  const [whole, fraction = ''] = text.replace('-', '').split('.')
  const cents = (fraction + '00').slice(0, 2)
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negative ? '-' : ''}${grouped}.${cents}`
}

export function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

// Shown in the table and written to the exported CSV.
export const STATUS_LABEL = {
  categorized: 'Categorized',
  needs_review: 'Needs review',
  excluded: 'Not counted',
}