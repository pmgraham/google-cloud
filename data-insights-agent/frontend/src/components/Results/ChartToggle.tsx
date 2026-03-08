import { Table, BarChart3, LineChart, PieChart, AreaChart } from 'lucide-react';
import type { ChartType } from '../../types';

interface ChartToggleProps {
  activeChart: ChartType;
  onChange: (type: ChartType) => void;
}

const chartOptions: { type: ChartType; icon: typeof Table; label: string }[] = [
  { type: 'table', icon: Table, label: 'Table' },
  { type: 'bar', icon: BarChart3, label: 'Bar' },
  { type: 'line', icon: LineChart, label: 'Line' },
  { type: 'area', icon: AreaChart, label: 'Area' },
  { type: 'pie', icon: PieChart, label: 'Pie' },
];

export function ChartToggle({ activeChart, onChange }: ChartToggleProps) {
  return (
    <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-lg">
      {chartOptions.map(({ type, icon: Icon, label }) => (
        <button
          key={type}
          onClick={() => onChange(type)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            activeChart === type
              ? 'bg-white text-primary-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-200'
          }`}
          title={label}
        >
          <Icon className="w-4 h-4" />
          <span className="hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}
