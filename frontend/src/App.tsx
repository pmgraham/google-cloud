import { useState, useEffect, useCallback } from 'react';
import type { ChatMessage } from './types';
import { useChat } from './hooks/useChat';
import { AppLayout } from './components/Layout/AppLayout';
import { ChatPanel } from './components/Chat/ChatPanel';
import { ResultsPanel } from './components/Results/ResultsPanel';
import { ResizeHandle } from './components/Layout/ResizeHandle';

// Min/max width constraints for results panel (in pixels)
const MIN_RESULTS_WIDTH = 320;
const MAX_RESULTS_WIDTH = 1200;
const DEFAULT_RESULTS_WIDTH = 600;

function App() {
  const { messages, isLoading, sendMessage, selectOption, clearChat } = useChat();
  const [selectedMessage, setSelectedMessage] = useState<ChatMessage | null>(null);
  const [resultsWidth, setResultsWidth] = useState(DEFAULT_RESULTS_WIDTH);

  const handleResize = useCallback((deltaX: number) => {
    setResultsWidth((prev) => {
      const newWidth = prev + deltaX;
      return Math.min(MAX_RESULTS_WIDTH, Math.max(MIN_RESULTS_WIDTH, newWidth));
    });
  }, []);

  // Auto-show results panel when a new message with query_result arrives
  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === 'assistant' && lastMessage.query_result) {
        setSelectedMessage(lastMessage);
      }
    }
  }, [messages]);

  const handleViewResults = (message: ChatMessage) => {
    setSelectedMessage(message);
  };

  const handleCloseResults = () => {
    setSelectedMessage(null);
  };

  const handleNewChat = () => {
    clearChat();
    setSelectedMessage(null);
  };

  return (
    <AppLayout onNewChat={handleNewChat}>
      <div className="flex h-full">
        {/* Chat Panel */}
        <div className={`flex-1 min-w-0 ${selectedMessage ? 'hidden md:flex md:flex-col' : 'flex flex-col'}`}>
          <ChatPanel
            messages={messages}
            isLoading={isLoading}
            onSendMessage={sendMessage}
            onSelectOption={selectOption}
            onViewResults={handleViewResults}
          />
        </div>

        {/* Results Panel with Resize Handle */}
        {selectedMessage && (
          <>
            <ResizeHandle onResize={handleResize} />
            <div
              className="w-full md:flex-shrink-0 h-full"
              style={{ maxWidth: '100%', width: resultsWidth }}
            >
              <ResultsPanel message={selectedMessage} onClose={handleCloseResults} />
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}

export default App;
