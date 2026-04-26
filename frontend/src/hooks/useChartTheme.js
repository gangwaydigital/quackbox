import { useTheme } from '../App'

/**
 * Theme-aware colors for recharts components. Recharts requires explicit
 * fill/stroke props on its axes and tooltips — they don't pick up Tailwind
 * `dark:` classes automatically.
 *
 * Spread the returned `axisProps` onto <XAxis> / <YAxis> and `tooltipProps`
 * onto <Tooltip> for legible charts in both light and dark mode.
 */
export function useChartTheme() {
  const { dark } = useTheme()
  const tickFill = dark ? '#9ca3af' : '#6b7280'      // gray-400 / gray-500
  const gridStroke = dark ? '#374151' : '#e5e7eb'    // gray-700 / gray-200
  const tooltipBg = dark ? '#111827' : '#ffffff'     // gray-900 / white
  const tooltipBorder = dark ? '#374151' : '#e5e7eb'
  const tooltipText = dark ? '#e5e7eb' : '#111827'

  return {
    dark,
    tickFill,
    gridStroke,
    axisProps: { tick: { fill: tickFill, fontSize: 10 }, stroke: gridStroke },
    tooltipProps: {
      contentStyle: {
        backgroundColor: tooltipBg,
        border: `1px solid ${tooltipBorder}`,
        borderRadius: 8,
        color: tooltipText,
        fontSize: 12,
      },
      labelStyle: { color: tooltipText },
      itemStyle: { color: tooltipText },
    },
  }
}
