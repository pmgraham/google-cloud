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
import { ArrowUpDown, ChevronLeft, ChevronRight, Zap, AlertTriangle } from 'lucide-react';
import type { QueryResult, EnrichedValue } from '../../types';

interface DataTableProps {
  queryResult: QueryResult;
}

// Type guard for enriched values
function isEnrichedValue(value: unknown): value is EnrichedValue {
  return (
    typeof value === 'object' &&
    value !== null &&
    'value' in value &&
    'source' in value &&
    'confidence' in value
  );
}

// Get display name for enriched column (remove _enriched_ prefix)
function getDisplayName(colName: string): string {
  if (colName.startsWith('_enriched_')) {
    return colName.replace('_enriched_', '');
  }
  return colName;
}

// Confidence badge colors
const confidenceColors = {
  high: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-red-100 text-red-700',
};

// Freshness badge colors
const freshnessColors = {
  static: 'bg-blue-100 text-blue-700',
  current: 'bg-green-100 text-green-700',
  dated: 'bg-yellow-100 text-yellow-700',
  stale: 'bg-red-100 text-red-700',
};

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
                col.is_enriched ? 'text-purple-700' : ''
              }`}
              onClick={() => column.toggleSorting()}
            >
              {col.is_enriched && <Zap className="w-3 h-3 text-purple-500" />}
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
                  return (
                    <th
                      key={header.id}
                      className={`px-4 py-3 text-left whitespace-nowrap ${
                        isEnriched
                          ? 'bg-purple-50 text-purple-700 border-l border-purple-200 first:border-l-0'
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
                  return (
                    <td
                      key={cell.id}
                      className={`px-4 py-3 whitespace-nowrap ${
                        isEnriched
                          ? 'bg-purple-50/50 border-l border-purple-100 first:border-l-0'
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
