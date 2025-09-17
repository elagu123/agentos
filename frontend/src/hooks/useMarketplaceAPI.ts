import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import {
  WorkflowTemplate,
  WorkflowDefinition,
} from '../types/workflow';

const API_BASE = '/api/v1/marketplace';

// API client configuration
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Marketplace API functions
export const marketplaceAPI = {
  // Templates
  searchTemplates: (params: {
    query?: string;
    category?: string;
    tags?: string[];
    min_rating?: number;
    is_featured?: boolean;
    is_certified?: boolean;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.get('/templates', { params }),

  getTemplate: (templateId: string) =>
    apiClient.get(`/templates/${templateId}`),

  createTemplate: (data: {
    name: string;
    description: string;
    category: string;
    tags: string[];
    workflow_definition: WorkflowDefinition;
    version?: string;
    visibility?: string;
    changelog?: string;
    preview_image_url?: string;
    search_keywords?: string[];
  }) => apiClient.post('/templates', data),

  updateTemplate: (templateId: string, data: any) =>
    apiClient.patch(`/templates/${templateId}`, data),

  deleteTemplate: (templateId: string) =>
    apiClient.delete(`/templates/${templateId}`),

  // Ratings and Reviews
  getTemplateRatings: (templateId: string) =>
    apiClient.get(`/templates/${templateId}/ratings`),

  createRating: (templateId: string, data: {
    rating: number;
    review_title?: string;
    review_text?: string;
    use_case?: string;
    industry?: string;
    team_size?: string;
  }) => apiClient.post(`/templates/${templateId}/ratings`, data),

  // Installation
  installTemplate: (templateId: string, data: {
    customization_data?: Record<string, any>;
    installation_type?: string;
  }) => apiClient.post(`/templates/${templateId}/install`, data),

  // Reporting
  reportTemplate: (templateId: string, data: {
    reason: string;
    description: string;
    evidence_urls?: string[];
  }) => apiClient.post(`/templates/${templateId}/report`, data),

  // Categories and Stats
  getCategories: () => apiClient.get('/categories'),

  getMarketplaceStats: () => apiClient.get('/stats'),

  // User templates
  getUserTemplates: (userId?: string) =>
    apiClient.get('/templates', {
      params: { author_id: userId },
    }),

  // Analytics and Recommendations
  getMarketplaceAnalytics: (timeRange: string = '30d') =>
    apiClient.get('/analytics', { params: { time_range: timeRange } }),

  getRecommendations: (params: {
    user_id?: string;
    template_id?: string;
    type?: 'personalized' | 'trending' | 'similar' | 'collaborative';
    context?: string;
  }) => apiClient.get('/recommendations', { params }),

  getUserProfile: (userId: string) =>
    apiClient.get(`/users/${userId}/profile`),

  // Moderation
  getModerationReports: (status?: string) =>
    apiClient.get('/moderation/reports', { params: { status } }),

  getPendingTemplates: () =>
    apiClient.get('/moderation/pending'),

  handleReportAction: (reportId: string, action: string) =>
    apiClient.post(`/moderation/reports/${reportId}/action`, { action }),

  handleTemplateAction: (templateId: string, action: string) =>
    apiClient.post(`/moderation/templates/${templateId}/action`, { action }),
};

// React Query hooks

// Templates
export const useTemplates = (params?: {
  query?: string;
  category?: string;
  tags?: string[];
  min_rating?: number;
  is_featured?: boolean;
  is_certified?: boolean;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}) => {
  return useQuery({
    queryKey: ['marketplace-templates', params],
    queryFn: () => marketplaceAPI.searchTemplates(params || {}).then(res => res.data),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

export const useTemplate = (templateId: string) => {
  return useQuery({
    queryKey: ['marketplace-template', templateId],
    queryFn: () => marketplaceAPI.getTemplate(templateId).then(res => res.data),
    enabled: !!templateId,
  });
};

export const useCreateTemplate = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: marketplaceAPI.createTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-templates'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-categories'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-stats'] });
    },
  });
};

export const useUpdateTemplate = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ templateId, data }: { templateId: string; data: any }) =>
      marketplaceAPI.updateTemplate(templateId, data),
    onSuccess: (_, { templateId }) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-template', templateId] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-templates'] });
    },
  });
};

export const useDeleteTemplate = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: marketplaceAPI.deleteTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-templates'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-stats'] });
    },
  });
};

// Ratings and Reviews
export const useTemplateRatings = (templateId: string) => {
  return useQuery({
    queryKey: ['marketplace-template-ratings', templateId],
    queryFn: () => marketplaceAPI.getTemplateRatings(templateId).then(res => res.data),
    enabled: !!templateId,
  });
};

export const useCreateRating = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ templateId, ...data }: { templateId: string; [key: string]: any }) =>
      marketplaceAPI.createRating(templateId, data),
    onSuccess: (_, { templateId }) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-template-ratings', templateId] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-template', templateId] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-templates'] });
    },
  });
};

// Installation
export const useInstallTemplate = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ templateId, ...data }: { templateId: string; [key: string]: any }) =>
      marketplaceAPI.installTemplate(templateId, data),
    onSuccess: (_, { templateId }) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-template', templateId] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-templates'] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] }); // Invalidate user workflows
    },
  });
};

// Reporting
export const useReportTemplate = () => {
  return useMutation({
    mutationFn: ({ templateId, ...data }: { templateId: string; [key: string]: any }) =>
      marketplaceAPI.reportTemplate(templateId, data),
  });
};

// Categories and Stats
export const useTemplateCategories = () => {
  return useQuery({
    queryKey: ['marketplace-categories'],
    queryFn: () => marketplaceAPI.getCategories().then(res => res.data),
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
};

export const useMarketplaceStats = () => {
  return useQuery({
    queryKey: ['marketplace-stats'],
    queryFn: () => marketplaceAPI.getMarketplaceStats().then(res => res.data),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

// User Templates
export const useUserTemplates = (userId?: string) => {
  return useQuery({
    queryKey: ['marketplace-user-templates', userId],
    queryFn: () => marketplaceAPI.getUserTemplates(userId).then(res => res.data),
    enabled: !!userId,
  });
};

// Advanced search with debouncing
export const useTemplateSearch = (
  searchQuery: string,
  filters: Record<string, any> = {},
  debounceMs: number = 300
) => {
  const [debouncedQuery, setDebouncedQuery] = React.useState(searchQuery);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [searchQuery, debounceMs]);

  return useTemplates({
    query: debouncedQuery,
    ...filters,
  });
};

// Marketplace analytics (if user has access)
export const useTemplateAnalytics = (templateId: string) => {
  return useQuery({
    queryKey: ['marketplace-template-analytics', templateId],
    queryFn: () => apiClient.get(`/templates/${templateId}/analytics`).then(res => res.data),
    enabled: !!templateId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Bulk operations
export const useBulkInstallTemplates = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (templateIds: string[]) =>
      Promise.all(
        templateIds.map(id =>
          marketplaceAPI.installTemplate(id, { installation_type: 'standard' })
        )
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-templates'] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
};

// Template collections (if implemented)
export const useTemplateCollections = () => {
  return useQuery({
    queryKey: ['marketplace-collections'],
    queryFn: () => apiClient.get('/collections').then(res => res.data),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};

export const useCreateTemplateCollection = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      name: string;
      description: string;
      template_ids: string[];
    }) => apiClient.post('/collections', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-collections'] });
    },
  });
};

// Analytics and Recommendations
export const useMarketplaceAnalytics = (timeRange: string = '30d') => {
  return useQuery({
    queryKey: ['marketplace-analytics-overview', timeRange],
    queryFn: () => marketplaceAPI.getMarketplaceAnalytics(timeRange).then(res => res.data),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useRecommendations = (params: {
  user_id?: string;
  template_id?: string;
  type?: 'personalized' | 'trending' | 'similar' | 'collaborative';
  context?: string;
}) => {
  return useQuery({
    queryKey: ['marketplace-recommendations', params],
    queryFn: () => marketplaceAPI.getRecommendations(params).then(res => res.data),
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: !!(params.user_id || params.template_id),
  });
};

export const useUserProfile = (userId: string) => {
  return useQuery({
    queryKey: ['user-profile', userId],
    queryFn: () => marketplaceAPI.getUserProfile(userId).then(res => res.data),
    enabled: !!userId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};

// Moderation hooks
export const useModerationReports = (status?: string) => {
  return useQuery({
    queryKey: ['moderation-reports', status],
    queryFn: () => marketplaceAPI.getModerationReports(status).then(res => res.data),
    staleTime: 1 * 60 * 1000, // 1 minute
  });
};

export const usePendingTemplates = () => {
  return useQuery({
    queryKey: ['moderation-pending'],
    queryFn: () => marketplaceAPI.getPendingTemplates().then(res => res.data),
    staleTime: 1 * 60 * 1000, // 1 minute
  });
};

export const useHandleReportAction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ reportId, action }: { reportId: string; action: string }) =>
      marketplaceAPI.handleReportAction(reportId, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-reports'] });
    },
  });
};

export const useHandleTemplateAction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ templateId, action }: { templateId: string; action: string }) =>
      marketplaceAPI.handleTemplateAction(templateId, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-pending'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace-templates'] });
    },
  });
};