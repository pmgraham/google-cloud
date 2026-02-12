import { useState, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  SortingState,
} from '@tanstack/react-table';
import { ArrowUpDown, ChevronLeft, ChevronRight, Zap, Calculator, AlertTriangle } from 'lucide-react';
import type { QueryResult, EnrichedValue, CalculatedValue } from '../../types';

/**
 * Props for the DataTable component.
 *
 * @remarks
 * Configures which query results to display in the data table.
 */
interface DataTableProps {
  /** Query results to display in table format */
  queryResult: QueryResult;
}

/**
 * Type guard to check if a value is an EnrichedValue object.
 *
 * @param value - Value to check (can be any type from query result row)
 * @returns True if value is an EnrichedValue with metadata
 *
 * @remarks
 * EnrichedValue objects come from the data enrichment workflow when the agent
 * augments query results with real-time data from Google Search. These objects
 * contain the actual value plus metadata (source, confidence, freshness, warnings).
 *
 * **Structure Check**:
 * - Must be an object (not null, not primitive)
 * - Must have `value` property (the actual data)
 * - Must have `source` property (attribution)
 * - Must have `confidence` property (quality indicator)
 *
 * **Use Case**:
 * Used in cell rendering logic to determine whether to display enriched value
 * with special styling (purple) and metadata tooltip.
 *
 * @example
 * ```typescript
 * const cellValue = row['_enriched_population'];
 *
 * if (isEnrichedValue(cellValue)) {
 *   // cellValue is typed as EnrichedValue
 *   console.log(cellValue.value);       // 39500000
 *   console.log(cellValue.source);      // "U.S. Census (2023)"
 *   console.log(cellValue.confidence);  // "high"
 * } else {
 *   // Regular primitive value
 *   console.log(cellValue);  // 42
 * }
 * ```
 */
function isEnrichedValue(value: unknown): value is EnrichedValue {
  return (
    typeof value === 'object' &&
    value !== null &&
    'value' in value &&
    'source' in value &&
    'confidence' in value
  );
}

/**
 * Type guard to check if a value is a CalculatedValue object.
 *
 * @param value - Value to check (can be any type from query result row)
 * @returns True if value is a CalculatedValue with formula metadata
 *
 * @remarks
 * CalculatedValue objects come from the `add_calculated_column` tool when the
 * agent derives new columns from existing data without re-running the SQL query.
 * These objects contain the computed value plus metadata (formula, format type, warnings).
 *
 * **Structure Check**:
 * - Must be an object (not null, not primitive)
 * - Must have `is_calculated` property set to `true`
 *
 * **Use Case**:
 * Used in cell rendering logic to determine whether to display calculated value
 * with special styling (blue, monospace font) and formula tooltip.
 *
 * @example
 * ```typescript
 * const cellValue = row['residents_per_store'];
 *
 * if (isCalculatedValue(cellValue)) {
 *   // cellValue is typed as CalculatedValue
 *   console.log(cellValue.value);         // 263333
 *   console.log(cellValue.expression);    // "_enriched_population / store_count"
 *   console.log(cellValue.format_type);   // "integer"
 * } else {
 *   // Regular primitive value
 *   console.log(cellValue);  // 42
 * }
 * ```
 */
function isCalculatedValue(value: unknown): value is CalculatedValue {
  return (
    typeof value === 'object' &&
    value !== null &&
    'is_calculated' in value &&
    (value as CalculatedValue).is_calculated === true
  );
}

/**
 * Format a calculated value according to its format type specification.
 *
 * @param value - Numeric value to format (can be null)
 * @param formatType - Format type from CalculatedValue metadata
 * @returns Formatted string representation of the value
 *
 * @remarks
 * This function applies the appropriate formatting to calculated column values
 * based on the `format_type` specified when the column was created via
 * `add_calculated_column`.
 *
 * **Supported Format Types**:
 * - `integer`: Rounds to whole number with thousands separators (e.g., `1,234`)
 * - `percent`: Shows as percentage with 1 decimal place (e.g., `45.2%`)
 * - `currency`: Shows as USD with 2 decimal places (e.g., `$1,234.56`)
 * - `number` (default): Shows with up to 2 decimal places and thousands separators (e.g., `1,234.56`)
 *
 * **Null Handling**:
 * Returns em dash (`—`) for null values instead of "null" or blank string.
 *
 * @example
 * ```typescript
 * formatCalculatedValue(263333, 'integer');    // "263,333"
 * formatCalculatedValue(45.234, 'percent');    // "45.2%"
 * formatCalculatedValue(1234.56, 'currency');  // "$1,234.56"
 * formatCalculatedValue(1234.567, 'number');   // "1,234.57"
 * formatCalculatedValue(null, 'integer');      // "—"
 * ```
 *
 * @example
 * ```typescript
 * // Usage in cell rendering
 * if (isCalculatedValue(cellValue)) {
 *   const formatted = formatCalculatedValue(cellValue.value, cellValue.format_type);
 *   return <span className="font-mono">{formatted}</span>;
 * }
 * ```
 */
function formatCalculatedValue(value: number | null, formatType: string): string {
  if (value === null) return '—';

  switch (formatType) {
    case 'integer':
      return Math.round(value).toLocaleString();
    case 'percent':
      return `${value.toFixed(1)}%`;
    case 'currency':
      return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    default: // number
      return value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }
}

/**
 * Get user-friendly display name for a column by removing internal prefixes.
 *
 * @param colName - Column name (may include `_enriched_` prefix)
 * @returns Clean column name without prefix
 *
 * @remarks
 * Enriched columns are prefixed with `_enriched_` internally to distinguish them
 * from original query columns. This function removes that prefix for display purposes.
 *
 * **Examples**:
 * - `_enriched_population` → `population`
 * - `_enriched_capital` → `capital`
 * - `store_count` → `store_count` (no change)
 *
 * @example
 * ```typescript
 * getDisplayName('_enriched_population');  // "population"
 * getDisplayName('state');                 // "state"
 * getDisplayName('_enriched_gdp');         // "gdp"
 * ```
 *
 * @example
 * ```typescript
 * // Usage in table header
 * <th>
 *   {col.is_enriched && <Zap />}
 *   {getDisplayName(col.name)}
 * </th>
 * ```
 */
function getDisplayName(colName: string): string {
  if (colName.startsWith('_enriched_')) {
    return colName.replace('_enriched_', '');
  }
  return colName;
}

/**
 * Tailwind CSS classes for confidence level badges in enriched value tooltips.
 *
 * @remarks
 * Maps confidence levels to appropriate color schemes using Tailwind utility classes.
 * Displayed in enriched value tooltips to indicate data quality.
 *
 * - `high`: Green (reliable, verified data)
 * - `medium`: Yellow (moderately reliable)
 * - `low`: Red (questionable, needs verification)
 */
const confidenceColors = {
  high: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-red-100 text-red-700',
};

/**
 * Tailwind CSS classes for freshness level badges in enriched value tooltips.
 *
 * @remarks
 * Maps freshness levels to appropriate color schemes using Tailwind utility classes.
 * Displayed in enriched value tooltips to indicate data currency.
 *
 * - `static`: Blue (timeless data, e.g., founding date)
 * - `current`: Green (recently updated, actively maintained)
 * - `dated`: Yellow (somewhat old but still usable)
 * - `stale`: Red (outdated, needs refresh)
 */
const freshnessColors = {
  static: 'bg-blue-100 text-blue-700',
  current: 'bg-green-100 text-green-700',
  dated: 'bg-yellow-100 text-yellow-700',
  stale: 'bg-red-100 text-red-700',
};

/**
 * Data table component with sorting, pagination, and rich rendering of enriched/calculated values.
 *
 * @param props - Component props
 * @returns Interactive data table with metadata tooltips
 *
 * @remarks
 * **Primary data table component** for displaying BigQuery query results with special
 * handling for enriched and calculated columns.
 *
 * **Features**:
 * - **Sorting**: Click column headers to sort ascending/descending
 * - **Pagination**: 10 rows per page with prev/next controls
 * - **Column highlighting**:
 *   - Purple background for enriched columns (data from Google Search)
 *   - Blue background for calculated columns (derived formulas)
 * - **Rich tooltips**:
 *   - Enriched values: Show source, confidence, freshness, warnings on hover
 *   - Calculated values: Show formula, format type, warnings on hover
 * - **Smart formatting**:
 *   - Numbers: Thousands separators, 2 decimal places
 *   - Integers: Thousands separators, no decimals
 *   - Calculated: Format based on type (integer, percent, currency, number)
 *   - Null values: Display as italic "null" or "no data"
 *
 * **TanStack Table Integration** (React Table v8):
 * - Uses `useReactTable` hook for state management
 * - Core features: sorting, pagination, column definitions
 * - Flexible rendering via `flexRender` helper
 * - Type-safe with `createColumnHelper`
 *
 * **Cell Rendering Logic**:
 * 1. Check if value is `EnrichedValue` → Render with purple styling + metadata tooltip
 * 2. Check if value is `CalculatedValue` → Render with blue styling + formula tooltip
 * 3. Otherwise → Render as regular value (null, number, or string)
 *
 * **Column Header Rendering**:
 * - Enriched columns: Purple text + Zap icon + clean name (without `_enriched_` prefix)
 * - Calculated columns: Blue text + Calculator icon + name
 * - Regular columns: Default text + name
 * - All headers: Clickable with sort icon
 *
 * **Visual Indicators**:
 * - Purple columns: Data enriched from Google Search
 * - Blue columns: Calculated from existing columns
 * - Warning icon (⚠): Data quality issues or calculation errors
 * - Hover tooltips: Full metadata for enriched/calculated values
 *
 * @example
 * ```tsx
 * import { DataTable } from './DataTable';
 *
 * function ResultsView({ queryResult }: { queryResult: QueryResult }) {
 *   return (
 *     <div className="border rounded-lg overflow-hidden">
 *       <DataTable queryResult={queryResult} />
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Query result with enriched data
 * const enrichedResult: QueryResult = {
 *   columns: [
 *     { name: "state", type: "STRING" },
 *     { name: "_enriched_capital", type: "STRING", is_enriched: true }
 *   ],
 *   rows: [
 *     {
 *       state: "California",
 *       _enriched_capital: {
 *         value: "Sacramento",
 *         source: "Wikipedia: California",
 *         confidence: "high",
 *         freshness: "current",
 *         warning: null
 *       }
 *     }
 *   ],
 *   total_rows: 50,
 *   // ...
 * };
 *
 * <DataTable queryResult={enrichedResult} />
 * // Renders:
 * // - "capital" header (purple, with Zap icon)
 * // - "Sacramento" cell (purple text)
 * // - Hover tooltip: "Source: Wikipedia: California | Confidence: high | Freshness: current"
 * ```
 *
 * @example
 * ```tsx
 * // Query result with calculated column
 * const calculatedResult: QueryResult = {
 *   columns: [
 *     { name: "state", type: "STRING" },
 *     { name: "population", type: "INTEGER" },
 *     { name: "density", type: "FLOAT64", is_calculated: true }
 *   ],
 *   rows: [
 *     {
 *       state: "California",
 *       population: 39500000,
 *       density: {
 *         value: 251.3,
 *         expression: "population / area_sq_mi",
 *         format_type: "number",
 *         is_calculated: true,
 *         warning: null
 *       }
 *     }
 *   ],
 *   // ...
 * };
 *
 * <DataTable queryResult={calculatedResult} />
 * // Renders:
 * // - "density" header (blue, with Calculator icon)
 * // - "251.3" cell (blue, monospace font)
 * // - Hover tooltip: "Formula: population / area_sq_mi | Format: number"
 * ```
 */
export function DataTable({ queryResult }: DataTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columnHelper = createColumnHelper<Record<string, unknown>>();

  const columns = useMemo(
    () =>
      queryResult.columns.map((col) =>
        columnHelper.accessor(col.name, {
          header: ({ column }) => (
            <button
              className={`flex items-center gap-1 font-semibold ${
                col.is_enriched ? 'text-purple-700' : col.is_calculated ? 'text-blue-700' : ''
              }`}
              onClick={() => column.toggleSorting()}
            >
              {col.is_enriched && <Zap className="w-3 h-3 text-purple-500" />}
              {col.is_calculated && <Calculator className="w-3 h-3 text-blue-500" />}
              {getDisplayName(col.name)}
              <ArrowUpDown className="w-3 h-3 opacity-50" />
            </button>
          ),
          cell: (info) => {
            const value = info.getValue();

            // Handle enriched values with metadata
            if (isEnrichedValue(value)) {
              const displayValue = value.value;

              if (displayValue === null || displayValue === undefined) {
                return (
                  <span className="text-gray-400 italic flex items-center gap-1">
                    {value.warning && (
                      <AlertTriangle className="w-3 h-3 text-amber-500" />
                    )}
                    no data
                  </span>
                );
              }

              return (
                <div className="group relative">
                  <div className="flex items-center gap-1.5">
                    {value.warning && (
                      <AlertTriangle className="w-3 h-3 text-amber-500 flex-shrink-0" />
                    )}
                    <span className="text-purple-900">{String(displayValue)}</span>
                  </div>

                  {/* Tooltip with enrichment metadata */}
                  <div className="absolute z-50 hidden group-hover:block bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg min-w-48 max-w-64">
                    <div className="space-y-1">
                      {value.source && (
                        <div>
                          <span className="text-gray-400">Source:</span>{' '}
                          <span className="text-gray-100">{value.source}</span>
                        </div>
                      )}
                      {value.confidence && (
                        <div className="flex items-center gap-1">
                          <span className="text-gray-400">Confidence:</span>
                          <span className={`px-1.5 py-0.5 rounded text-xs ${confidenceColors[value.confidence]}`}>
                            {value.confidence}
                          </span>
                        </div>
                      )}
                      {value.freshness && (
                        <div className="flex items-center gap-1">
                          <span className="text-gray-400">Freshness:</span>
                          <span className={`px-1.5 py-0.5 rounded text-xs ${freshnessColors[value.freshness]}`}>
                            {value.freshness}
                          </span>
                        </div>
                      )}
                      {value.warning && (
                        <div className="text-amber-300 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          {value.warning}
                        </div>
                      )}
                    </div>
                    {/* Tooltip arrow */}
                    <div className="absolute bottom-0 left-4 transform translate-y-full">
                      <div className="border-8 border-transparent border-t-gray-900" />
                    </div>
                  </div>
                </div>
              );
            }

            // Handle calculated values
            if (isCalculatedValue(value)) {
              const displayValue = formatCalculatedValue(value.value, value.format_type);

              return (
                <div className="group relative">
                  <div className="flex items-center gap-1.5">
                    {value.warning && (
                      <AlertTriangle className="w-3 h-3 text-amber-500 flex-shrink-0" />
                    )}
                    <span className="text-blue-900 font-mono">{displayValue}</span>
                  </div>

                  {/* Tooltip with calculation info */}
                  <div className="absolute z-50 hidden group-hover:block bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg min-w-48 max-w-64">
                    <div className="space-y-1">
                      <div>
                        <span className="text-gray-400">Formula:</span>{' '}
                        <code className="text-blue-300 bg-gray-800 px-1 rounded">{value.expression}</code>
                      </div>
                      <div>
                        <span className="text-gray-400">Format:</span>{' '}
                        <span className="text-gray-100">{value.format_type}</span>
                      </div>
                      {value.warning && (
                        <div className="text-amber-300 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          {value.warning}
                        </div>
                      )}
                    </div>
                    <div className="absolute bottom-0 left-4 transform translate-y-full">
                      <div className="border-8 border-transparent border-t-gray-900" />
                    </div>
                  </div>
                </div>
              );
            }

            // Handle regular values
            if (value === null || value === undefined) {
              return <span className="text-gray-400 italic">null</span>;
            }
            if (typeof value === 'number') {
              return (
                <span className="font-mono">
                  {Number.isInteger(value)
                    ? value.toLocaleString()
                    : value.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                </span>
              );
            }
            return String(value);
          },
        })
      ),
    [queryResult.columns, columnHelper]
  );

  const table = useReactTable({
    data: queryResult.rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: 10 },
    },
  });

  return (
    <div className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-gray-200">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header, index) => {
                  const colInfo = queryResult.columns[index];
                  const isEnriched = colInfo?.is_enriched;
                  const isCalculated = colInfo?.is_calculated;
                  return (
                    <th
                      key={header.id}
                      className={`px-4 py-3 text-left whitespace-nowrap ${
                        isEnriched
                          ? 'bg-purple-50 text-purple-700 border-l border-purple-200 first:border-l-0'
                          : isCalculated
                          ? 'bg-blue-50 text-blue-700 border-l border-blue-200 first:border-l-0'
                          : 'bg-gray-50 text-gray-700'
                      }`}
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-100">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                {row.getVisibleCells().map((cell, index) => {
                  const colInfo = queryResult.columns[index];
                  const isEnriched = colInfo?.is_enriched;
                  const isCalculated = colInfo?.is_calculated;
                  return (
                    <td
                      key={cell.id}
                      className={`px-4 py-3 whitespace-nowrap ${
                        isEnriched
                          ? 'bg-purple-50/50 border-l border-purple-100 first:border-l-0'
                          : isCalculated
                          ? 'bg-blue-50/50 border-l border-blue-100 first:border-l-0'
                          : ''
                      }`}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
        <div className="text-sm text-gray-600">
          Showing {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1}-
          {Math.min(
            (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
            queryResult.total_rows
          )}{' '}
          of {queryResult.total_rows} rows
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="p-2 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-gray-600">
            Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
          </span>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="p-2 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
