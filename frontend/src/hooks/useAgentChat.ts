import { useState, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import axios from 'axios';
import { performanceMonitor } from '../utils/performance';

interface AgentResponse {
  response: string;
  confidence: number;
  sources: Array<{
    type: string;
    content: string;
    source: string;
    score: number;
  }>;
  execution_time: number;
  tokens_used: number;
  cost: number;
}

interface UseAgentChatOptions {
  onMessageReceived?: (response: AgentResponse) => void;
  onError?: (error: Error) => void;
}

export function useAgentChat({ onMessageReceived, onError }: UseAgentChatOptions = {}) {
  const [isLoading, setIsLoading] = useState(false);
  const { getToken } = useAuth();

  const sendMessage = useCallback(async (message: string): Promise<AgentResponse> => {
    setIsLoading(true);
    const endPerformanceMonitoring = performanceMonitor.mark('chat_message');

    try {
      const token = await getToken();

      const response = await axios.post(
        '/api/v1/agents/principal/chat',
        {
          message,
          conversation_id: 'main', // For now, use a single conversation
          include_sources: true
        },
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          timeout: 30000 // 30 second timeout for chat
        }
      );

      const agentResponse: AgentResponse = response.data;

      if (onMessageReceived) {
        onMessageReceived(agentResponse);
      }

      return agentResponse;
    } catch (error) {
      console.error('Chat API error:', error);

      const errorMessage = axios.isAxiosError(error) && error.response?.data?.detail
        ? error.response.data.detail
        : 'Failed to send message';

      const errorObj = new Error(errorMessage);

      if (onError) {
        onError(errorObj);
      }

      throw errorObj;
    } finally {
      setIsLoading(false);
      endPerformanceMonitoring();
    }
  }, [getToken, onMessageReceived, onError]);

  return {
    sendMessage,
    isLoading
  };
}