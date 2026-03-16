import React, { useState, useEffect } from 'react';

interface ReviewNotesEditorProps {
  initialValue?: string;
  onSave: (value: string) => void;
  rows?: number;
}

export function ReviewNotesEditor({ initialValue, onSave, rows = 3 }: ReviewNotesEditorProps) {
  const [value, setValue] = useState(initialValue || "");
  const hasChanges = value !== (initialValue || "");
  
  useEffect(() => {
    setValue(initialValue || "");
  }, [initialValue]);

  return (
    <div className="flex flex-col gap-2">
      <textarea 
        className="w-full text-sm px-3 py-2 rounded-lg border border-zinc-200 bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all resize-none shadow-sm"
        rows={rows}
        placeholder="Add notes about your decision..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      {hasChanges && (
        <div className="flex justify-end gap-2">
          <button 
            onClick={() => setValue(initialValue || "")}
            className="px-3 py-1.5 text-xs font-medium text-zinc-600 bg-zinc-50 hover:bg-zinc-100 rounded-md transition-colors border border-zinc-200"
          >
            Cancel
          </button>
          <button 
            onClick={() => {
              onSave(value);
            }}
            className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md transition-colors shadow-sm"
          >
            Save Notes
          </button>
        </div>
      )}
    </div>
  );
}
