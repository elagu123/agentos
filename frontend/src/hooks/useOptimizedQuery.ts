/**
 * Optimized React Query hooks for better performance
 */
import { useQuery, useMutation, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import axios, { AxiosError } from 'axios';
import { requestDeduplicator, performanceMonitor } from '../utils/performance';

// =============================================================================
// AXIOS CONFIGURATION
// =============================================================================

// Create optimized axios instance
const apiClient = axios.create({
  timeout: 10000, // 10 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for authentication
apiClient.interceptors.request.use(async (config) => {
  const { getToken } = useAuth();
  const token = await getToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Log error for monitoring
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// =============================================================================
// OPTIMIZED QUERY HOOK
// =============================================================================

interface OptimizedQueryOptions<T> extends Omit<UseQueryOptions<T>, 'queryKey' | 'queryFn'> {
  dedupe?: boolean;
  dedupeTime?: number;
  enablePerformanceMonitoring?: boolean;
}

export function useOptimizedQuery<T>(
  key: (string | number)[],
  fetcher: () => Promise<T>,
  options: OptimizedQueryOptions<T> = {}
) {
  const {
    dedupe = true,
    dedupeTime = 5000,
    enablePerformanceMonitoring = true,
    staleTime = 1000 * 60 * 5, // 5 minutes
    cacheTime = 1000 * 60 * 10, // 10 minutes
    retry = (failureCount, error) => {
      // Don't retry on 4xx errors (client errors)
      if (error instanceof AxiosError && error.response?.status && error.response.status >= 400 && error.response.status < 500) {
        return false;
      }
      return failureCount < 3;
    },
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
    ...restOptions
  } = options;

  const queryKey = key.map(String);
  const cacheKey = queryKey.join(':');

  return useQuery({
    queryKey,
    queryFn: async () => {
      let endPerformanceMonitoring: (() => void) | undefined;

      if (enablePerformanceMonitoring) {
        endPerformanceMonitoring = performanceMonitor.mark(`api_${cacheKey}`);
      }

      try {
        if (dedupe) {
          return await requestDeduplicator.dedupe(
            cacheKey,
            fetcher,
            { ttl: dedupeTime }
          );
        } else {
          return await fetcher();
        }
      } finally {
        if (endPerformanceMonitoring) {
          endPerformanceMonitoring();
        }
      }
    },
    staleTime,
    cacheTime,
    retry,
    retryDelay,
    ...restOptions,
  });
}

// =============================================================================
// SPECIFIC API HOOKS
// =============================================================================

/**
 * Hook for fetching user dashboard data
 */
export function useDashboardData() {
  return useOptimizedQuery(
    ['dashboard'],
    async () => {
      const response = await apiClient.get('/api/v1/dashboard');
      return response.data;
    },
    {
      staleTime: 1000 * 60 * 2, // 2 minutes
      refetchOnWindowFocus: true,
    }
  );
}

/**
 * Hook for fetching workflows
 */
export function useWorkflows(filters?: { status?: string; limit?: number }) {
  return useOptimizedQuery(
    ['workflows', filters],
    async () => {
      const params = new URLSearchParams();
      if (filters?.status) params.append('status', filters.status);
      if (filters?.limit) params.append('limit', filters.limit.toString());

      const response = await apiClient.get(`/api/v1/workflows?${params}`);
      return response.data;
    },
    {
      staleTime: 1000 * 30, // 30 seconds
    }
  );
}

/**
 * Hook for fetching agents
 */
export function useAgents() {
  return useOptimizedQuery(
    ['agents'],
    async () => {
      const response = await apiClient.get('/api/v1/agents');
      return response.data;
    },
    {
      staleTime: 1000 * 60 * 5, // 5 minutes (agents don't change often)
    }
  );
}

/**
 * Hook for fetching chat history
 */
export function useChatHistory(conversationId: string, enabled = true) {
  return useOptimizedQuery(
    ['chat', 'history', conversationId],
    async () => {
      const response = await apiClient.get(`/api/v1/agents/principal/conversation/${conversationId}`);
      return response.data;
    },
    {
      enabled,
      staleTime: 1000 * 60, // 1 minute
      refetchInterval: 30000, // Refetch every 30 seconds for active chats
    }
  );
}

/**
 * Hook for fetching analytics data
 */
export function useAnalytics(timeRange = '30d') {
  return useOptimizedQuery(
    ['analytics', timeRange],
    async () => {
      const response = await apiClient.get(`/api/v1/analytics?range=${timeRange}`);
      return response.data;
    },
    {
      staleTime: 1000 * 60 * 5, // 5 minutes
    }
  );
}

/**
 * Hook for fetching organization data
 */
export function useOrganization() {
  return useOptimizedQuery(
    ['organization'],
    async () => {
      const response = await apiClient.get('/api/v1/auth/me');
      return response.data.organization;
    },
    {
      staleTime: 1000 * 60 * 30, // 30 minutes (organization data rarely changes)
    }
  );
}

// =============================================================================
// OPTIMIZED MUTATION HOOK
// =============================================================================

interface OptimizedMutationOptions<TData, TError, TVariables>
  extends Omit<UseMutationOptions<TData, TError, TVariables>, 'mutationFn'> {
  enablePerformanceMonitoring?: boolean;
}

export function useOptimizedMutation<TData, TError = AxiosError, TVariables = unknown>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options: OptimizedMutationOptions<TData, TError, TVariables> = {}
) {
  const { enablePerformanceMonitoring = true, ...restOptions } = options;

  return useMutation({
    mutationFn: async (variables: TVariables) => {
      let endPerformanceMonitoring: (() => void) | undefined;

      if (enablePerformanceMonitoring) {
        endPerformanceMonitoring = performanceMonitor.mark('mutation');
      }

      try {
        return await mutationFn(variables);
      } finally {
        if (endPerformanceMonitoring) {
          endPerformanceMonitoring();
        }
      }
    },
    ...restOptions,
  });
}

// =============================================================================
// MUTATION HOOKS FOR COMMON OPERATIONS
// =============================================================================

/**
 * Hook for sending chat messages
 */
export function useSendMessage() {
  return useOptimizedMutation(
    async (data: { message: string; conversationId?: string }) => {
      const response = await apiClient.post('/api/v1/agents/principal/chat', data);
      return response.data;
    },
    {
      onSuccess: () => {
        // Invalidate chat history on successful message
        // This will be handled by React Query's cache invalidation
      },
    }
  );
}

/**
 * Hook for creating workflows
 */
export function useCreateWorkflow() {
  return useOptimizedMutation(
    async (workflowData: any) => {
      const response = await apiClient.post('/api/v1/workflows', workflowData);
      return response.data;
    }
  );
}

/**
 * Hook for executing workflows
 */
export function useExecuteWorkflow() {
  return useOptimizedMutation(
    async (data: { workflowId: string; variables?: any }) => {
      const response = await apiClient.post('/api/v1/orchestration/execute', data);
      return response.data;
    }
  );
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Prefetch data for improved user experience
 */
export function prefetchDashboardData() {
  // This can be called when user navigates to a page that will need dashboard data
  requestDeduplicator.dedupe(
    'dashboard',
    async () => {
      const response = await apiClient.get('/api/v1/dashboard');
      return response.data;
    },
    { ttl: 1000 * 60 * 2 } // 2 minutes
  );
}

/**
 * Clear cache for specific keys
 */
export function clearCache(pattern?: string) {
  if (pattern) {
    requestDeduplicator.clearCache(pattern);
  } else {
    requestDeduplicator.clearCache();
  }
}

/**
 * Get performance statistics
 */
export function getPerformanceStats() {
  return {
    apiCalls: performanceMonitor.getAllStats(),
    cache: requestDeduplicator.getCacheStats(),
  };
}