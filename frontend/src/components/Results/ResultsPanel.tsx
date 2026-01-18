import { useState } from 'react';
import { X, Download, Maximize2 } from 'lucide-react';
import type { ChatMessage, ChartType } from '../../types';
import { DataTable } from './DataTable';
import { ChartView } from './ChartView';
import { ChartToggle } from './ChartToggle';
import { SqlViewer } from './SqlViewer';

interface ResultsPanelProps {
  message: ChatMessage | null;
  onClose: () => void;
}

export function ResultsPanel({ message, onClose }: ResultsPanelProps) {
  const [chartType, setChartType] = useState<ChartType>('table');

  if (!message || !message.query_result) {
    return null;
  }

  const { query_result } = message;

  const handleExportCSV = () => {
    // Generate CSV content
    const headers = query_result.columns.map((col) => col.name).join(',');
    const rows = query_result.rows
      .map((row) =>
        query_result.columns
          .map((col) => {
            const value = row[col.name];
            if (value === null || value === undefined) return '';
            if (typeof value === 'string' && value.includes(',')) {
              return `"${value.replace(/"/g, '""')}"`;
            }
            return String(value);
          })
          .join(',')
      )
      .join('\n');

    const csv = `${headers}\n${rows}`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `query_results_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 className="font-semibold text-gray-900">Query Results</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            title="Export as CSV"
          >
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Export</span>
          </button>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Chart Type Toggle */}
        <div className="flex items-center justify-between">
          <ChartToggle activeChart={chartType} onChange={setChartType} />
          <span className="text-sm text-gray-500">
            {query_result.total_rows} rows in {query_result.query_time_ms.toFixed(0)}ms
          </span>
        </div>

        {/* Data Visualization */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          {chartType === 'table' ? (
            <DataTable queryResult={query_result} />
          ) : (
            <div className="p-4">
              <ChartView queryResult={query_result} chartType={chartType} />
            </div>
          )}
        </div>

        {/* SQL Query */}
        <SqlViewer sql={query_result.sql} queryTimeMs={query_result.query_time_ms} />
      </div>
    </div>
  );
}
