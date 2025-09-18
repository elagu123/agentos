/**
 * Optimized WebSocket hook for real-time communication in AgentOS.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Connection state management
 * - Message queuing for disconnected states
 * - Channel subscription management
 * - Performance monitoring
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { performanceMonitor } from '../utils/performance';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

interface WebSocketOptions {
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  channels?: string[];
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error';
  sendMessage: (message: WebSocketMessage) => void;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  reconnect: () => void;
  disconnect: () => void;
  lastMessage: WebSocketMessage | null;
  messageHistory: WebSocketMessage[];
}

const WEBSOCKET_URL = process.env.NODE_ENV === 'production'
  ? `wss://${window.location.host}/api/v1/ws`
  : 'ws://localhost:8000/api/v1/ws';

export function useWebSocket(
  userId: string,
  options: WebSocketOptions = {}
): UseWebSocketReturn {
  const {
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    channels = [],
    onMessage,
    onConnect,
    onDisconnect,
    onError
  } = options;

  const { getToken } = useAuth();
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [messageHistory, setMessageHistory] = useState<WebSocketMessage[]>([]);

  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const messageQueueRef = useRef<WebSocketMessage[]>([]);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const pingIntervalRef = useRef<NodeJS.Timeout>();

  // Clear reconnect timeout
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = undefined;
    }
  }, []);

  // Clear ping interval
  const clearPingInterval = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = undefined;
    }
  }, []);

  // Send message
  const sendMessage = useCallback((message: WebSocketMessage) => {
    const endPerformanceMonitoring = performanceMonitor.mark('websocket_send');

    try {
      if (websocketRef.current?.readyState === WebSocket.OPEN) {
        websocketRef.current.send(JSON.stringify(message));
        endPerformanceMonitoring();
      } else {
        // Queue message for when connection is restored
        messageQueueRef.current.push(message);
        console.warn('WebSocket not connected, message queued');
      }
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      endPerformanceMonitoring();
    }
  }, []);

  // Send queued messages
  const sendQueuedMessages = useCallback(() => {
    if (messageQueueRef.current.length > 0 && websocketRef.current?.readyState === WebSocket.OPEN) {
      console.log(`Sending ${messageQueueRef.current.length} queued messages`);

      messageQueueRef.current.forEach(message => {
        try {
          websocketRef.current!.send(JSON.stringify(message));
        } catch (error) {
          console.error('Failed to send queued message:', error);
        }
      });

      messageQueueRef.current = [];
    }
  }, []);

  // Start ping interval
  const startPingInterval = useCallback(() => {
    clearPingInterval();

    pingIntervalRef.current = setInterval(() => {
      if (websocketRef.current?.readyState === WebSocket.OPEN) {
        sendMessage({
          type: 'ping',
          timestamp: Date.now()
        });
      }
    }, 30000); // Ping every 30 seconds
  }, [sendMessage, clearPingInterval]);

  // Connect to WebSocket
  const connect = useCallback(async () => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      setConnectionState('connecting');

      const token = await getToken();
      if (!token) {
        throw new Error('No authentication token available');
      }

      const channelParams = channels.length > 0 ? `&channels=${channels.join(',')}` : '';
      const wsUrl = `${WEBSOCKET_URL}/${userId}?token=${token}${channelParams}`;

      const endPerformanceMonitoring = performanceMonitor.mark('websocket_connect');

      websocketRef.current = new WebSocket(wsUrl);

      websocketRef.current.onopen = () => {
        console.log('WebSocket connected');
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;
        clearReconnectTimeout();

        // Send queued messages
        sendQueuedMessages();

        // Start ping interval
        startPingInterval();

        endPerformanceMonitoring();
        onConnect?.();
      };

      websocketRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          setLastMessage(message);
          setMessageHistory(prev => [...prev.slice(-99), message]); // Keep last 100 messages

          // Handle system messages
          if (message.type === 'pong') {
            // Pong received, connection is healthy
            return;
          }

          onMessage?.(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      websocketRef.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setConnectionState('disconnected');
        clearPingInterval();
        endPerformanceMonitoring();

        onDisconnect?.();

        // Attempt reconnection if not a normal closure
        if (event.code !== 1000 && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(reconnectInterval * Math.pow(2, reconnectAttemptsRef.current), 30000);
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('Max reconnection attempts reached');
          setConnectionState('error');
        }
      };

      websocketRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionState('error');
        endPerformanceMonitoring();
        onError?.(error);
      };

    } catch (error) {
      console.error('Failed to establish WebSocket connection:', error);
      setConnectionState('error');
    }
  }, [
    userId,
    channels,
    getToken,
    reconnectInterval,
    maxReconnectAttempts,
    onConnect,
    onDisconnect,
    onError,
    onMessage,
    sendQueuedMessages,
    startPingInterval,
    clearReconnectTimeout,
    clearPingInterval
  ]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    clearPingInterval();

    if (websocketRef.current) {
      websocketRef.current.close(1000, 'Normal closure');
      websocketRef.current = null;
    }

    setConnectionState('disconnected');
  }, [clearReconnectTimeout, clearPingInterval]);

  // Reconnect WebSocket
  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      reconnectAttemptsRef.current = 0;
      connect();
    }, 1000);
  }, [disconnect, connect]);

  // Subscribe to channel
  const subscribe = useCallback((channel: string) => {
    sendMessage({
      type: 'subscribe',
      channel
    });
  }, [sendMessage]);

  // Unsubscribe from channel
  const unsubscribe = useCallback((channel: string) => {
    sendMessage({
      type: 'unsubscribe',
      channel
    });
  }, [sendMessage]);

  // Auto-connect effect
  useEffect(() => {
    if (autoConnect && userId) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [autoConnect, userId, connect, disconnect]);

  // Handle page visibility for connection management
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && connectionState === 'disconnected') {
        // Page became visible and we're disconnected, try to reconnect
        setTimeout(() => {
          if (connectionState === 'disconnected') {
            reconnect();
          }
        }, 1000);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [connectionState, reconnect]);

  return {
    connectionState,
    sendMessage,
    subscribe,
    unsubscribe,
    reconnect,
    disconnect,
    lastMessage,
    messageHistory
  };
}

// Hook for common WebSocket patterns
export function useAgentWebSocket(userId: string, organizationId: string) {
  const defaultChannels = [
    `user:${userId}`,
    `org:${organizationId}`,
    'system'
  ];

  return useWebSocket(userId, {
    channels: defaultChannels,
    autoConnect: true
  });
}

// Hook for workflow updates
export function useWorkflowWebSocket(userId: string, workflowId: string) {
  const channels = [
    `user:${userId}`,
    `workflow:${workflowId}`
  ];

  return useWebSocket(userId, {
    channels,
    autoConnect: true
  });
}

// Hook for chat updates
export function useChatWebSocket(userId: string, conversationId: string) {
  const channels = [
    `user:${userId}`,
    `chat:${conversationId}`
  ];

  return useWebSocket(userId, {
    channels,
    autoConnect: true
  });
}