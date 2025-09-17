import { Node, Edge } from '@xyflow/react';

// Core workflow types matching backend schema
export interface WorkflowVariable {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  default_value?: any;
  description?: string;
  required?: boolean;
}

export interface StepConfig {
  agent_type?: string;
  task?: string;
  data?: Record<string, any>;
  context?: Record<string, any>;
  capabilities?: string[];
  condition?: {
    variable: string;
    operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains' | 'not_contains';
    value: any;
  };
  loop_config?: {
    iterable_variable: string;
    max_iterations?: number;
  };
  parallel_steps?: string[];
  webhook_url?: string;
  webhook_method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  delay_seconds?: number;
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: 'agent_task' | 'conditional' | 'loop' | 'parallel' | 'webhook' | 'delay' | 'user_input' | 'data_transformation';
  config: StepConfig;
  position: { x: number; y: number };
  dependencies?: string[];
  retry_config?: {
    max_retries: number;
    retry_delay: number;
    backoff_multiplier: number;
  };
}

export interface StepConnection {
  from_step: string;
  to_step: string;
  condition?: {
    variable: string;
    operator: string;
    value: any;
  };
}

export interface WorkflowDefinition {
  id?: string;
  name: string;
  description?: string;
  version: string;
  input_variables: WorkflowVariable[];
  output_variables: WorkflowVariable[];
  steps: WorkflowStep[];
  connections: StepConnection[];
  start_step: string;
  end_steps: string[];
  timeout_seconds?: number;
  retry_policy?: {
    max_retries: number;
    retry_delay: number;
  };
  metadata?: Record<string, any>;
}

// Visual workflow types for React Flow
export interface WorkflowNode extends Node {
  data: {
    step: WorkflowStep;
    isValid: boolean;
    validationErrors: string[];
    isExecuting?: boolean;
    executionResult?: any;
    executionError?: string;
  };
}

export interface WorkflowEdge extends Edge {
  data?: {
    connection: StepConnection;
    isValid: boolean;
  };
}

// Execution types
export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  input_variables: Record<string, any>;
  output_variables?: Record<string, any>;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  step_executions: StepExecution[];
}

export interface StepExecution {
  step_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  started_at?: string;
  completed_at?: string;
  input_data?: any;
  output_data?: any;
  error_message?: string;
  retry_count: number;
}

// Template types
export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  workflow_definition: WorkflowDefinition;
  variables: WorkflowVariable[];
  preview_image?: string;
  author: string;
  rating: number;
  downloads: number;
  created_at: string;
  updated_at: string;
}

// Validation types
export interface ValidationError {
  type: 'error' | 'warning';
  message: string;
  step_id?: string;
  connection_id?: string;
}

export interface WorkflowValidationResult {
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  execution_graph?: {
    levels: string[][];
    critical_path: string[];
    estimated_duration: number;
  };
}

// Agent types
export interface AgentCapability {
  name: string;
  description: string;
  input_schema: Record<string, any>;
  output_schema: Record<string, any>;
}

export interface AgentType {
  id: string;
  name: string;
  description: string;
  capabilities: AgentCapability[];
  icon: string;
  color: string;
  category: string;
}

// Event types for real-time updates
export interface StepExecutionEvent {
  execution_id: string;
  step_id: string;
  event_type: 'step_started' | 'step_completed' | 'step_failed' | 'step_output' | 'workflow_completed' | 'workflow_failed';
  timestamp: string;
  data?: any;
  error?: string;
}