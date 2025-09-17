import React, { useCallback, useMemo, useState, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Node,
  Edge,
  Connection,
  Panel,
  ReactFlowInstance,
} from '@xyflow/react';
import { Plus, Save, Play, Eye, Upload, Download, AlertTriangle, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';

import { allNodeTypes } from './NodeTypes';
import { NodePalette } from './NodePalette';
import { PropertiesPanel } from './PropertiesPanel';
import { TemplateGallery } from './TemplateGallery';
import { ExecutionMonitor } from './ExecutionMonitor';

import {
  WorkflowDefinition,
  WorkflowStep,
  WorkflowNode,
  WorkflowEdge,
  StepConnection,
} from '../../types/workflow';
import { validateWorkflow } from '../../utils/workflowValidation';
import { useCreateWorkflow, useUpdateWorkflow, useExecuteWorkflow } from '../../hooks/useWorkflowAPI';

import '@xyflow/react/dist/style.css';

interface WorkflowBuilderProps {
  initialWorkflow?: WorkflowDefinition;
  onSave?: (workflow: WorkflowDefinition) => void;
  onExecute?: (workflowId: string, variables: Record<string, any>) => void;
  mode?: 'create' | 'edit' | 'view';
}

let nodeId = 0;
const getId = () => `node_${nodeId++}`;

export const WorkflowBuilder: React.FC<WorkflowBuilderProps> = ({
  initialWorkflow,
  onSave,
  onExecute,
  mode = 'create',
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<WorkflowEdge>([]);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  // UI State
  const [isPaletteOpen, setIsPaletteOpen] = useState(true);
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [isPropertiesPanelOpen, setIsPropertiesPanelOpen] = useState(false);
  const [isTemplateGalleryOpen, setIsTemplateGalleryOpen] = useState(false);
  const [isExecutionMonitorOpen, setIsExecutionMonitorOpen] = useState(false);
  const [currentExecutionId, setCurrentExecutionId] = useState<string | null>(null);

  // Workflow State
  const [workflowName, setWorkflowName] = useState(initialWorkflow?.name || 'New Workflow');
  const [workflowDescription, setWorkflowDescription] = useState(initialWorkflow?.description || '');
  const [validationResult, setValidationResult] = useState<any>(null);

  // API Hooks
  const createWorkflowMutation = useCreateWorkflow();
  const updateWorkflowMutation = useUpdateWorkflow();
  const executeWorkflowMutation = useExecuteWorkflow();

  // Initialize workflow from props
  React.useEffect(() => {
    if (initialWorkflow) {
      loadWorkflowIntoEditor(initialWorkflow);
    }
  }, [initialWorkflow]);

  // Real-time validation
  React.useEffect(() => {
    const workflow = buildWorkflowFromEditor();
    if (workflow.steps.length > 0) {
      const result = validateWorkflow(workflow);
      setValidationResult(result);

      // Update node validation states
      setNodes(prevNodes =>
        prevNodes.map(node => {
          const stepErrors = result.errors
            .filter(error => error.step_id === node.data.step.id)
            .map(error => error.message);

          return {
            ...node,
            data: {
              ...node.data,
              isValid: stepErrors.length === 0,
              validationErrors: stepErrors,
            },
          };
        })
      );
    }
  }, [nodes, edges, setNodes]);

  const loadWorkflowIntoEditor = (workflow: WorkflowDefinition) => {
    const newNodes: WorkflowNode[] = workflow.steps.map(step => ({
      id: step.id,
      type: step.type,
      position: step.position,
      data: {
        step,
        isValid: true,
        validationErrors: [],
      },
    }));

    const newEdges: WorkflowEdge[] = workflow.connections.map((connection, index) => ({
      id: `edge-${index}`,
      source: connection.from_step,
      target: connection.to_step,
      data: {
        connection,
        isValid: true,
      },
    }));

    setNodes(newNodes);
    setEdges(newEdges);
    setWorkflowName(workflow.name);
    setWorkflowDescription(workflow.description || '');
  };

  const buildWorkflowFromEditor = (): WorkflowDefinition => {
    const steps: WorkflowStep[] = nodes.map(node => node.data.step);
    const connections: StepConnection[] = edges.map(edge => edge.data!.connection);

    return {
      name: workflowName,
      description: workflowDescription,
      version: '1.0.0',
      input_variables: [],
      output_variables: [],
      steps,
      connections,
      start_step: steps.length > 0 ? steps[0].id : '',
      end_steps: steps.length > 0 ? [steps[steps.length - 1].id] : [],
    };
  };

  const onConnect = useCallback((params: Connection) => {
    const newConnection: StepConnection = {
      from_step: params.source!,
      to_step: params.target!,
    };

    const newEdge: WorkflowEdge = {
      ...params,
      id: `edge-${edges.length}`,
      data: {
        connection: newConnection,
        isValid: true,
      },
    } as WorkflowEdge;

    setEdges(eds => addEdge(newEdge, eds));
  }, [edges.length, setEdges]);

  const onNodeAdd = useCallback((nodeType: string, config: any = {}) => {
    if (!reactFlowInstance) return;

    const id = getId();
    const position = reactFlowInstance.screenToFlowPosition({
      x: window.innerWidth / 2,
      y: window.innerHeight / 2,
    });

    const newStep: WorkflowStep = {
      id,
      name: config.label || `${nodeType.replace('_', ' ')} ${id}`,
      type: nodeType as any,
      config,
      position,
    };

    const newNode: WorkflowNode = {
      id,
      type: nodeType,
      position,
      data: {
        step: newStep,
        isValid: true,
        validationErrors: [],
      },
    };

    setNodes(nds => nds.concat(newNode));
  }, [reactFlowInstance, setNodes]);

  const onNodeClick = useCallback((event: React.MouseEvent, node: WorkflowNode) => {
    setSelectedNode(node);
    setIsPropertiesPanelOpen(true);
  }, []);

  const onStepUpdate = useCallback((stepId: string, updates: Partial<WorkflowStep>) => {
    setNodes(nds =>
      nds.map(node =>
        node.id === stepId
          ? {
              ...node,
              data: {
                ...node.data,
                step: { ...node.data.step, ...updates },
              },
            }
          : node
      )
    );
  }, [setNodes]);

  const onSaveWorkflow = async () => {
    const workflow = buildWorkflowFromEditor();
    const validation = validateWorkflow(workflow);

    if (!validation.is_valid) {
      toast.error('Please fix validation errors before saving');
      return;
    }

    try {
      if (mode === 'create') {
        await createWorkflowMutation.mutateAsync(workflow);
        toast.success('Workflow created successfully');
      } else if (mode === 'edit' && initialWorkflow?.id) {
        await updateWorkflowMutation.mutateAsync({
          id: initialWorkflow.id,
          workflow,
        });
        toast.success('Workflow updated successfully');
      }

      onSave?.(workflow);
    } catch (error) {
      toast.error('Failed to save workflow');
      console.error('Save error:', error);
    }
  };

  const onExecuteWorkflow = async () => {
    const workflow = buildWorkflowFromEditor();
    const validation = validateWorkflow(workflow);

    if (!validation.is_valid) {
      toast.error('Cannot execute workflow with validation errors');
      return;
    }

    try {
      // For demo purposes, we'll use empty input variables
      const execution = await executeWorkflowMutation.mutateAsync({
        workflowId: initialWorkflow?.id || 'demo',
        inputVariables: {},
      });

      setCurrentExecutionId(execution.data.id);
      setIsExecutionMonitorOpen(true);
      toast.success('Workflow execution started');
    } catch (error) {
      toast.error('Failed to execute workflow');
      console.error('Execution error:', error);
    }
  };

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (!reactFlowInstance) return;

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      const type = event.dataTransfer.getData('application/reactflow');

      if (!type) return;

      const nodeData = JSON.parse(type);
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });

      onNodeAdd(nodeData.type, { ...nodeData.config, label: nodeData.label });
    },
    [reactFlowInstance, onNodeAdd]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
    setIsPropertiesPanelOpen(false);
  }, []);

  const isReadOnly = mode === 'view';
  const canSave = mode !== 'view' && validationResult?.is_valid;
  const canExecute = validationResult?.is_valid && initialWorkflow?.id;

  return (
    <div className="h-screen flex relative">
      {/* Node Palette */}
      {!isReadOnly && (
        <NodePalette
          isOpen={isPaletteOpen}
          onToggle={() => setIsPaletteOpen(!isPaletteOpen)}
          onNodeAdd={onNodeAdd}
        />
      )}

      {/* Main Canvas */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onInit={setReactFlowInstance}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={allNodeTypes}
          fitView
          defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
          className="bg-workflow-background"
          nodesDraggable={!isReadOnly}
          nodesConnectable={!isReadOnly}
          elementsSelectable={!isReadOnly}
        >
          <Background color="#e5e7eb" size={1} />
          <Controls showInteractive={false} />
          <MiniMap className="bg-white border border-gray-300" />

          {/* Top Toolbar */}
          <Panel position="top-left" className="flex items-center space-x-2 bg-white rounded-lg shadow-md p-2 m-4">
            {!isReadOnly && (
              <button
                onClick={() => setIsPaletteOpen(!isPaletteOpen)}
                className="p-2 hover:bg-gray-100 rounded transition-colors"
                title="Toggle Node Palette"
              >
                <Plus className="w-5 h-5" />
              </button>
            )}

            <div className="flex items-center space-x-2 px-2 border-l border-gray-200">
              <input
                type="text"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                disabled={isReadOnly}
                className="text-lg font-semibold bg-transparent border-none outline-none"
                placeholder="Workflow Name"
              />
            </div>

            <div className="flex items-center space-x-2 px-2 border-l border-gray-200">
              {validationResult?.is_valid ? (
                <CheckCircle className="w-5 h-5 text-green-500" title="Workflow is valid" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-orange-500" title="Validation errors" />
              )}
              <span className="text-sm text-gray-600">
                {validationResult?.errors?.length || 0} errors
              </span>
            </div>
          </Panel>

          {/* Action Buttons */}
          <Panel position="top-right" className="flex items-center space-x-2 bg-white rounded-lg shadow-md p-2 m-4">
            <button
              onClick={() => setIsTemplateGalleryOpen(true)}
              className="px-3 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            >
              <Upload className="w-4 h-4 mr-2 inline" />
              Templates
            </button>

            {canExecute && (
              <button
                onClick={onExecuteWorkflow}
                disabled={executeWorkflowMutation.isPending}
                className="px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                <Play className="w-4 h-4 mr-2 inline" />
                {executeWorkflowMutation.isPending ? 'Starting...' : 'Execute'}
              </button>
            )}

            {!isReadOnly && (
              <button
                onClick={onSaveWorkflow}
                disabled={!canSave || createWorkflowMutation.isPending || updateWorkflowMutation.isPending}
                className="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                <Save className="w-4 h-4 mr-2 inline" />
                {createWorkflowMutation.isPending || updateWorkflowMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            )}
          </Panel>
        </ReactFlow>
      </div>

      {/* Properties Panel */}
      {selectedNode && (
        <PropertiesPanel
          selectedStep={selectedNode.data.step}
          onStepUpdate={onStepUpdate}
          onClose={() => setIsPropertiesPanelOpen(false)}
          isOpen={isPropertiesPanelOpen}
          validationErrors={selectedNode.data.validationErrors}
        />
      )}

      {/* Template Gallery Modal */}
      {isTemplateGalleryOpen && (
        <TemplateGallery
          onClose={() => setIsTemplateGalleryOpen(false)}
          onSelectTemplate={(template) => {
            loadWorkflowIntoEditor(template.workflow_definition);
            setIsTemplateGalleryOpen(false);
          }}
        />
      )}

      {/* Execution Monitor Modal */}
      {isExecutionMonitorOpen && currentExecutionId && (
        <ExecutionMonitor
          executionId={currentExecutionId}
          onClose={() => setIsExecutionMonitorOpen(false)}
        />
      )}
    </div>
  );
};