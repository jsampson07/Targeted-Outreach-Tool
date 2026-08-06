export type HistoryFilterValue = 'all' | 'logged' | 'unlogged'

type Props = {
  value: HistoryFilterValue
  onChange: (value: HistoryFilterValue) => void
}

const OPTIONS: { value: HistoryFilterValue; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'logged', label: 'Logged' },
  { value: 'unlogged', label: 'Not yet logged' },
]

/**
 * Client-side filter for the history list. Default (set by parent): Logged.
 * Changing filter does not hit the network — data is already fetched.
 */
export function HistoryFilter({ value, onChange }: Props) {
  return (
    <fieldset className="history-filter">
      <legend className="history-filter-legend">Show</legend>
      <div className="history-filter-options" role="radiogroup" aria-label="Show">
        {OPTIONS.map((option) => (
          <label key={option.value} className="history-filter-option">
            <input
              type="radio"
              name="history-filter"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
