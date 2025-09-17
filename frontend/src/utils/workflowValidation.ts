import {
  WorkflowDefinition,
  WorkflowStep,
  StepConnection,
  ValidationError,
  WorkflowValidationResult
} from '../types/workflow';

export class WorkflowValidator {
  private workflow: WorkflowDefinition;
  private errors: ValidationError[] = [];
  private warnings: ValidationError[] = [];

  constructor(workflow: WorkflowDefinition) {
    this.workflow = workflow;
  }

  validate(): WorkflowValidationResult {
    this.errors = [];
    this.warnings = [];

    this.validateBasicStructure();
    this.validateSteps();
    this.validateConnections();
    this.validateDependencies();
    this.detectCycles();
    this.validateVariables();

    return {
      is_valid: this.errors.length === 0,
      errors: this.errors,
      warnings: this.warnings,
      execution_graph: this.errors.length === 0 ? this.buildExecutionGraph() : undefined,
    };
  }

  private validateBasicStructure(): void {
    if (!this.workflow.name || this.workflow.name.trim() === '') {
      this.errors.push({
        type: 'error',
        message: 'Workflow name is required',
      });
    }

    if (!this.workflow.start_step) {
      this.errors.push({
        type: 'error',
        message: 'Start step is required',
      });
    }

    if (!this.workflow.end_steps || this.workflow.end_steps.length === 0) {
      this.errors.push({
        type: 'error',
        message: 'At least one end step is required',
      });
    }

    if (!this.workflow.steps || this.workflow.steps.length === 0) {
      this.errors.push({
        type: 'error',
        message: 'Workflow must have at least one step',
      });
    }
  }

  private validateSteps(): void {
    const stepIds = new Set<string>();

    this.workflow.steps.forEach(step => {
      // Check for duplicate step IDs
      if (stepIds.has(step.id)) {
        this.errors.push({
          type: 'error',
          message: `Duplicate step ID: ${step.id}`,
          step_id: step.id,
        });
      }
      stepIds.add(step.id);

      // Validate step structure
      if (!step.name || step.name.trim() === '') {
        this.errors.push({
          type: 'error',
          message: `Step ${step.id} must have a name`,
          step_id: step.id,
        });
      }

      // Validate step type-specific configuration
      this.validateStepConfig(step);
    });

    // Validate start step exists
    if (this.workflow.start_step && !stepIds.has(this.workflow.start_step)) {
      this.errors.push({
        type: 'error',
        message: `Start step '${this.workflow.start_step}' does not exist`,
      });
    }

    // Validate end steps exist
    this.workflow.end_steps.forEach(endStep => {
      if (!stepIds.has(endStep)) {
        this.errors.push({
          type: 'error',
          message: `End step '${endStep}' does not exist`,
        });
      }
    });
  }

  private validateStepConfig(step: WorkflowStep): void {
    switch (step.type) {
      case 'agent_task':
        if (!step.config.agent_type) {
          this.errors.push({
            type: 'error',
            message: `Agent task step '${step.id}' must specify agent_type`,
            step_id: step.id,
          });
        }
        if (!step.config.task) {
          this.errors.push({
            type: 'error',
            message: `Agent task step '${step.id}' must specify task`,
            step_id: step.id,
          });
        }
        break;

      case 'conditional':
        if (!step.config.condition) {
          this.errors.push({
            type: 'error',
            message: `Conditional step '${step.id}' must specify condition`,
            step_id: step.id,
          });
        }
        break;

      case 'loop':
        if (!step.config.loop_config?.iterable_variable) {
          this.errors.push({
            type: 'error',
            message: `Loop step '${step.id}' must specify iterable_variable`,
            step_id: step.id,
          });
        }
        break;

      case 'parallel':
        if (!step.config.parallel_steps || step.config.parallel_steps.length === 0) {
          this.errors.push({
            type: 'error',
            message: `Parallel step '${step.id}' must specify parallel_steps`,
            step_id: step.id,
          });
        }
        break;

      case 'webhook':
        if (!step.config.webhook_url) {
          this.errors.push({
            type: 'error',
            message: `Webhook step '${step.id}' must specify webhook_url`,
            step_id: step.id,
          });
        }
        break;

      case 'delay':
        if (!step.config.delay_seconds || step.config.delay_seconds <= 0) {
          this.errors.push({
            type: 'error',
            message: `Delay step '${step.id}' must specify positive delay_seconds`,
            step_id: step.id,
          });
        }
        break;
    }
  }

  private validateConnections(): void {
    const stepIds = new Set(this.workflow.steps.map(s => s.id));

    this.workflow.connections.forEach((connection, index) => {
      // Validate from_step exists
      if (!stepIds.has(connection.from_step)) {
        this.errors.push({
          type: 'error',
          message: `Connection ${index}: from_step '${connection.from_step}' does not exist`,
          connection_id: `${connection.from_step}-${connection.to_step}`,
        });
      }

      // Validate to_step exists
      if (!stepIds.has(connection.to_step)) {
        this.errors.push({
          type: 'error',
          message: `Connection ${index}: to_step '${connection.to_step}' does not exist`,
          connection_id: `${connection.from_step}-${connection.to_step}`,
        });
      }

      // Validate no self-connections
      if (connection.from_step === connection.to_step) {
        this.errors.push({
          type: 'error',
          message: `Step '${connection.from_step}' cannot connect to itself`,
          connection_id: `${connection.from_step}-${connection.to_step}`,
        });
      }
    });
  }

  private validateDependencies(): void {
    const stepIds = new Set(this.workflow.steps.map(s => s.id));

    this.workflow.steps.forEach(step => {
      if (step.dependencies) {
        step.dependencies.forEach(dep => {
          if (!stepIds.has(dep)) {
            this.errors.push({
              type: 'error',
              message: `Step '${step.id}' depends on non-existent step '${dep}'`,
              step_id: step.id,
            });
          }
        });
      }
    });
  }

  private detectCycles(): void {
    const graph = this.buildDependencyGraph();
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    const hasCycle = (node: string): boolean => {
      if (recursionStack.has(node)) {
        return true;
      }
      if (visited.has(node)) {
        return false;
      }

      visited.add(node);
      recursionStack.add(node);

      const neighbors = graph.get(node) || [];
      for (const neighbor of neighbors) {
        if (hasCycle(neighbor)) {
          return true;
        }
      }

      recursionStack.delete(node);
      return false;
    };

    for (const stepId of this.workflow.steps.map(s => s.id)) {
      if (!visited.has(stepId) && hasCycle(stepId)) {
        this.errors.push({
          type: 'error',
          message: `Cycle detected in workflow dependencies involving step '${stepId}'`,
          step_id: stepId,
        });
        break;
      }
    }
  }

  private validateVariables(): void {
    // Check for variable name conflicts
    const allVariables = [
      ...this.workflow.input_variables,
      ...this.workflow.output_variables,
    ];

    const variableNames = new Set<string>();
    allVariables.forEach(variable => {
      if (variableNames.has(variable.name)) {
        this.errors.push({
          type: 'error',
          message: `Duplicate variable name: '${variable.name}'`,
        });
      }
      variableNames.add(variable.name);
    });

    // Validate required input variables
    this.workflow.input_variables.forEach(variable => {
      if (variable.required && variable.default_value === undefined) {
        this.warnings.push({
          type: 'warning',
          message: `Required input variable '${variable.name}' has no default value`,
        });
      }
    });
  }

  private buildDependencyGraph(): Map<string, string[]> {
    const graph = new Map<string, string[]>();

    // Initialize graph with all steps
    this.workflow.steps.forEach(step => {
      graph.set(step.id, []);
    });

    // Add explicit dependencies
    this.workflow.steps.forEach(step => {
      if (step.dependencies) {
        step.dependencies.forEach(dep => {
          const neighbors = graph.get(dep) || [];
          neighbors.push(step.id);
          graph.set(dep, neighbors);
        });
      }
    });

    // Add connections as dependencies
    this.workflow.connections.forEach(connection => {
      const neighbors = graph.get(connection.from_step) || [];
      neighbors.push(connection.to_step);
      graph.set(connection.from_step, neighbors);
    });

    return graph;
  }

  private buildExecutionGraph(): {
    levels: string[][];
    critical_path: string[];
    estimated_duration: number;
  } {
    const graph = this.buildDependencyGraph();
    const levels: string[][] = [];
    const inDegree = new Map<string, number>();
    const queue: string[] = [];

    // Calculate in-degrees
    this.workflow.steps.forEach(step => {
      inDegree.set(step.id, 0);
    });

    graph.forEach((neighbors, node) => {
      neighbors.forEach(neighbor => {
        inDegree.set(neighbor, (inDegree.get(neighbor) || 0) + 1);
      });
    });

    // Find starting nodes (in-degree = 0)
    inDegree.forEach((degree, node) => {
      if (degree === 0) {
        queue.push(node);
      }
    });

    // Build execution levels
    while (queue.length > 0) {
      const currentLevel = [...queue];
      levels.push(currentLevel);
      queue.length = 0;

      currentLevel.forEach(node => {
        const neighbors = graph.get(node) || [];
        neighbors.forEach(neighbor => {
          const newDegree = (inDegree.get(neighbor) || 0) - 1;
          inDegree.set(neighbor, newDegree);
          if (newDegree === 0) {
            queue.push(neighbor);
          }
        });
      });
    }

    // Simple critical path calculation (longest path)
    const criticalPath = this.findLongestPath(graph);

    // Estimate duration (simplified - 30 seconds per step)
    const estimatedDuration = criticalPath.length * 30;

    return {
      levels,
      critical_path: criticalPath,
      estimated_duration: estimatedDuration,
    };
  }

  private findLongestPath(graph: Map<string, string[]>): string[] {
    // Simplified longest path calculation
    // In a real implementation, this would consider actual step durations
    const visited = new Set<string>();
    let longestPath: string[] = [];

    const dfs = (node: string, currentPath: string[]): void => {
      if (visited.has(node)) return;

      visited.add(node);
      currentPath.push(node);

      const neighbors = graph.get(node) || [];
      if (neighbors.length === 0) {
        // Leaf node - check if this is the longest path so far
        if (currentPath.length > longestPath.length) {
          longestPath = [...currentPath];
        }
      } else {
        neighbors.forEach(neighbor => {
          dfs(neighbor, currentPath);
        });
      }

      currentPath.pop();
      visited.delete(node);
    };

    // Start from the workflow start step
    if (this.workflow.start_step) {
      dfs(this.workflow.start_step, []);
    }

    return longestPath;
  }
}

export const validateWorkflow = (workflow: WorkflowDefinition): WorkflowValidationResult => {
  const validator = new WorkflowValidator(workflow);
  return validator.validate();
};