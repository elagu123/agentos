import React from 'react';
import { X, Settings, AlertCircle, CheckCircle } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { WorkflowStep, StepConfig } from '../../types/workflow';
import { clsx } from 'clsx';

const stepConfigSchema = z.object({
  agent_type: z.string().optional(),
  task: z.string().optional(),
  webhook_url: z.string().url().optional().or(z.literal('')),
  webhook_method: z.enum(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']).optional(),
  delay_seconds: z.number().min(1).optional(),
  condition: z.object({
    variable: z.string(),
    operator: z.enum(['equals', 'not_equals', 'greater_than', 'less_than', 'contains', 'not_contains']),
    value: z.any(),
  }).optional(),
  loop_config: z.object({
    iterable_variable: z.string(),
    max_iterations: z.number().min(1).optional(),
  }).optional(),
  parallel_steps: z.array(z.string()).optional(),
});

interface PropertiesPanelProps {
  selectedStep: WorkflowStep | null;
  onStepUpdate: (stepId: string, updates: Partial<WorkflowStep>) => void;
  onClose: () => void;
  isOpen: boolean;
  validationErrors: string[];
}

const AGENT_TYPES = [
  { value: 'copywriter', label: 'Copywriter Agent', description: 'Marketing content and copy creation' },
  { value: 'researcher', label: 'Researcher Agent', description: 'Research and competitive analysis' },
  { value: 'scheduler', label: 'Scheduler Agent', description: 'Calendar and meeting management' },
  { value: 'email_responder', label: 'Email Responder', description: 'Email processing and responses' },
  { value: 'data_analyzer', label: 'Data Analyzer', description: 'Data analysis and insights' },
];

const OPERATORS = [
  { value: 'equals', label: 'Equals' },
  { value: 'not_equals', label: 'Not Equals' },
  { value: 'greater_than', label: 'Greater Than' },
  { value: 'less_than', label: 'Less Than' },
  { value: 'contains', label: 'Contains' },
  { value: 'not_contains', label: 'Does Not Contain' },
];

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedStep,
  onStepUpdate,
  onClose,
  isOpen,
  validationErrors,
}) => {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isDirty },
    reset,
  } = useForm<{
    name: string;
    config: StepConfig;
  }>({
    resolver: zodResolver(z.object({
      name: z.string().min(1, 'Name is required'),
      config: stepConfigSchema,
    })),
  });

  React.useEffect(() => {
    if (selectedStep) {
      reset({
        name: selectedStep.name,
        config: selectedStep.config,
      });
    }
  }, [selectedStep, reset]);

  const stepType = selectedStep?.type;
  const watchedConfig = watch('config');

  const onSubmit = (data: { name: string; config: StepConfig }) => {
    if (selectedStep) {
      onStepUpdate(selectedStep.id, {
        name: data.name,
        config: data.config,
      });
    }
  };

  const renderStepTypeFields = () => {
    if (!stepType) return null;

    switch (stepType) {
      case 'agent_task':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Agent Type
              </label>
              <select
                {...register('config.agent_type')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Select an agent...</option>
                {AGENT_TYPES.map(agent => (
                  <option key={agent.value} value={agent.value}>
                    {agent.label}
                  </option>
                ))}
              </select>
              {errors.config?.agent_type && (
                <p className="mt-1 text-sm text-red-600">{errors.config.agent_type.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Task Description
              </label>
              <textarea
                {...register('config.task')}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Describe what this agent should do..."
              />
              {errors.config?.task && (
                <p className="mt-1 text-sm text-red-600">{errors.config.task.message}</p>
              )}
            </div>
          </div>
        );

      case 'conditional':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Variable Name
              </label>
              <input
                type="text"
                {...register('config.condition.variable')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Variable to check"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Operator
              </label>
              <select
                {...register('config.condition.operator')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {OPERATORS.map(op => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Value
              </label>
              <input
                type="text"
                {...register('config.condition.value')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Value to compare"
              />
            </div>
          </div>
        );

      case 'loop':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Iterable Variable
              </label>
              <input
                type="text"
                {...register('config.loop_config.iterable_variable')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Variable containing array/list"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Iterations
              </label>
              <input
                type="number"
                {...register('config.loop_config.max_iterations', { valueAsNumber: true })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Maximum number of iterations"
                min="1"
              />
            </div>
          </div>
        );

      case 'webhook':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Webhook URL
              </label>
              <input
                type="url"
                {...register('config.webhook_url')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="https://api.example.com/webhook"
              />
              {errors.config?.webhook_url && (
                <p className="mt-1 text-sm text-red-600">{errors.config.webhook_url.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                HTTP Method
              </label>
              <select
                {...register('config.webhook_method')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {HTTP_METHODS.map(method => (
                  <option key={method} value={method}>
                    {method}
                  </option>
                ))}
              </select>
            </div>
          </div>
        );

      case 'delay':
        return (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Delay (seconds)
            </label>
            <input
              type="number"
              {...register('config.delay_seconds', { valueAsNumber: true })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="60"
              min="1"
            />
            {errors.config?.delay_seconds && (
              <p className="mt-1 text-sm text-red-600">{errors.config.delay_seconds.message}</p>
            )}
          </div>
        );

      default:
        return (
          <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
            <p className="text-sm text-gray-600">
              No specific configuration needed for this step type.
            </p>
          </div>
        );
    }
  };

  if (!isOpen || !selectedStep) {
    return null;
  }

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-lg border-l border-gray-200 z-30 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <Settings className="w-5 h-5 text-gray-500" />
          <h3 className="text-lg font-semibold text-gray-900">Properties</h3>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <form onSubmit={handleSubmit(onSubmit)} className="p-4 space-y-6">
        {/* Basic Info */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Basic Information</h4>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Step Name
              </label>
              <input
                type="text"
                {...register('name')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Enter step name"
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Step Type
              </label>
              <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-md text-sm text-gray-700 capitalize">
                {selectedStep.type.replace('_', ' ')}
              </div>
            </div>
          </div>
        </div>

        {/* Step-specific Configuration */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Configuration</h4>
          {renderStepTypeFields()}
        </div>

        {/* Validation Status */}
        {validationErrors.length > 0 && (
          <div className="border border-red-200 rounded-lg p-3 bg-red-50">
            <div className="flex items-center space-x-2 mb-2">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <h5 className="text-sm font-medium text-red-800">Validation Errors</h5>
            </div>
            <ul className="space-y-1">
              {validationErrors.map((error, index) => (
                <li key={index} className="text-xs text-red-700">
                  • {error}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Save Button */}
        <div className="sticky bottom-0 bg-white pt-4 border-t border-gray-200">
          <button
            type="submit"
            disabled={!isDirty}
            className={clsx(
              'w-full px-4 py-2 rounded-md text-sm font-medium transition-colors',
              isDirty
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            )}
          >
            {isDirty ? 'Save Changes' : 'No Changes'}
          </button>
        </div>
      </form>
    </div>
  );
};