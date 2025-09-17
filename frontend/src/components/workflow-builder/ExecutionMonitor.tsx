import React, { useState, useEffect } from 'react';
import { X, Play, Pause, Square, Clock, CheckCircle, AlertCircle, Loader2, RotateCcw } from 'lucide-react';
import { WorkflowExecution, StepExecution, StepExecutionEvent } from '../../types/workflow';
import { useExecution, useCancelExecution } from '../../hooks/useWorkflowAPI';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';

interface ExecutionMonitorProps {
  executionId: string;
  onClose: () => void;
}

export const ExecutionMonitor: React.FC<ExecutionMonitorProps> = ({
  executionId,
  onClose,
}) => {
  const [events, setEvents] = useState<StepExecutionEvent[]>([]);
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);

  const { data: execution, isLoading } = useExecution(executionId);
  const cancelExecutionMutation = useCancelExecution();

  // WebSocket connection for real-time updates
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/api/v1/orchestration/executions/${executionId}/stream`);

    ws.onopen = () => {
      setIsWebSocketConnected(true);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const stepEvent: StepExecutionEvent = JSON.parse(event.data);
        setEvents(prev => [...prev, stepEvent]);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      setIsWebSocketConnected(false);
      console.log('WebSocket disconnected');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsWebSocketConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [executionId]);

  const handleCancelExecution = async () => {
    try {
      await cancelExecutionMutation.mutateAsync(executionId);
      toast.success('Execution cancelled');
    } catch (error) {
      toast.error('Failed to cancel execution');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-5 h-5 text-gray-400" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'cancelled':
        return <Square className="w-5 h-5 text-orange-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'text-gray-600 bg-gray-100';
      case 'running':
        return 'text-blue-600 bg-blue-100';
      case 'completed':
        return 'text-green-600 bg-green-100';
      case 'failed':
        return 'text-red-600 bg-red-100';
      case 'cancelled':
        return 'text-orange-600 bg-orange-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const formatDuration = (startTime?: string, endTime?: string) => {
    if (!startTime) return 'Not started';

    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const duration = Math.round((end.getTime() - start.getTime()) / 1000);

    if (duration < 60) return `${duration}s`;
    if (duration < 3600) return `${Math.floor(duration / 60)}m ${duration % 60}s`;
    return `${Math.floor(duration / 3600)}h ${Math.floor((duration % 3600) / 60)}m`;
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const getProgressPercentage = () => {
    if (!execution?.step_executions.length) return 0;

    const completed = execution.step_executions.filter(
      step => step.status === 'completed' || step.status === 'failed'
    ).length;

    return Math.round((completed / execution.step_executions.length) * 100);
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-gray-600 mt-4 text-center">Loading execution details...</p>
        </div>
      </div>
    );
  }

  if (!execution) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <p className="text-red-600">Execution not found</p>
          <button
            onClick={onClose}
            className="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl h-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              {getStatusIcon(execution.status)}
              <h2 className="text-xl font-bold text-gray-900">Workflow Execution</h2>
            </div>
            <div className="flex items-center space-x-2">
              <span className={clsx(
                'px-3 py-1 rounded-full text-sm font-medium capitalize',
                getStatusColor(execution.status)
              )}>
                {execution.status}
              </span>
              {isWebSocketConnected && (
                <div className="flex items-center space-x-1 text-green-600">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm">Live</span>
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {(execution.status === 'running' || execution.status === 'pending') && (
              <button
                onClick={handleCancelExecution}
                disabled={cancelExecutionMutation.isPending}
                className="px-3 py-2 text-sm border border-red-300 text-red-600 rounded hover:bg-red-50 disabled:opacity-50"
              >
                <Square className="w-4 h-4 mr-1 inline" />
                {cancelExecutionMutation.isPending ? 'Cancelling...' : 'Cancel'}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Execution Overview */}
        <div className="p-6 border-b border-gray-200">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{execution.step_executions.length}</div>
              <div className="text-sm text-gray-600">Total Steps</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {execution.step_executions.filter(s => s.status === 'completed').length}
              </div>
              <div className="text-sm text-gray-600">Completed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {execution.step_executions.filter(s => s.status === 'failed').length}
              </div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">
                {formatDuration(execution.started_at, execution.completed_at)}
              </div>
              <div className="text-sm text-gray-600">Duration</div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${getProgressPercentage()}%` }}
            ></div>
          </div>
          <div className="text-center text-sm text-gray-600 mt-2">
            {getProgressPercentage()}% Complete
          </div>
        </div>

        {/* Step Execution Details */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Step Execution Details</h3>
            <div className="space-y-4">
              {execution.step_executions.map((stepExecution, index) => (
                <div
                  key={stepExecution.step_id}
                  className={clsx(
                    'border rounded-lg p-4 transition-all',
                    stepExecution.status === 'running' ? 'border-blue-300 bg-blue-50' :
                    stepExecution.status === 'completed' ? 'border-green-300 bg-green-50' :
                    stepExecution.status === 'failed' ? 'border-red-300 bg-red-50' :
                    'border-gray-200'
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-3">
                      <div className="flex-shrink-0 w-8 h-8 bg-white border-2 border-gray-300 rounded-full flex items-center justify-center text-sm font-medium">
                        {index + 1}
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900">{stepExecution.step_id}</h4>
                        <div className="flex items-center space-x-2 text-sm text-gray-600">
                          {getStatusIcon(stepExecution.status)}
                          <span className="capitalize">{stepExecution.status}</span>
                          {stepExecution.retry_count > 0 && (
                            <span className="flex items-center space-x-1 text-orange-600">
                              <RotateCcw className="w-3 h-3" />
                              <span>{stepExecution.retry_count} retries</span>
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="text-right text-sm text-gray-600">
                      {stepExecution.started_at && (
                        <div>Started: {formatTimestamp(stepExecution.started_at)}</div>
                      )}
                      {stepExecution.completed_at && (
                        <div>Completed: {formatTimestamp(stepExecution.completed_at)}</div>
                      )}
                      <div className="font-medium">
                        {formatDuration(stepExecution.started_at, stepExecution.completed_at)}
                      </div>
                    </div>
                  </div>

                  {stepExecution.error_message && (
                    <div className="mt-2 p-3 bg-red-100 border border-red-200 rounded text-sm text-red-700">
                      <strong>Error:</strong> {stepExecution.error_message}
                    </div>
                  )}

                  {stepExecution.output_data && (
                    <div className="mt-2 p-3 bg-gray-100 border border-gray-200 rounded text-sm">
                      <strong>Output:</strong>
                      <pre className="mt-1 text-xs overflow-x-auto">
                        {JSON.stringify(stepExecution.output_data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Real-time Events Log */}
        {events.length > 0 && (
          <div className="border-t border-gray-200 bg-gray-50 p-4 max-h-48 overflow-y-auto">
            <h4 className="font-medium text-gray-900 mb-2">Real-time Events</h4>
            <div className="space-y-1 text-sm">
              {events.slice(-10).map((event, index) => (
                <div key={index} className="flex items-start space-x-2">
                  <span className="text-gray-500 font-mono text-xs">
                    {formatTimestamp(event.timestamp)}
                  </span>
                  <span className="capitalize text-gray-700">
                    {event.event_type.replace('_', ' ')}
                  </span>
                  <span className="text-gray-600">
                    Step: {event.step_id}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};