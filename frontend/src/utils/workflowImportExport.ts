import { WorkflowDefinition } from '../types/workflow';

export interface ExportOptions {
  format: 'json' | 'yaml';
  includeMetadata: boolean;
  minify: boolean;
}

export interface ImportResult {
  success: boolean;
  workflow?: WorkflowDefinition;
  errors: string[];
  warnings: string[];
}

/**
 * Export workflow to different formats
 */
export const exportWorkflow = (
  workflow: WorkflowDefinition,
  options: ExportOptions = { format: 'json', includeMetadata: true, minify: false }
): string => {
  try {
    // Clean up workflow for export
    const exportData = {
      ...workflow,
      // Remove runtime-only fields if not including metadata
      ...(options.includeMetadata ? {} : {
        id: undefined,
        created_at: undefined,
        updated_at: undefined,
      }),
    };

    switch (options.format) {
      case 'json':
        return JSON.stringify(exportData, null, options.minify ? 0 : 2);

      case 'yaml':
        // Simple YAML conversion (in a real app, you'd use a YAML library)
        return convertToYAML(exportData);

      default:
        throw new Error(`Unsupported export format: ${options.format}`);
    }
  } catch (error) {
    throw new Error(`Failed to export workflow: ${error}`);
  }
};

/**
 * Import workflow from different formats
 */
export const importWorkflow = (data: string, format: 'json' | 'yaml' = 'json'): ImportResult => {
  const errors: string[] = [];
  const warnings: string[] = [];

  try {
    let workflowData: any;

    switch (format) {
      case 'json':
        workflowData = JSON.parse(data);
        break;

      case 'yaml':
        workflowData = parseYAML(data);
        break;

      default:
        return {
          success: false,
          errors: [`Unsupported import format: ${format}`],
          warnings: [],
        };
    }

    // Validate required fields
    const validation = validateWorkflowData(workflowData);
    errors.push(...validation.errors);
    warnings.push(...validation.warnings);

    if (errors.length > 0) {
      return {
        success: false,
        errors,
        warnings,
      };
    }

    // Transform to proper workflow format
    const workflow = transformToWorkflow(workflowData);

    return {
      success: true,
      workflow,
      errors: [],
      warnings,
    };

  } catch (error) {
    return {
      success: false,
      errors: [`Failed to parse workflow data: ${error}`],
      warnings: [],
    };
  }
};

/**
 * Download workflow as file
 */
export const downloadWorkflow = (
  workflow: WorkflowDefinition,
  filename?: string,
  options?: ExportOptions
) => {
  const defaultOptions: ExportOptions = {
    format: 'json',
    includeMetadata: true,
    minify: false,
  };

  const exportOptions = { ...defaultOptions, ...options };
  const data = exportWorkflow(workflow, exportOptions);

  const blob = new Blob([data], {
    type: exportOptions.format === 'json' ? 'application/json' : 'application/x-yaml',
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = filename || `${workflow.name || 'workflow'}.${exportOptions.format}`;

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
};

/**
 * Read workflow from uploaded file
 */
export const readWorkflowFile = (file: File): Promise<ImportResult> => {
  return new Promise((resolve) => {
    const reader = new FileReader();

    reader.onload = (event) => {
      const data = event.target?.result as string;
      const format = file.name.endsWith('.yaml') || file.name.endsWith('.yml') ? 'yaml' : 'json';

      const result = importWorkflow(data, format);
      resolve(result);
    };

    reader.onerror = () => {
      resolve({
        success: false,
        errors: ['Failed to read file'],
        warnings: [],
      });
    };

    reader.readAsText(file);
  });
};

/**
 * Copy workflow to clipboard
 */
export const copyWorkflowToClipboard = async (
  workflow: WorkflowDefinition,
  options?: ExportOptions
): Promise<boolean> => {
  try {
    const data = exportWorkflow(workflow, options);
    await navigator.clipboard.writeText(data);
    return true;
  } catch (error) {
    console.error('Failed to copy to clipboard:', error);
    return false;
  }
};

/**
 * Paste workflow from clipboard
 */
export const pasteWorkflowFromClipboard = async (): Promise<ImportResult> => {
  try {
    const data = await navigator.clipboard.readText();
    return importWorkflow(data);
  } catch (error) {
    return {
      success: false,
      errors: [`Failed to paste from clipboard: ${error}`],
      warnings: [],
    };
  }
};

// Helper functions
const validateWorkflowData = (data: any): { errors: string[]; warnings: string[] } => {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Required fields
  if (!data.name) errors.push('Workflow name is required');
  if (!data.steps || !Array.isArray(data.steps)) errors.push('Steps array is required');
  if (!data.connections || !Array.isArray(data.connections)) errors.push('Connections array is required');

  // Optional but recommended fields
  if (!data.description) warnings.push('Workflow description is recommended');
  if (!data.version) warnings.push('Workflow version is recommended');

  // Validate steps
  if (data.steps) {
    data.steps.forEach((step: any, index: number) => {
      if (!step.id) errors.push(`Step ${index + 1}: ID is required`);
      if (!step.name) errors.push(`Step ${index + 1}: Name is required`);
      if (!step.type) errors.push(`Step ${index + 1}: Type is required`);
      if (!step.config) warnings.push(`Step ${index + 1}: Configuration is recommended`);
    });
  }

  // Validate connections
  if (data.connections) {
    data.connections.forEach((conn: any, index: number) => {
      if (!conn.from_step) errors.push(`Connection ${index + 1}: from_step is required`);
      if (!conn.to_step) errors.push(`Connection ${index + 1}: to_step is required`);
    });
  }

  return { errors, warnings };
};

const transformToWorkflow = (data: any): WorkflowDefinition => {
  return {
    name: data.name || 'Imported Workflow',
    description: data.description || '',
    version: data.version || '1.0.0',
    input_variables: data.input_variables || [],
    output_variables: data.output_variables || [],
    steps: data.steps.map((step: any) => ({
      id: step.id,
      name: step.name,
      type: step.type,
      config: step.config || {},
      position: step.position || { x: 0, y: 0 },
      dependencies: step.dependencies || [],
      retry_config: step.retry_config,
    })),
    connections: data.connections.map((conn: any) => ({
      from_step: conn.from_step,
      to_step: conn.to_step,
      condition: conn.condition,
    })),
    start_step: data.start_step || (data.steps.length > 0 ? data.steps[0].id : ''),
    end_steps: data.end_steps || (data.steps.length > 0 ? [data.steps[data.steps.length - 1].id] : []),
    timeout_seconds: data.timeout_seconds,
    retry_policy: data.retry_policy,
    metadata: data.metadata || {},
  };
};

// Simple YAML conversion (in production, use a proper YAML library)
const convertToYAML = (obj: any, indent = 0): string => {
  const spaces = '  '.repeat(indent);
  let yaml = '';

  for (const [key, value] of Object.entries(obj)) {
    if (value === null || value === undefined) continue;

    if (Array.isArray(value)) {
      yaml += `${spaces}${key}:\n`;
      value.forEach(item => {
        if (typeof item === 'object') {
          yaml += `${spaces}- \n${convertToYAML(item, indent + 1)}`;
        } else {
          yaml += `${spaces}- ${item}\n`;
        }
      });
    } else if (typeof value === 'object') {
      yaml += `${spaces}${key}:\n${convertToYAML(value, indent + 1)}`;
    } else {
      yaml += `${spaces}${key}: ${value}\n`;
    }
  }

  return yaml;
};

// Simple YAML parser (in production, use a proper YAML library)
const parseYAML = (yaml: string): any => {
  // This is a very basic YAML parser - in production use js-yaml or similar
  try {
    // For now, assume it's actually JSON
    return JSON.parse(yaml);
  } catch {
    throw new Error('YAML parsing not fully implemented - please use JSON format');
  }
};