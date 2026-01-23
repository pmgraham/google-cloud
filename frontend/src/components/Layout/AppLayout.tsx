import { ReactNode } from 'react';
import { Header } from './Header';

/**
 * Props for the AppLayout component.
 *
 * @remarks
 * Defines the content and event handlers for the top-level application layout.
 */
interface AppLayoutProps {
  /** Main application content (typically ChatPanel and ResultsPanel) */
  children: ReactNode;
  /** Optional callback invoked when user clicks "New Chat" button in header */
  onNewChat?: () => void;
}

/**
 * Top-level application layout component with header and main content area.
 *
 * @param props - Component props
 * @returns Full-screen layout with fixed header and flexible content area
 *
 * @remarks
 * **Root layout component** that provides the structural framework for the application.
 *
 * **Structure**:
 * - Header: Fixed at top (contains app branding and "New Chat" button)
 * - Main: Flexible content area below header (overflow hidden for child panels to manage scrolling)
 * - Layout: Flexbox column filling full viewport height
 *
 * **Overflow Handling**:
 * - Main area has `overflow-hidden` to delegate scroll management to child components
 * - Prevents double scrollbars when child panels have their own scroll areas
 * - Children should handle their own overflow (e.g., ChatPanel, ResultsPanel)
 *
 * **State Management**:
 * Stateless component - only passes `onNewChat` event handler to Header.
 *
 * **Visual Design**:
 * - Background: Light gray (`bg-gray-50`)
 * - Full viewport height (`h-screen`)
 * - No padding or margins (children define their own spacing)
 *
 * @example
 * ```tsx
 * import { AppLayout } from './components/Layout/AppLayout';
 * import { ChatPanel } from './components/Chat/ChatPanel';
 *
 * function App() {
 *   const handleNewChat = () => {
 *     // Reset chat state
 *     setMessages([]);
 *     setSessionId(generateNewSessionId());
 *   };
 *
 *   return (
 *     <AppLayout onNewChat={handleNewChat}>
 *       <div className="flex h-full">
 *         <div className="flex-1">
 *           <ChatPanel {...chatProps} />
 *         </div>
 *         {selectedMessage && (
 *           <ResultsPanel {...resultsProps} />
 *         )}
 *       </div>
 *     </AppLayout>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Minimal usage without new chat functionality
 * <AppLayout>
 *   <MainContent />
 * </AppLayout>
 * ```
 */
export function AppLayout({ children, onNewChat }: AppLayoutProps) {
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <Header onNewChat={onNewChat} />
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
    </div>
  );
}
