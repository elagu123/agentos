import React from 'react';
import { Bot, User, ExternalLink, Loader2 } from 'lucide-react';
import { Message } from './ChatInterface';

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex items-start space-x-3 ${
            message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
          }`}
        >
          {/* Avatar */}
          <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
            message.role === 'user'
              ? 'bg-gray-200 text-gray-600'
              : 'bg-blue-500 text-white'
          }`}>
            {message.role === 'user' ? (
              <User className="h-4 w-4" />
            ) : (
              <Bot className="h-4 w-4" />
            )}
          </div>

          {/* Message Content */}
          <div className={`flex-1 max-w-2xl ${
            message.role === 'user' ? 'text-right' : 'text-left'
          }`}>
            <div className={`inline-block px-4 py-2 rounded-lg ${
              message.role === 'user'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-900'
            }`}>
              {message.isLoading ? (
                <div className="flex items-center space-x-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              ) : (
                <div className="whitespace-pre-wrap text-sm">
                  {message.content}
                </div>
              )}
            </div>

            {/* Timestamp */}
            <div className={`mt-1 text-xs text-gray-500 ${
              message.role === 'user' ? 'text-right' : 'text-left'
            }`}>
              {formatTime(message.timestamp)}
            </div>

            {/* Sources (only for assistant messages) */}
            {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="text-xs text-gray-600 font-medium">Sources used:</p>
                {message.sources.map((source, index) => (
                  <div
                    key={index}
                    className="bg-gray-50 border border-gray-200 rounded-md p-2 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-700">
                        {source.type} - {source.source}
                      </span>
                      <span className="text-gray-500">
                        {Math.round(source.score * 100)}% match
                      </span>
                    </div>
                    <p className="mt-1 text-gray-600">
                      {source.content}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* Error Display */}
            {message.error && (
              <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-md">
                <p className="text-xs text-red-700">
                  Error: {message.error}
                </p>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}