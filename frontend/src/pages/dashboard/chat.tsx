import React from 'react';
import DashboardLayout from '../../components/layout/DashboardLayout';
import ChatInterface from '../../components/chat/ChatInterface';

export default function ChatPage() {
  return (
    <DashboardLayout>
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Principal Agent Chat</h1>
          <p className="mt-1 text-sm text-gray-600">
            Chat with your AI agent that knows your business context
          </p>
        </div>

        {/* Chat Interface - takes full remaining height */}
        <div className="flex-1 min-h-0">
          <ChatInterface />
        </div>
      </div>
    </DashboardLayout>
  );
}