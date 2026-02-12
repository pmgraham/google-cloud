import ReactECharts from 'echarts-for-react';
import type { ChartType, QueryResult } from '../../types';
import { useChartConfig } from '../../hooks/useChartConfig';

/**
 * Props for the ChartView component.
 *
 * @remarks
 * Configures which query results to visualize and how to display them.
 */
interface ChartViewProps {
  /** Query results to visualize */
  queryResult: QueryResult;
  /** Type of chart to render (bar, line, pie, area) */
  chartType: ChartType;
  /** Optional explicit y-axis column name (auto-detected if not provided) */
  yAxisColumn?: string;
}

/**
 * Chart visualization component using Apache ECharts.
 *
 * @param props - Component props
 * @returns Interactive ECharts visualization or error message
 *
 * @remarks
 * Renders query results as interactive charts using Apache ECharts via the
 * `echarts-for-react` wrapper. This component is a thin wrapper that delegates
 * chart configuration to the `useChartConfig` hook.
 *
 * **Supported Chart Types**:
 * - `bar`: Categorical comparisons (e.g., sales by state)
 * - `line`: Time series data (e.g., revenue over months)
 * - `area`: Cumulative trends (filled line chart)
 * - `pie`: Parts of a whole (limited to reasonable number of categories)
 *
 * **Chart Configuration**:
 * Uses `useChartConfig` hook which automatically:
 * - Detects x/y axis columns based on data types
 * - Extracts numeric values from enriched/calculated columns
 * - Applies appropriate styling and formatting
 * - Handles edge cases (empty data, incompatible types)
 *
 * **ECharts Integration**:
 * - Renderer: SVG (better quality, accessible)
 * - Fixed height: 320px (h-80)
 * - notMerge: true (completely replaces chart on data change)
 * - Responsive: Adapts to container width
 *
 * **Error Handling**:
 * If `useChartConfig` returns null (incompatible data), displays an error message
 * explaining why the chart cannot be rendered.
 *
 * **Data Compatibility**:
 * Works seamlessly with:
 * - Regular primitive values (numbers, strings)
 * - Enriched values (extracts `.value` property)
 * - Calculated values (extracts `.value` property and applies formatting)
 *
 * @example
 * ```tsx
 * // Basic usage with auto-detected columns
 * <ChartView
 *   queryResult={result}
 *   chartType="bar"
 * />
 * ```
 *
 * @example
 * ```tsx
 * // Explicit metric selection for multi-metric data
 * function ChartWithMetricSelector({ result }: Props) {
 *   const [metric, setMetric] = useState('total_sales');
 *
 *   return (
 *     <div>
 *       <select onChange={e => setMetric(e.target.value)}>
 *         <option value="total_sales">Total Sales</option>
 *         <option value="avg_price">Average Price</option>
 *       </select>
 *       <ChartView
 *         queryResult={result}
 *         chartType="bar"
 *         yAxisColumn={metric}
 *       />
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Works with enriched data automatically
 * const enrichedResult: QueryResult = {
 *   columns: [
 *     { name: "state", type: "STRING" },
 *     { name: "_enriched_population", type: "INTEGER", is_enriched: true }
 *   ],
 *   rows: [
 *     {
 *       state: "CA",
 *       _enriched_population: {
 *         value: 39500000,
 *         source: "U.S. Census",
 *         confidence: "high",
 *         freshness: "current",
 *         warning: null
 *       }
 *     }
 *   ],
 *   // ...
 * };
 *
 * // useChartConfig extracts the .value property automatically
 * <ChartView queryResult={enrichedResult} chartType="bar" />
 * ```
 */
export function ChartView({ queryResult, chartType, yAxisColumn }: ChartViewProps) {
  const chartOptions = useChartConfig({
    queryResult,
    chartType,
    yAxisColumn,
  });

  if (!chartOptions) {
    return (
      <div className="flex items-center justify-center h-80 text-gray-500">
        <p>Cannot display this data as a {chartType} chart</p>
      </div>
    );
  }

  return (
    <div className="w-full h-80">
      <ReactECharts
        option={chartOptions}
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'svg' }}
        notMerge={true}
      />
    </div>
  );
}
