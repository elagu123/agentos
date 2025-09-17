import React from 'react';
import {
  Bot,
  GitBranch,
  RefreshCw,
  Zap,
  Globe,
  Clock,
  Users,
  Database,
  Plus
} from 'lucide-react';
import { clsx } from 'clsx';

interface NodeTemplate {
  type: string;
  label: string;
  icon: React.ComponentType<any>;
  description: string;
  category: 'agents' | 'control' | 'integration' | 'data';
  color: string;
  defaultConfig?: any;
}

const NODE_TEMPLATES: NodeTemplate[] = [
  // Agent nodes
  {
    type: 'agent_task',
    label: 'Copywriter Agent',
    icon: Bot,
    description: 'Create marketing content and copy',
    category: 'agents',
    color: 'bg-purple-500',
    defaultConfig: { agent_type: 'copywriter' }
  },
  {
    type: 'agent_task',
    label: 'Researcher Agent',
    icon: Bot,
    description: 'Perform research and analysis',
    category: 'agents',
    color: 'bg-blue-500',
    defaultConfig: { agent_type: 'researcher' }
  },
  {
    type: 'agent_task',
    label: 'Scheduler Agent',
    icon: Bot,
    description: 'Manage calendar and scheduling',
    category: 'agents',
    color: 'bg-green-500',
    defaultConfig: { agent_type: 'scheduler' }
  },
  {
    type: 'agent_task',
    label: 'Email Responder',
    icon: Bot,
    description: 'Handle email responses',
    category: 'agents',
    color: 'bg-orange-500',
    defaultConfig: { agent_type: 'email_responder' }
  },
  {
    type: 'agent_task',
    label: 'Data Analyzer',
    icon: Bot,
    description: 'Analyze data and generate insights',
    category: 'agents',
    color: 'bg-red-500',
    defaultConfig: { agent_type: 'data_analyzer' }
  },

  // Control flow nodes
  {
    type: 'conditional',
    label: 'Conditional',
    icon: GitBranch,
    description: 'Branch workflow based on conditions',
    category: 'control',
    color: 'bg-yellow-500',
    defaultConfig: {
      condition: {
        variable: '',
        operator: 'equals',
        value: ''
      }
    }
  },
  {
    type: 'loop',
    label: 'Loop',
    icon: RefreshCw,
    description: 'Repeat steps for each item',
    category: 'control',
    color: 'bg-indigo-500',
    defaultConfig: {
      loop_config: {
        iterable_variable: '',
        max_iterations: 10
      }
    }
  },
  {
    type: 'parallel',
    label: 'Parallel',
    icon: Zap,
    description: 'Execute multiple steps in parallel',
    category: 'control',
    color: 'bg-pink-500',
    defaultConfig: {
      parallel_steps: []
    }
  },

  // Integration nodes
  {
    type: 'webhook',
    label: 'Webhook',
    icon: Globe,
    description: 'Call external API endpoints',
    category: 'integration',
    color: 'bg-teal-500',
    defaultConfig: {
      webhook_url: '',
      webhook_method: 'POST'
    }
  },
  {
    type: 'delay',
    label: 'Delay',
    icon: Clock,
    description: 'Wait for specified time',
    category: 'control',
    color: 'bg-gray-500',
    defaultConfig: {
      delay_seconds: 60
    }
  },

  // Data nodes
  {
    type: 'user_input',
    label: 'User Input',
    icon: Users,
    description: 'Request input from user',
    category: 'data',
    color: 'bg-cyan-500',
    defaultConfig: {}
  },
  {
    type: 'data_transformation',
    label: 'Transform Data',
    icon: Database,
    description: 'Transform and process data',
    category: 'data',
    color: 'bg-emerald-500',
    defaultConfig: {}
  },
];

const CATEGORIES = [
  { id: 'agents', label: 'AI Agents', color: 'text-purple-600' },
  { id: 'control', label: 'Control Flow', color: 'text-blue-600' },
  { id: 'integration', label: 'Integration', color: 'text-green-600' },
  { id: 'data', label: 'Data Processing', color: 'text-orange-600' },
];

interface NodePaletteProps {
  onNodeAdd: (nodeType: string, config?: any) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export const NodePalette: React.FC<NodePaletteProps> = ({
  onNodeAdd,
  isOpen,
  onToggle
}) => {
  const [selectedCategory, setSelectedCategory] = React.useState<string>('agents');

  const filteredTemplates = NODE_TEMPLATES.filter(
    template => template.category === selectedCategory
  );

  const handleNodeDragStart = (event: React.DragEvent, nodeTemplate: NodeTemplate) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify({
      type: nodeTemplate.type,
      config: nodeTemplate.defaultConfig || {},
      label: nodeTemplate.label,
    }));
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className={clsx(
      'fixed left-0 top-0 h-full bg-white shadow-lg border-r border-gray-200 transition-transform duration-300 z-40',
      isOpen ? 'translate-x-0' : '-translate-x-full',
      'w-80'
    )}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Node Palette</h2>
          <button
            onClick={onToggle}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Plus className={clsx('w-5 h-5 transition-transform', isOpen && 'rotate-45')} />
          </button>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex overflow-x-auto border-b border-gray-200">
        {CATEGORIES.map(category => (
          <button
            key={category.id}
            onClick={() => setSelectedCategory(category.id)}
            className={clsx(
              'px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors',
              selectedCategory === category.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            )}
          >
            {category.label}
          </button>
        ))}
      </div>

      {/* Node Templates */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-3">
          {filteredTemplates.map((template, index) => {
            const Icon = template.icon;
            return (
              <div
                key={`${template.type}-${index}`}
                draggable
                onDragStart={(e) => handleNodeDragStart(e, template)}
                onClick={() => onNodeAdd(template.type, template.defaultConfig)}
                className="p-3 border border-gray-200 rounded-lg hover:border-blue-300 hover:shadow-md cursor-move transition-all group"
              >
                <div className="flex items-start space-x-3">
                  <div className={clsx('p-2 rounded-lg', template.color)}>
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium text-gray-900 group-hover:text-blue-600">
                      {template.label}
                    </h3>
                    <p className="text-xs text-gray-500 mt-1">
                      {template.description}
                    </p>
                    {template.defaultConfig?.agent_type && (
                      <div className="mt-2">
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          {template.defaultConfig.agent_type}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Instructions */}
        <div className="mt-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <h4 className="text-sm font-medium text-blue-900 mb-1">How to use:</h4>
          <ul className="text-xs text-blue-700 space-y-1">
            <li>• Drag nodes to the canvas</li>
            <li>• Click to add at center</li>
            <li>• Connect nodes with handles</li>
            <li>• Configure in properties panel</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default NodePalette;