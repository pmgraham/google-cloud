import { useCallback, useEffect, useState } from 'react';
import { GripVertical } from 'lucide-react';

/**
 * Props for the ResizeHandle component.
 *
 * @remarks
 * Defines the callback for handling resize events.
 */
interface ResizeHandleProps {
  /** Callback invoked during drag with horizontal delta in pixels (positive = dragged right, negative = dragged left) */
  onResize: (deltaX: number) => void;
}

/**
 * Draggable resize handle for adjusting panel widths.
 *
 * @param props - Component props
 * @returns Vertical resize handle with grip icon
 *
 * @remarks
 * **Interactive resize control** that allows users to adjust the width of adjacent panels
 * by dragging horizontally.
 *
 * **Features**:
 * - **Drag to resize**: Click and drag to adjust panel widths
 * - **Visual feedback**: Changes color when hovering or dragging
 * - **Cursor change**: Sets `col-resize` cursor during drag
 * - **Text selection prevention**: Disables text selection while dragging
 * - **Responsive**: Hidden on mobile (`hidden md:flex`)
 *
 * **Drag Behavior**:
 * 1. User clicks handle → `isDragging` set to true
 * 2. Mouse move events tracked → `onResize(deltaX)` called with pixel delta
 * 3. User releases mouse → `isDragging` set to false, listeners removed
 *
 * **Delta Calculation**:
 * - Computes horizontal movement between mouse events
 * - **Inverted**: `lastX - e.clientX` (dragging left increases right panel width)
 * - This inversion is intentional for results panel resize behavior
 *
 * **Event Listeners**:
 * Uses `useEffect` to attach/detach global mouse listeners during drag:
 * - `mousemove`: Calculates delta and calls `onResize()`
 * - `mouseup`: Ends drag operation
 * - Cleanup: Removes listeners and resets body styles on unmount or drag end
 *
 * **Body Style Management**:
 * During drag, sets:
 * - `userSelect: 'none'` (prevents text selection)
 * - `cursor: 'col-resize'` (shows resize cursor everywhere)
 * Restores to default on drag end.
 *
 * **Visual States**:
 * - Default: Gray background (`bg-gray-100`)
 * - Hover: Primary background (`hover:bg-primary-100`)
 * - Dragging: Stronger primary background (`bg-primary-200`)
 *
 * @example
 * ```tsx
 * import { ResizeHandle } from './components/Layout/ResizeHandle';
 *
 * function SplitView() {
 *   const [rightWidth, setRightWidth] = useState(400);
 *
 *   const handleResize = (deltaX: number) => {
 *     setRightWidth(prev => Math.max(300, Math.min(800, prev + deltaX)));
 *   };
 *
 *   return (
 *     <div className="flex h-screen">
 *       <div className="flex-1">Left panel</div>
 *       <ResizeHandle onResize={handleResize} />
 *       <div style={{ width: rightWidth }}>Right panel</div>
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // With min/max width constraints
 * const handleResize = (deltaX: number) => {
 *   setResultsPanelWidth(prev => {
 *     const newWidth = prev + deltaX;
 *     return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth));
 *   });
 * };
 *
 * <ResizeHandle onResize={handleResize} />
 * ```
 */
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
