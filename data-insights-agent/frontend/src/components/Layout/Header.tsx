import { Database, MessageSquare, Settings } from 'lucide-react';

/**
 * Props for the Header component.
 *
 * @remarks
 * Defines optional event handlers for header actions.
 */
interface HeaderProps {
  /** Optional callback invoked when user clicks "New Chat" button */
  onNewChat?: () => void;
}

/**
 * Application header component with branding and action buttons.
 *
 * @param props - Component props
 * @returns Header bar with app branding, new chat button, and settings button
 *
 * @remarks
 * **Top navigation component** displayed at the top of every page.
 *
 * **Structure**:
 * - Left section: App branding (Database icon + title + subtitle)
 * - Right section: Action buttons (New Chat, Settings)
 *
 * **Branding**:
 * - Icon: Database icon in primary-colored circle
 * - Title: "Data Insights Agent" (large, bold)
 * - Subtitle: "Ask questions about your data in natural language" (small, muted)
 *
 * **Action Buttons**:
 * - **New Chat**: Creates a fresh conversation (calls `onNewChat` callback)
 * - **Settings**: Placeholder button (no functionality yet)
 *
 * **Visual Design**:
 * - Background: White with bottom border
 * - Padding: `px-6 py-4`
 * - Responsive: Buttons may need adjustment on mobile
 *
 * **State Management**:
 * Stateless component - only emits `onNewChat` event when button clicked.
 *
 * @example
 * ```tsx
 * import { Header } from './components/Layout/Header';
 *
 * function AppLayout({ children }: { children: ReactNode }) {
 *   const handleNewChat = () => {
 *     resetChatState();
 *     navigate('/');
 *   };
 *
 *   return (
 *     <div className="flex flex-col h-screen">
 *       <Header onNewChat={handleNewChat} />
 *       <main className="flex-1">{children}</main>
 *     </div>
 *   );
 * }
 * ```
 *
 * @example
 * ```tsx
 * // Without new chat functionality
 * <Header />
 * ```
 */
export function Header({ onNewChat }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 bg-primary-100 rounded-lg">
            <Database className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Data Insights Agent</h1>
            <p className="text-sm text-gray-500">Ask questions about your data in natural language</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onNewChat}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            New Chat
          </button>
          <button
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
