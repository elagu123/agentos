import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  Bot,
  GitBranch,
  RefreshCw,
  Zap,
  Globe,
  Clock,
  Users,
  Database,
  AlertCircle,
  CheckCircle,
  Loader2
} from 'lucide-react';
import { WorkflowNode } from '../../types/workflow';
import { clsx } from 'clsx';

// Node type icons mapping
const NODE_ICONS = {
  agent_task: Bot,
  conditional: GitBranch,
  loop: RefreshCw,
  parallel: Zap,
  webhook: Globe,
  delay: Clock,
  user_input: Users,
  data_transformation: Database,
};

// Agent type colors
const AGENT_COLORS = {
  copywriter: 'bg-purple-500',
  researcher: 'bg-blue-500',
  scheduler: 'bg-green-500',
  email_responder: 'bg-orange-500',
  data_analyzer: 'bg-red-500',
};

interface BaseNodeProps extends NodeProps {
  data: WorkflowNode['data'];
}

const BaseNode: React.FC<BaseNodeProps> = ({ data, selected }) => {
  const { step, isValid, validationErrors, isExecuting, executionResult, executionError } = data;
  const Icon = NODE_ICONS[step.type] || Bot;

  const getNodeColor = () => {
    if (step.type === 'agent_task' && step.config.agent_type) {
      return AGENT_COLORS[step.config.agent_type as keyof typeof AGENT_COLORS] || 'bg-gray-500';
    }
    return 'bg-blue-500';
  };

  const getStatusIcon = () => {
    if (isExecuting) {
      return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
    }
    if (executionError) {
      return <AlertCircle className="w-4 h-4 text-red-500" />;
    }
    if (executionResult) {
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    }
    if (!isValid) {
      return <AlertCircle className="w-4 h-4 text-orange-500" />;
    }
    return null;
  };

  return (
    <div
      className={clsx(
        'px-4 py-3 shadow-md rounded-lg border-2 bg-white min-w-[200px] max-w-[300px]',
        selected ? 'border-blue-500' : 'border-gray-200',
        isExecuting && 'ring-2 ring-blue-300 animate-pulse-slow',
        !isValid && 'border-orange-300'
      )}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-gray-400 border-2 border-white"
      />

      {/* Node Header */}
      <div className="flex items-center space-x-3 mb-2">
        <div className={clsx('p-2 rounded-full', getNodeColor())}>
          <Icon className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-gray-900 truncate">
            {step.name}
          </h3>
          <p className="text-xs text-gray-500 capitalize">
            {step.type.replace('_', ' ')}
          </p>
        </div>
        {getStatusIcon()}
      </div>

      {/* Node Content */}
      <div className="space-y-1">
        {step.type === 'agent_task' && step.config.agent_type && (
          <div className="text-xs text-gray-600">
            <span className="font-medium">Agent:</span> {step.config.agent_type}
          </div>
        )}

        {step.config.task && (
          <div className="text-xs text-gray-600">
            <span className="font-medium">Task:</span>{' '}
            <span className="truncate block">{step.config.task}</span>
          </div>
        )}

        {step.config.condition && (
          <div className="text-xs text-gray-600">
            <span className="font-medium">Condition:</span>{' '}
            {step.config.condition.variable} {step.config.condition.operator} {step.config.condition.value}
          </div>
        )}

        {step.config.webhook_url && (
          <div className="text-xs text-gray-600">
            <span className="font-medium">URL:</span>{' '}
            <span className="truncate block">{step.config.webhook_url}</span>
          </div>
        )}

        {step.config.delay_seconds && (
          <div className="text-xs text-gray-600">
            <span className="font-medium">Delay:</span> {step.config.delay_seconds}s
          </div>
        )}
      </div>

      {/* Validation Errors */}
      {!isValid && validationErrors.length > 0 && (
        <div className="mt-2 p-2 bg-orange-50 border border-orange-200 rounded text-xs">
          <ul className="list-disc list-inside space-y-1">
            {validationErrors.map((error, index) => (
              <li key={index} className="text-orange-700">{error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Execution Error */}
      {executionError && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          {executionError}
        </div>
      )}

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-gray-400 border-2 border-white"
      />
    </div>
  );
};

// Specialized node components
export const AgentTaskNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);
export const ConditionalNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);
export const LoopNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);
export const ParallelNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);
export const WebhookNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);
export const DelayNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);
export const UserInputNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);
export const DataTransformationNode = memo<BaseNodeProps>((props) => <BaseNode {...props} />);

// Node types mapping for React Flow
export const nodeTypes = {
  agent_task: AgentTaskNode,
  conditional: ConditionalNode,
  loop: LoopNode,
  parallel: ParallelNode,
  webhook: WebhookNode,
  delay: DelayNode,
  user_input: UserInputNode,
  data_transformation: DataTransformationNode,
};

// Start and End nodes
export const StartNode = memo<NodeProps>(() => (
  <div className="px-4 py-2 bg-green-500 text-white rounded-full shadow-md text-sm font-medium">
    START
    <Handle
      type="source"
      position={Position.Bottom}
      className="w-3 h-3 !bg-green-600 border-2 border-white"
    />
  </div>
));

export const EndNode = memo<NodeProps>(() => (
  <div className="px-4 py-2 bg-red-500 text-white rounded-full shadow-md text-sm font-medium">
    END
    <Handle
      type="target"
      position={Position.Top}
      className="w-3 h-3 !bg-red-600 border-2 border-white"
    />
  </div>
));

// Add start and end nodes to nodeTypes
export const allNodeTypes = {
  ...nodeTypes,
  start: StartNode,
  end: EndNode,
};