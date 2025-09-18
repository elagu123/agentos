import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, AlertCircle } from 'lucide-react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import { useAgentChat } from '../../hooks/useAgentChat';

export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  sources?: Array<{
    type: string;
    content: string;
    source: string;
    score: number;
  }>;
  isLoading?: boolean;
  error?: string;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: "Hello! I'm your Principal Agent. I have knowledge about your business context and can help you with various tasks. How can I assist you today?",
      role: 'assistant',
      timestamp: new Date()
    }
  ]);

  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { sendMessage, isLoading } = useAgentChat({
    onMessageReceived: (response) => {
      // Remove loading message and add actual response
      setMessages(prev =>
        prev.filter(msg => !msg.isLoading).concat({
          id: Date.now().toString(),
          content: response.response,
          role: 'assistant',
          timestamp: new Date(),
          sources: response.sources
        })
      );
      setIsTyping(false);
    },
    onError: (error) => {
      setMessages(prev =>
        prev.filter(msg => !msg.isLoading).concat({
          id: Date.now().toString(),
          content: "I apologize, but I encountered an error processing your request. Please try again.",
          role: 'assistant',
          timestamp: new Date(),
          error: error.message
        })
      );
      setIsTyping(false);
    }
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      role: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);

    // Add loading message
    const loadingMessage: Message = {
      id: `loading-${Date.now()}`,
      content: '',
      role: 'assistant',
      timestamp: new Date(),
      isLoading: true
    };

    setMessages(prev => [...prev, loadingMessage]);

    // Send to backend
    try {
      await sendMessage(content);
    } catch (error) {
      console.error('Error sending message:', error);
      setIsTyping(false);
      setMessages(prev => prev.filter(msg => !msg.isLoading));
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Chat Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-10 w-10 bg-blue-500 rounded-full flex items-center justify-center">
              <Bot className="h-6 w-6 text-white" />
            </div>
          </div>
          <div className="ml-4">
            <h3 className="text-lg font-medium text-gray-900">Principal Agent</h3>
            <p className="text-sm text-gray-600">
              {isTyping ? (
                <span className="flex items-center">
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  Thinking...
                </span>
              ) : (
                'Ready to help with your business needs'
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <MessageList messages={messages} />
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-4">
        <MessageInput
          onSendMessage={handleSendMessage}
          disabled={isLoading}
          placeholder="Ask your agent anything about your business..."
        />
      </div>

      {/* Context Information */}
      <div className="px-4 pb-4">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="flex items-start">
            <AlertCircle className="h-4 w-4 text-blue-600 mt-0.5 mr-2 flex-shrink-0" />
            <div className="text-sm text-blue-800">
              <p className="font-medium">Your agent knows your business context</p>
              <p className="mt-1">
                I have access to your uploaded documents, business information, and previous conversations
                to provide personalized assistance.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}