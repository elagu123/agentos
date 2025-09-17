import React from 'react';
import { ArrowRight, Play, Settings, Globe, Clock, Users, Database, GitBranch, RefreshCw, Zap } from 'lucide-react';
import { WorkflowDefinition } from '../../types/workflow';
import { clsx } from 'clsx';

interface TemplatePreviewProps {
  workflowDefinition: WorkflowDefinition;
  templateName: string;
}

const STEP_ICONS = {
  agent_task: Play,
  conditional: GitBranch,
  loop: RefreshCw,
  parallel: Zap,
  webhook: Globe,
  delay: Clock,
  user_input: Users,
  data_transformation: Database,
};

const STEP_COLORS = {
  agent_task: 'bg-blue-100 text-blue-600 border-blue-200',
  conditional: 'bg-yellow-100 text-yellow-600 border-yellow-200',
  loop: 'bg-purple-100 text-purple-600 border-purple-200',
  parallel: 'bg-pink-100 text-pink-600 border-pink-200',
  webhook: 'bg-green-100 text-green-600 border-green-200',
  delay: 'bg-gray-100 text-gray-600 border-gray-200',
  user_input: 'bg-indigo-100 text-indigo-600 border-indigo-200',
  data_transformation: 'bg-red-100 text-red-600 border-red-200',
};

export const TemplatePreview: React.FC<TemplatePreviewProps> = ({
  workflowDefinition,
  templateName,
}) => {
  const { steps, connections, input_variables, output_variables } = workflowDefinition;

  const getStepConnections = (stepId: string) => {
    return connections.filter(conn => conn.from_step === stepId);
  };

  const getStepInputs = (stepId: string) => {
    return connections.filter(conn => conn.to_step === stepId);
  };

  const isStartStep = (stepId: string) => {
    return stepId === workflowDefinition.start_step;
  };

  const isEndStep = (stepId: string) => {
    return workflowDefinition.end_steps.includes(stepId);
  };

  const renderStep = (step: any, index: number) => {
    const Icon = STEP_ICONS[step.type as keyof typeof STEP_ICONS] || Settings;
    const colorClass = STEP_COLORS[step.type as keyof typeof STEP_COLORS] || 'bg-gray-100 text-gray-600 border-gray-200';
    const outgoing = getStepConnections(step.id);
    const incoming = getStepInputs(step.id);

    return (
      <div key={step.id} className="relative">
        {/* Step Node */}
        <div className={clsx(
          'relative p-4 border-2 rounded-lg min-w-[200px]',
          colorClass,
          isStartStep(step.id) && 'ring-2 ring-green-300',
          isEndStep(step.id) && 'ring-2 ring-red-300'
        )}>
          {/* Step Header */}
          <div className="flex items-center space-x-3 mb-2">
            <div className="p-2 bg-white rounded-full">
              <Icon className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="font-medium text-gray-900 truncate">{step.name}</h4>
              <p className="text-xs opacity-75 capitalize">
                {step.type.replace('_', ' ')}
              </p>
            </div>
            <div className="text-xs font-medium bg-white px-2 py-1 rounded">
              #{index + 1}
            </div>
          </div>

          {/* Step Details */}
          <div className="space-y-1 text-xs">
            {step.config.agent_type && (
              <div className="flex justify-between">
                <span className="opacity-75">Agent:</span>
                <span className="font-medium">{step.config.agent_type}</span>
              </div>
            )}
            {step.config.task && (
              <div>
                <span className="opacity-75">Task:</span>
                <p className="mt-1 text-xs bg-white bg-opacity-50 p-2 rounded truncate">
                  {step.config.task.length > 100
                    ? `${step.config.task.substring(0, 100)}...`
                    : step.config.task
                  }
                </p>
              </div>
            )}
            {step.config.webhook_url && (
              <div className="flex justify-between">
                <span className="opacity-75">URL:</span>
                <span className="font-medium truncate">{step.config.webhook_url}</span>
              </div>
            )}
            {step.config.delay_seconds && (
              <div className="flex justify-between">
                <span className="opacity-75">Delay:</span>
                <span className="font-medium">{step.config.delay_seconds}s</span>
              </div>
            )}
          </div>

          {/* Step Badges */}
          <div className="flex items-center space-x-1 mt-2">
            {isStartStep(step.id) && (
              <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">
                START
              </span>
            )}
            {isEndStep(step.id) && (
              <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded-full">
                END
              </span>
            )}
            {incoming.length > 1 && (
              <span className="text-xs bg-blue-500 text-white px-2 py-0.5 rounded-full">
                {incoming.length} inputs
              </span>
            )}
          </div>
        </div>

        {/* Outgoing Connections */}
        {outgoing.length > 0 && (
          <div className="absolute left-full top-1/2 transform -translate-y-1/2 ml-4">
            <div className="flex items-center space-x-2">
              {outgoing.map((connection, connIndex) => (
                <div key={connIndex} className="flex items-center space-x-2">
                  <ArrowRight className="w-4 h-4 text-gray-400" />
                  {connection.condition && (
                    <div className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded border">
                      IF {connection.condition.variable} {connection.condition.operator} {connection.condition.value}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Simple layout: arrange steps in a grid based on dependencies
  const arrangeSteps = () => {
    const arranged: any[][] = [];
    const processed = new Set<string>();
    const startSteps = steps.filter(step =>
      !connections.some(conn => conn.to_step === step.id) || isStartStep(step.id)
    );

    let currentLevel = startSteps;
    while (currentLevel.length > 0) {
      arranged.push([...currentLevel]);
      currentLevel.forEach(step => processed.add(step.id));

      // Find next level
      const nextLevel = steps.filter(step =>
        !processed.has(step.id) &&
        connections.some(conn =>
          conn.to_step === step.id && processed.has(conn.from_step)
        )
      );

      currentLevel = nextLevel;
    }

    // Add any remaining steps
    const remaining = steps.filter(step => !processed.has(step.id));
    if (remaining.length > 0) {
      arranged.push(remaining);
    }

    return arranged;
  };

  const levels = arrangeSteps();

  return (
    <div className="space-y-8">
      {/* Workflow Info */}
      <div className="bg-gray-50 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Workflow: {templateName}
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Input Variables */}
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Input Variables</h4>
            {input_variables.length === 0 ? (
              <p className="text-sm text-gray-500">No input variables</p>
            ) : (
              <div className="space-y-1">
                {input_variables.map((variable, index) => (
                  <div key={index} className="text-sm bg-white p-2 rounded border">
                    <div className="font-medium">{variable.name}</div>
                    <div className="text-gray-600 text-xs">
                      Type: {variable.type}
                      {variable.required && <span className="text-red-500 ml-1">*</span>}
                    </div>
                    {variable.description && (
                      <div className="text-gray-500 text-xs mt-1">{variable.description}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Output Variables */}
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Output Variables</h4>
            {output_variables.length === 0 ? (
              <p className="text-sm text-gray-500">No output variables</p>
            ) : (
              <div className="space-y-1">
                {output_variables.map((variable, index) => (
                  <div key={index} className="text-sm bg-white p-2 rounded border">
                    <div className="font-medium">{variable.name}</div>
                    <div className="text-gray-600 text-xs">Type: {variable.type}</div>
                    {variable.description && (
                      <div className="text-gray-500 text-xs mt-1">{variable.description}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Statistics */}
          <div>
            <h4 className="font-medium text-gray-900 mb-2">Statistics</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Total Steps:</span>
                <span className="font-medium">{steps.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Connections:</span>
                <span className="font-medium">{connections.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Complexity:</span>
                <span className="font-medium">
                  {steps.length < 5 ? 'Simple' : steps.length < 10 ? 'Medium' : 'Complex'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Visualization */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Workflow Structure</h3>

        {levels.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No workflow steps to display</p>
        ) : (
          <div className="space-y-8 overflow-x-auto">
            {levels.map((level, levelIndex) => (
              <div key={levelIndex} className="flex items-center space-x-8 min-w-max">
                {level.map((step, stepIndex) => (
                  <div key={step.id} className="flex items-center space-x-4">
                    {renderStep(step, steps.findIndex(s => s.id === step.id))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="font-medium text-gray-900 mb-3">Legend</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {Object.entries(STEP_COLORS).map(([type, colorClass]) => {
            const Icon = STEP_ICONS[type as keyof typeof STEP_ICONS];
            return (
              <div key={type} className="flex items-center space-x-2">
                <div className={clsx('p-1 rounded border', colorClass)}>
                  <Icon className="w-3 h-3" />
                </div>
                <span className="capitalize">{type.replace('_', ' ')}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};