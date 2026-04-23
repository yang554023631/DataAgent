import { useEffect, useRef } from 'react';
import { useChatStore } from './stores/chatStore';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import ClarificationModal from './components/ClarificationModal';

function App() {
  const {
    sessionId,
    messages,
    isLoading,
    showClarification,
    clarification,
    initSession,
    sendMessage,
    submitClarification,
    closeClarification
  } = useChatStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    initSession();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-blue-600 shadow-md">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-white">广告报表智能助手</h1>
        </div>
      </header>

      <main className="flex-1 flex flex-col max-w-4xl mx-auto w-full">
        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-4">
          {messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}
          <div ref={messagesEndRef} />

          {isLoading && (
            <div className="flex justify-end mb-4">
              <div className="bg-blue-600 text-white rounded-lg px-4 py-2">
                思考中...
              </div>
            </div>
          )}
        </div>

        {/* Chat input */}
        <ChatInput
          onSend={sendMessage}
          disabled={isLoading || !sessionId}
        />
      </main>

      {/* Clarification Modal */}
      {showClarification && clarification && (
        <ClarificationModal
          clarification={clarification}
          onSubmit={submitClarification}
          onClose={closeClarification}
        />
      )}
    </div>
  );
}

export default App
