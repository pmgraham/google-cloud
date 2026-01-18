import { useCallback, useEffect, useState } from 'react';
import { GripVertical } from 'lucide-react';

interface ResizeHandleProps {
  onResize: (deltaX: number) => void;
}

export function ResizeHandle({ onResize }: ResizeHandleProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    let lastX = 0;

    const handleMouseMove = (e: MouseEvent) => {
      if (lastX !== 0) {
        // Negative because dragging left should increase results panel width
        onResize(lastX - e.clientX);
      }
      lastX = e.clientX;
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      lastX = 0;
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    // Prevent text selection while dragging
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging, onResize]);

  return (
    <div
      onMouseDown={handleMouseDown}
      className={`
        hidden md:flex items-center justify-center w-2 cursor-col-resize
        hover:bg-primary-100 transition-colors group flex-shrink-0
        ${isDragging ? 'bg-primary-200' : 'bg-gray-100'}
      `}
      title="Drag to resize"
    >
      <GripVertical
        className={`w-4 h-4 text-gray-400 group-hover:text-primary-500 ${isDragging ? 'text-primary-600' : ''}`}
      />
    </div>
  );
}
