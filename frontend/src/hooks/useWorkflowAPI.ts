import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import {
  WorkflowDefinition,
  WorkflowExecution,
  WorkflowTemplate,
  WorkflowValidationResult,
  AgentType
} from '../types/workflow';

const API_BASE = '/api/v1';

// API client configuration
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Workflow API functions
export const workflowAPI = {
  // Workflow CRUD
  createWorkflow: (workflow: Omit<WorkflowDefinition, 'id'>) =>
    apiClient.post<WorkflowDefinition>('/orchestration/workflows', workflow),

  updateWorkflow: (id: string, workflow: Partial<WorkflowDefinition>) =>
    apiClient.put<WorkflowDefinition>(`/orchestration/workflows/${id}`, workflow),

  getWorkflow: (id: string) =>
    apiClient.get<WorkflowDefinition>(`/orchestration/workflows/${id}`),

  listWorkflows: (params?: { category?: string; search?: string }) =>
    apiClient.get<WorkflowDefinition[]>('/orchestration/workflows', { params }),

  deleteWorkflow: (id: string) =>
    apiClient.delete(`/orchestration/workflows/${id}`),

  // Workflow validation
  validateWorkflow: (workflow: WorkflowDefinition) =>
    apiClient.post<WorkflowValidationResult>('/orchestration/workflows/validate', workflow),

  // Workflow execution
  executeWorkflow: (workflowId: string, inputVariables: Record<string, any>) =>
    apiClient.post<WorkflowExecution>('/orchestration/execute', {
      workflow_id: workflowId,
      input_variables: inputVariables,
    }),

  executeWorkflowSync: (workflowId: string, inputVariables: Record<string, any>) =>
    apiClient.post<WorkflowExecution>('/orchestration/execute', {
      workflow_id: workflowId,
      input_variables: inputVariables,
      execution_mode: 'sync',
    }),

  // Execution monitoring
  getExecution: (executionId: string) =>
    apiClient.get<WorkflowExecution>(`/orchestration/executions/${executionId}`),

  listExecutions: (workflowId?: string) =>
    apiClient.get<WorkflowExecution[]>('/orchestration/executions', {
      params: workflowId ? { workflow_id: workflowId } : undefined,
    }),

  cancelExecution: (executionId: string) =>
    apiClient.post(`/orchestration/executions/${executionId}/cancel`),

  // Templates
  listTemplates: (params?: { category?: string; search?: string }) =>
    apiClient.get<WorkflowTemplate[]>('/orchestration/templates', { params }),

  getTemplate: (templateId: string) =>
    apiClient.get<WorkflowTemplate>(`/orchestration/templates/${templateId}`),

  installTemplate: (templateId: string, customization?: Record<string, any>) =>
    apiClient.post<WorkflowDefinition>(`/orchestration/templates/${templateId}/install`, {
      customization,
    }),

  // Agent types
  listAgentTypes: () =>
    apiClient.get<AgentType[]>('/specialized-agents'),

  getAgentCapabilities: (agentType: string) =>
    apiClient.get(`/specialized-agents/${agentType}/capabilities`),
};

// React Query hooks
export const useWorkflows = (params?: { category?: string; search?: string }) => {
  return useQuery({
    queryKey: ['workflows', params],
    queryFn: () => workflowAPI.listWorkflows(params).then(res => res.data),
  });
};

export const useWorkflow = (id: string) => {
  return useQuery({
    queryKey: ['workflow', id],
    queryFn: () => workflowAPI.getWorkflow(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useCreateWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: workflowAPI.createWorkflow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
};

export const useUpdateWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, workflow }: { id: string; workflow: Partial<WorkflowDefinition> }) =>
      workflowAPI.updateWorkflow(id, workflow),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['workflow', id] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
};

export const useDeleteWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: workflowAPI.deleteWorkflow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
};

export const useValidateWorkflow = () => {
  return useMutation({
    mutationFn: workflowAPI.validateWorkflow,
  });
};

export const useExecuteWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ workflowId, inputVariables }: { workflowId: string; inputVariables: Record<string, any> }) =>
      workflowAPI.executeWorkflow(workflowId, inputVariables),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executions'] });
    },
  });
};

export const useExecution = (executionId: string) => {
  return useQuery({
    queryKey: ['execution', executionId],
    queryFn: () => workflowAPI.getExecution(executionId).then(res => res.data),
    enabled: !!executionId,
    refetchInterval: (data) => {
      // Auto-refresh if execution is still running
      return data?.status === 'running' || data?.status === 'pending' ? 2000 : false;
    },
  });
};

export const useExecutions = (workflowId?: string) => {
  return useQuery({
    queryKey: ['executions', workflowId],
    queryFn: () => workflowAPI.listExecutions(workflowId).then(res => res.data),
  });
};

export const useCancelExecution = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: workflowAPI.cancelExecution,
    onSuccess: (_, executionId) => {
      queryClient.invalidateQueries({ queryKey: ['execution', executionId] });
      queryClient.invalidateQueries({ queryKey: ['executions'] });
    },
  });
};

export const useTemplates = (params?: { category?: string; search?: string }) => {
  return useQuery({
    queryKey: ['templates', params],
    queryFn: () => workflowAPI.listTemplates(params).then(res => res.data),
  });
};

export const useTemplate = (templateId: string) => {
  return useQuery({
    queryKey: ['template', templateId],
    queryFn: () => workflowAPI.getTemplate(templateId).then(res => res.data),
    enabled: !!templateId,
  });
};

export const useInstallTemplate = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ templateId, customization }: { templateId: string; customization?: Record<string, any> }) =>
      workflowAPI.installTemplate(templateId, customization),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
};

export const useAgentTypes = () => {
  return useQuery({
    queryKey: ['agentTypes'],
    queryFn: () => workflowAPI.listAgentTypes().then(res => res.data),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });
};