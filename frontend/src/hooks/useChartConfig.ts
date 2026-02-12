import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import type { ChartType, QueryResult, ColumnInfo } from '../types';

/**
 * Options for configuring chart generation from query results.
 *
 * @remarks
 * These options control how query results are transformed into ECharts configurations.
 * Column selection can be automatic (based on data types) or manual (via xAxisColumn/yAxisColumn).
 */
interface UseChartConfigOptions {
  /** Query results to visualize */
  queryResult: QueryResult;
  /** Type of chart to generate (bar, line, pie, area, table) */
  chartType: ChartType;
  /** Optional explicit x-axis column name (auto-detected if not provided) */
  xAxisColumn?: string;
  /** Optional explicit y-axis column name (auto-detected if not provided) */
  yAxisColumn?: string;
}

/**
 * Check if a column contains numeric data suitable for charting.
 *
 * @param col - Column metadata to check
 * @returns True if the column can be used as numeric data in charts
 *
 * @remarks
 * A column is considered numeric if:
 * - It has a BigQuery numeric type (INTEGER, FLOAT64, NUMERIC, etc.)
 * - It's an enriched column (which may contain numeric values in `.value` property)
 * - It's a calculated column (which always contains numeric values)
 *
 * This function is used to identify columns suitable for y-axis, pie values, etc.
 *
 * @example
 * ```typescript
 * const columns: ColumnInfo[] = [
 *   { name: "state", type: "STRING" },
 *   { name: "population", type: "INTEGER" },
 *   { name: "_enriched_gdp", type: "INTEGER", is_enriched: true },
 * ];
 *
 * columns.filter(isNumericColumn);
 * // Returns: [{ name: "population", ... }, { name: "_enriched_gdp", ... }]
 * ```
 */
function isNumericColumn(col: ColumnInfo): boolean {
  // Standard numeric types
  if (['INTEGER', 'FLOAT', 'NUMERIC', 'INT64', 'FLOAT64', 'BIGNUMERIC'].includes(col.type.toUpperCase())) {
    return true;
  }
  // Enriched and calculated columns contain numeric values
  if (col.is_enriched || col.is_calculated) {
    return true;
  }
  return false;
}

/**
 * Extract a numeric value from primitive, enriched, or calculated column values.
 *
 * @param value - Value from a query result row (can be number, EnrichedValue, CalculatedValue, or other)
 * @returns Numeric representation of the value, or 0 if extraction fails
 *
 * @remarks
 * **CRITICAL FUNCTION** for handling query results with enriched and calculated data.
 *
 * Query result rows can contain three types of values:
 * 1. **Primitives**: Regular numbers, strings, booleans, null
 * 2. **EnrichedValue objects**: `{ value: number, source: string, confidence: "high", ... }`
 * 3. **CalculatedValue objects**: `{ value: number, expression: string, format_type: "percent", ... }`
 *
 * This function normalizes all three types to a simple number for charting.
 *
 * **Extraction Logic**:
 * - If value is null/undefined → Returns 0
 * - If value is an object with `.value` property → Extracts and parses `.value`
 * - If value is already a number → Returns it directly
 * - If value is a string → Attempts to parse as number (stripping non-numeric chars)
 * - If parsing fails → Returns 0
 *
 * **Use Case**:
 * When generating charts from query results, you must use this function to extract
 * numeric values because enriched/calculated columns contain objects, not primitives.
 *
 * @example
 * ```typescript
 * // Regular numeric value
 * extractNumericValue(42);  // Returns: 42
 *
 * // Enriched value (from Google Search enrichment)
 * const enriched = {
 *   value: 39500000,
 *   source: "U.S. Census (2023)",
 *   confidence: "high",
 *   freshness: "current",
 *   warning: null
 * };
 * extractNumericValue(enriched);  // Returns: 39500000
 *
 * // Calculated value (from add_calculated_column)
 * const calculated = {
 *   value: 263333,
 *   expression: "_enriched_population / store_count",
 *   format_type: "integer",
 *   is_calculated: true
 * };
 * extractNumericValue(calculated);  // Returns: 263333
 *
 * // String number with formatting
 * extractNumericValue("$1,234.56");  // Returns: 1234.56
 *
 * // Null or failed parsing
 * extractNumericValue(null);  // Returns: 0
 * extractNumericValue("invalid");  // Returns: 0
 *
 * // Using in chart data preparation
 * const chartData = queryResult.rows.map(row => ({
 *   category: row.state,
 *   value: extractNumericValue(row.population)  // Works for all value types!
 * }));
 * ```
 */
function extractNumericValue(value: unknown): number {
  if (value === null || value === undefined) return 0;
  // Handle enriched/calculated objects with .value property
  if (typeof value === 'object' && value !== null && 'value' in value) {
    const innerValue = (value as { value: unknown }).value;
    if (innerValue === null || innerValue === undefined) return 0;
    if (typeof innerValue === 'number') return innerValue;
    // Try to parse string numbers
    const parsed = parseFloat(String(innerValue).replace(/[^0-9.-]/g, ''));
    return isNaN(parsed) ? 0 : parsed;
  }
  // Regular numeric value
  if (typeof value === 'number') return value;
  // Try to parse string
  const parsed = parseFloat(String(value));
  return isNaN(parsed) ? 0 : parsed;
}

/**
 * Get all columns from a QueryResult that contain numeric data suitable for charting.
 *
 * @param columns - Array of column metadata from query results
 * @returns Filtered array containing only columns with numeric data
 *
 * @remarks
 * This is a convenience wrapper around `isNumericColumn()` for filtering column lists.
 * Used to identify which columns can be used for y-axis, pie chart values, etc.
 *
 * Numeric columns include:
 * - Regular BigQuery numeric types (INTEGER, FLOAT64, NUMERIC, etc.)
 * - Enriched columns (may contain numeric values in objects)
 * - Calculated columns (always contain numeric values in objects)
 *
 * @example
 * ```typescript
 * const result: QueryResult = {
 *   columns: [
 *     { name: "state", type: "STRING" },
 *     { name: "store_count", type: "INTEGER" },
 *     { name: "_enriched_population", type: "INTEGER", is_enriched: true },
 *     { name: "residents_per_store", type: "FLOAT64", is_calculated: true }
 *   ],
 *   // ...
 * };
 *
 * const numericCols = getNumericColumns(result.columns);
 * // Returns: [
 * //   { name: "store_count", type: "INTEGER" },
 * //   { name: "_enriched_population", type: "INTEGER", is_enriched: true },
 * //   { name: "residents_per_store", type: "FLOAT64", is_calculated: true }
 * // ]
 *
 * // Use for chart configuration
 * const yAxisOptions = numericCols.map(col => col.name);
 * ```
 */
export function getNumericColumns(columns: ColumnInfo[]): ColumnInfo[] {
  return columns.filter(isNumericColumn);
}

/**
 * React hook that generates ECharts configuration from query results.
 *
 * @param options - Configuration options for chart generation
 * @returns ECharts configuration object, or null if chart cannot be generated
 *
 * @remarks
 * This hook automatically transforms QueryResult data into Apache ECharts configurations
 * for various chart types. It handles all three types of column values (primitives,
 * enriched, calculated) using the `extractNumericValue()` helper.
 *
 * **Features**:
 * - **Auto-detection**: Automatically selects x/y columns if not specified
 * - **Type handling**: Correctly extracts values from enriched/calculated columns
 * - **Responsive styling**: Adjusts label rotation for long x-axes
 * - **Multiple chart types**: bar, line, area, pie
 * - **Memoization**: Caches result to prevent unnecessary recalculations
 *
 * **Auto-Detection Logic**:
 * - X-axis: First STRING/DATE column, or first column
 * - Y-axis: First numeric column, or second column
 *
 * **Supported Chart Types**:
 * - `bar`: Categorical comparisons (e.g., sales by state)
 * - `line`: Time series data (e.g., revenue over months)
 * - `area`: Cumulative trends (same as line with filled area)
 * - `pie`: Parts of a whole (limited to reasonable number of categories)
 * - `table`: Returns null (table rendering handled separately)
 *
 * **Value Extraction**:
 * Uses `extractNumericValue()` to handle enriched and calculated columns correctly.
 * This ensures charts work with all query result types.
 *
 * @example
 * ```tsx
 * import ReactECharts from 'echarts-for-react';
 *
 * function ChartPanel({ queryResult, chartType }: Props) {
 *   const chartConfig = useChartConfig({
 *     queryResult,
 *     chartType
 *   });
 *
 *   if (!chartConfig || chartType === 'table') {
 *     return <DataTable data={queryResult} />;
 *   }
 *
 *   return <ReactECharts option={chartConfig} />;
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Manual column selection
 * function CustomChart({ queryResult }: Props) {
 *   const chartConfig = useChartConfig({
 *     queryResult,
 *     chartType: 'bar',
 *     xAxisColumn: 'state',      // Explicit x-axis
 *     yAxisColumn: 'total_sales' // Explicit y-axis
 *   });
 *
 *   return <ReactECharts option={chartConfig!} />;
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Works with enriched data
 * function EnrichedChart({ queryResult }: Props) {
 *   // queryResult has enriched columns like "_enriched_population"
 *   const chartConfig = useChartConfig({
 *     queryResult,
 *     chartType: 'bar',
 *     yAxisColumn: '_enriched_population' // Enriched column!
 *   });
 *
 *   // extractNumericValue() is used internally to extract the .value
 *   return <ReactECharts option={chartConfig!} />;
 * }
 * ```
 */
export function useChartConfig({
  queryResult,
  chartType,
  xAxisColumn,
  yAxisColumn,
}: UseChartConfigOptions): EChartsOption | null {
  return useMemo(() => {
    if (!queryResult || chartType === 'table' || queryResult.rows.length === 0) {
      return null;
    }

    const { columns, rows } = queryResult;

    // Auto-detect x and y columns if not specified
    const numericColumns = columns.filter(isNumericColumn);
    const stringColumns = columns.filter((col) =>
      ['STRING', 'DATE', 'DATETIME', 'TIMESTAMP'].includes(col.type.toUpperCase()) &&
      !col.is_enriched && !col.is_calculated
    );

    const xCol = xAxisColumn || stringColumns[0]?.name || columns[0]?.name;
    const yCol = yAxisColumn || numericColumns[0]?.name || columns[1]?.name;

    if (!xCol || !yCol) {
      return null;
    }

    // Extract data - handle enriched/calculated values
    const xData = rows.map((row) => {
      const val = row[xCol];
      if (typeof val === 'object' && val !== null && 'value' in val) {
        return String((val as { value: unknown }).value ?? '');
      }
      return String(val ?? '');
    });
    const yData = rows.map((row) => extractNumericValue(row[yCol]));

    // Base options
    const baseOptions: EChartsOption = {
      tooltip: {
        trigger: chartType === 'pie' ? 'item' : 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e5e7eb',
        borderWidth: 1,
        textStyle: {
          color: '#374151',
        },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true,
      },
      color: [
        '#3b82f6', // blue
        '#10b981', // emerald
        '#f59e0b', // amber
        '#ef4444', // red
        '#8b5cf6', // violet
        '#ec4899', // pink
        '#06b6d4', // cyan
        '#84cc16', // lime
      ],
    };

    switch (chartType) {
      case 'bar':
        return {
          ...baseOptions,
          xAxis: {
            type: 'category',
            data: xData,
            axisLabel: {
              rotate: xData.length > 10 ? 45 : 0,
              interval: 0,
            },
          },
          yAxis: {
            type: 'value',
            name: yCol,
          },
          series: [
            {
              name: yCol,
              type: 'bar',
              data: yData,
              itemStyle: {
                borderRadius: [4, 4, 0, 0],
              },
            },
          ],
        };

      case 'line':
        return {
          ...baseOptions,
          xAxis: {
            type: 'category',
            data: xData,
            boundaryGap: false,
          },
          yAxis: {
            type: 'value',
            name: yCol,
          },
          series: [
            {
              name: yCol,
              type: 'line',
              data: yData,
              smooth: true,
              symbol: 'circle',
              symbolSize: 6,
            },
          ],
        };

      case 'area':
        return {
          ...baseOptions,
          xAxis: {
            type: 'category',
            data: xData,
            boundaryGap: false,
          },
          yAxis: {
            type: 'value',
            name: yCol,
          },
          series: [
            {
              name: yCol,
              type: 'line',
              data: yData,
              smooth: true,
              areaStyle: {
                opacity: 0.3,
              },
              symbol: 'circle',
              symbolSize: 6,
            },
          ],
        };

      case 'pie':
        const pieData = rows.map((row) => {
          const xVal = row[xCol];
          const name = typeof xVal === 'object' && xVal !== null && 'value' in xVal
            ? String((xVal as { value: unknown }).value ?? '')
            : String(xVal ?? '');
          return {
            name,
            value: extractNumericValue(row[yCol]),
          };
        });

        return {
          ...baseOptions,
          series: [
            {
              type: 'pie',
              radius: ['40%', '70%'],
              avoidLabelOverlap: true,
              itemStyle: {
                borderRadius: 4,
                borderColor: '#fff',
                borderWidth: 2,
              },
              label: {
                show: true,
                formatter: '{b}: {d}%',
              },
              emphasis: {
                label: {
                  show: true,
                  fontSize: 14,
                  fontWeight: 'bold',
                },
              },
              data: pieData,
            },
          ],
        };

      default:
        return null;
    }
  }, [queryResult, chartType, xAxisColumn, yAxisColumn]);
}
