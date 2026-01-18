import { ChevronDown, Zap, Calculator } from 'lucide-react';
import type { ColumnInfo } from '../../types';

interface MetricSelectorProps {
  columns: ColumnInfo[];
  selectedColumn: string;
  onChange: (columnName: string) => void;
  disabled?: boolean;
}

// Get display name for column (remove _enriched_ prefix)
function getDisplayName(colName: string): string {
  if (colName.startsWith('_enriched_')) {
    return colName.replace('_enriched_', '');
  }
  return colName;
}

export function MetricSelector({ columns, selectedColumn, onChange, disabled }: MetricSelectorProps) {
  const selectedCol = columns.find((c) => c.name === selectedColumn);

  return (
    <div className="relative">
      <select
        value={selectedColumn}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="appearance-none bg-white border border-gray-200 rounded-lg pl-3 pr-8 py-1.5 text-sm font-medium text-gray-700 hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {columns.map((col) => (
          <option key={col.name} value={col.name}>
            {col.is_enriched ? '⚡ ' : col.is_calculated ? '🔢 ' : ''}
            {getDisplayName(col.name)}
          </option>
        ))}
      </select>
      <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
        <ChevronDown className="w-4 h-4 text-gray-400" />
      </div>
      {selectedCol && (
        <div className="absolute -left-6 inset-y-0 flex items-center pointer-events-none">
          {selectedCol.is_enriched && <Zap className="w-4 h-4 text-purple-500" />}
          {selectedCol.is_calculated && <Calculator className="w-4 h-4 text-blue-500" />}
        </div>
      )}
    </div>
  );
}
