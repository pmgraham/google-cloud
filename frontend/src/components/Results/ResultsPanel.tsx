import { useState } from 'react';
import { X, Download, Zap, Calculator, AlertTriangle, Info } from 'lucide-react';
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
    // Helper to extract display value from enriched/calculated objects
    const getExportValue = (value: unknown): string => {
      if (value === null || value === undefined) return '';
      // Handle enriched values (have 'value' and 'source' properties)
      if (typeof value === 'object' && value !== null && 'value' in value) {
        const innerValue = (value as { value: unknown }).value;
        if (innerValue === null || innerValue === undefined) return '';
        return String(innerValue);
      }
      return String(value);
    };

    // Generate CSV content
    const headers = query_result.columns.map((col) => col.name).join(',');
    const rows = query_result.rows
      .map((row) =>
        query_result.columns
          .map((col) => {
            const value = row[col.name];
            const exportValue = getExportValue(value);
            if (exportValue === '') return '';
            if (exportValue.includes(',') || exportValue.includes('"') || exportValue.includes('\n')) {
              return `"${exportValue.replace(/"/g, '""')}"`;
            }
            return exportValue;
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

        {/* Enrichment Metadata Banner */}
        {query_result.enrichment_metadata && (
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <Zap className="w-4 h-4 text-purple-500 mt-0.5 flex-shrink-0" />
              <div className="flex-1 text-sm">
                <div className="font-medium text-purple-900 flex items-center gap-2">
                  Enriched Data
                  <span className="text-xs font-normal text-purple-600 bg-purple-100 px-2 py-0.5 rounded">
                    {query_result.enrichment_metadata.total_enriched} values enriched
                  </span>
                </div>
                <div className="text-purple-700 mt-1 flex items-center gap-1">
                  <Info className="w-3 h-3" />
                  <span>
                    Purple columns contain data from Google Search. Hover over values for source details.
                  </span>
                </div>
                {query_result.enrichment_metadata.warnings.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {query_result.enrichment_metadata.warnings.map((warning, i) => (
                      <div key={i} className="text-amber-700 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                        <span>{warning}</span>
                      </div>
                    ))}
                  </div>
                )}
                {query_result.enrichment_metadata.partial_failure && (
                  <div className="mt-2 text-amber-700 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>Some enrichment lookups failed. Missing data shown as "no data".</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Calculation Metadata Banner */}
        {query_result.calculation_metadata && query_result.calculation_metadata.calculated_columns.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <Calculator className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <div className="flex-1 text-sm">
                <div className="font-medium text-blue-900 flex items-center gap-2">
                  Calculated Columns
                  <span className="text-xs font-normal text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
                    {query_result.calculation_metadata.calculated_columns.length} column{query_result.calculation_metadata.calculated_columns.length > 1 ? 's' : ''}
                  </span>
                </div>
                <div className="text-blue-700 mt-1 flex items-center gap-1">
                  <Info className="w-3 h-3" />
                  <span>
                    Blue columns are calculated from existing data. Hover over values to see formulas.
                  </span>
                </div>
                <div className="mt-2 text-xs text-blue-600">
                  {query_result.calculation_metadata.calculated_columns.map((col, i) => (
                    <span key={col.name} className="inline-flex items-center gap-1 mr-3">
                      <code className="bg-blue-100 px-1 rounded">{col.name}</code>
                      <span className="text-blue-400">=</span>
                      <code className="text-blue-800">{col.expression}</code>
                    </span>
                  ))}
                </div>
                {query_result.calculation_metadata.warnings.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {query_result.calculation_metadata.warnings.map((warning, i) => (
                      <div key={i} className="text-amber-700 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                        <span>{warning}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

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
