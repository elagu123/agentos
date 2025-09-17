import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Upload, X, Plus, Trash2, Eye, Save, AlertCircle, CheckCircle } from 'lucide-react';
import { WorkflowDefinition } from '../../types/workflow';
import { useCreateTemplate, useUpdateTemplate } from '../../hooks/useMarketplaceAPI';
import { validateWorkflow } from '../../utils/workflowValidation';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';

const templateSchema = z.object({
  name: z.string().min(3, 'Name must be at least 3 characters').max(255, 'Name too long'),
  description: z.string().min(10, 'Description must be at least 10 characters').max(2000, 'Description too long'),
  category: z.string().min(1, 'Please select a category'),
  tags: z.array(z.string()).min(1, 'Please add at least one tag').max(10, 'Maximum 10 tags'),
  workflow_definition: z.object({}).passthrough(),
  version: z.string().regex(/^\d+\.\d+\.\d+$/, 'Version must be in format X.Y.Z'),
  visibility: z.enum(['public', 'organization', 'private']),
  changelog: z.string().optional(),
  preview_image_url: z.string().url().optional().or(z.literal('')),
  search_keywords: z.array(z.string()).max(20, 'Maximum 20 keywords'),
});

type TemplateFormData = z.infer<typeof templateSchema>;

interface TemplatePublisherProps {
  initialWorkflow?: WorkflowDefinition;
  existingTemplate?: any;
  onClose: () => void;
  onSuccess?: (template: any) => void;
}

const CATEGORIES = [
  { value: 'content_creation', label: 'Content Creation' },
  { value: 'customer_support', label: 'Customer Support' },
  { value: 'research_analysis', label: 'Research & Analysis' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'data_processing', label: 'Data Processing' },
  { value: 'automation', label: 'Automation' },
];

const VISIBILITY_OPTIONS = [
  { value: 'public', label: 'Public', description: 'Visible to everyone in the marketplace' },
  { value: 'organization', label: 'Organization', description: 'Only visible to your organization' },
  { value: 'private', label: 'Private', description: 'Only visible to you' },
];

const SUGGESTED_TAGS = [
  'marketing', 'automation', 'content', 'analysis', 'email', 'research',
  'customer-service', 'data-processing', 'lead-generation', 'reporting',
  'scheduling', 'copywriting', 'social-media', 'seo', 'analytics'
];

export const TemplatePublisher: React.FC<TemplatePublisherProps> = ({
  initialWorkflow,
  existingTemplate,
  onClose,
  onSuccess,
}) => {
  const [workflowValidation, setWorkflowValidation] = useState<any>(null);
  const [previewMode, setPreviewMode] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [keywordInput, setKeywordInput] = useState('');

  const isEditing = !!existingTemplate;

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isValid },
    getValues,
  } = useForm<TemplateFormData>({
    resolver: zodResolver(templateSchema),
    defaultValues: {
      name: existingTemplate?.name || '',
      description: existingTemplate?.description || '',
      category: existingTemplate?.category || '',
      tags: existingTemplate?.tags || [],
      workflow_definition: existingTemplate?.workflow_definition || initialWorkflow || {},
      version: existingTemplate?.version || '1.0.0',
      visibility: existingTemplate?.visibility || 'public',
      changelog: existingTemplate?.changelog || '',
      preview_image_url: existingTemplate?.preview_image_url || '',
      search_keywords: existingTemplate?.search_keywords || [],
    },
  });

  const createTemplateMutation = useCreateTemplate();
  const updateTemplateMutation = useUpdateTemplate();

  const watchedValues = watch();

  // Validate workflow on load and changes
  React.useEffect(() => {
    if (watchedValues.workflow_definition) {
      const validation = validateWorkflow(watchedValues.workflow_definition);
      setWorkflowValidation(validation);
    }
  }, [watchedValues.workflow_definition]);

  const handleTagAdd = () => {
    const trimmedTag = tagInput.trim().toLowerCase();
    if (trimmedTag && !watchedValues.tags.includes(trimmedTag) && watchedValues.tags.length < 10) {
      setValue('tags', [...watchedValues.tags, trimmedTag], { shouldValidate: true });
      setTagInput('');
    }
  };

  const handleTagRemove = (tagToRemove: string) => {
    setValue('tags', watchedValues.tags.filter(tag => tag !== tagToRemove), { shouldValidate: true });
  };

  const handleSuggestedTagAdd = (tag: string) => {
    if (!watchedValues.tags.includes(tag) && watchedValues.tags.length < 10) {
      setValue('tags', [...watchedValues.tags, tag], { shouldValidate: true });
    }
  };

  const handleKeywordAdd = () => {
    const trimmedKeyword = keywordInput.trim().toLowerCase();
    if (trimmedKeyword && !watchedValues.search_keywords.includes(trimmedKeyword) && watchedValues.search_keywords.length < 20) {
      setValue('search_keywords', [...watchedValues.search_keywords, trimmedKeyword], { shouldValidate: true });
      setKeywordInput('');
    }
  };

  const handleKeywordRemove = (keywordToRemove: string) => {
    setValue('search_keywords', watchedValues.search_keywords.filter(kw => kw !== keywordToRemove), { shouldValidate: true });
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.type === 'application/json') {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const workflowData = JSON.parse(e.target?.result as string);
          setValue('workflow_definition', workflowData, { shouldValidate: true });
          toast.success('Workflow loaded successfully');
        } catch (error) {
          toast.error('Invalid JSON file');
        }
      };
      reader.readAsText(file);
    } else {
      toast.error('Please upload a JSON file');
    }
  };

  const onSubmit = async (data: TemplateFormData) => {
    try {
      if (isEditing) {
        await updateTemplateMutation.mutateAsync({
          templateId: existingTemplate.id,
          data,
        });
        toast.success('Template updated successfully');
      } else {
        const result = await createTemplateMutation.mutateAsync(data);
        toast.success('Template published successfully');
        onSuccess?.(result.data);
      }
      onClose();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save template');
    }
  };

  const isLoading = createTemplateMutation.isPending || updateTemplateMutation.isPending;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl h-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900">
            {isEditing ? 'Edit Template' : 'Publish Template'}
          </h2>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPreviewMode(!previewMode)}
              className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors flex items-center space-x-2"
            >
              <Eye className="w-4 h-4" />
              <span>{previewMode ? 'Edit' : 'Preview'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {previewMode ? (
            // Preview Mode
            <div className="space-y-6">
              <div className="bg-gray-50 rounded-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-2">{watchedValues.name}</h3>
                <p className="text-gray-600 mb-4">{watchedValues.description}</p>

                <div className="flex items-center space-x-4 mb-4">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                    {CATEGORIES.find(c => c.value === watchedValues.category)?.label}
                  </span>
                  <span className="text-sm text-gray-500">Version {watchedValues.version}</span>
                  <span className="text-sm text-gray-500 capitalize">{watchedValues.visibility}</span>
                </div>

                {watchedValues.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {watchedValues.tags.map(tag => (
                      <span key={tag} className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-700">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Workflow Validation */}
              {workflowValidation && (
                <div className={clsx(
                  'p-4 rounded-lg border',
                  workflowValidation.is_valid
                    ? 'bg-green-50 border-green-200'
                    : 'bg-red-50 border-red-200'
                )}>
                  <div className="flex items-center space-x-2 mb-2">
                    {workflowValidation.is_valid ? (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-600" />
                    )}
                    <h4 className="font-medium">
                      Workflow {workflowValidation.is_valid ? 'Valid' : 'Validation Issues'}
                    </h4>
                  </div>

                  {workflowValidation.errors.length > 0 && (
                    <div className="mb-2">
                      <h5 className="text-sm font-medium text-red-800 mb-1">Errors:</h5>
                      <ul className="text-sm text-red-700 list-disc list-inside">
                        {workflowValidation.errors.map((error: any, index: number) => (
                          <li key={index}>{error.message}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {workflowValidation.warnings.length > 0 && (
                    <div>
                      <h5 className="text-sm font-medium text-yellow-800 mb-1">Warnings:</h5>
                      <ul className="text-sm text-yellow-700 list-disc list-inside">
                        {workflowValidation.warnings.map((warning: any, index: number) => (
                          <li key={index}>{warning.message}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            // Edit Mode
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              {/* Basic Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Template Name *
                  </label>
                  <input
                    type="text"
                    {...register('name')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Enter template name"
                  />
                  {errors.name && (
                    <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Version *
                  </label>
                  <input
                    type="text"
                    {...register('version')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="1.0.0"
                  />
                  {errors.version && (
                    <p className="mt-1 text-sm text-red-600">{errors.version.message}</p>
                  )}
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description *
                </label>
                <textarea
                  {...register('description')}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Describe what this template does and how it helps users..."
                />
                {errors.description && (
                  <p className="mt-1 text-sm text-red-600">{errors.description.message}</p>
                )}
              </div>

              {/* Category and Visibility */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category *
                  </label>
                  <select
                    {...register('category')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">Select a category</option>
                    {CATEGORIES.map(category => (
                      <option key={category.value} value={category.value}>
                        {category.label}
                      </option>
                    ))}
                  </select>
                  {errors.category && (
                    <p className="mt-1 text-sm text-red-600">{errors.category.message}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Visibility *
                  </label>
                  <select
                    {...register('visibility')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  >
                    {VISIBILITY_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-xs text-gray-500">
                    {VISIBILITY_OPTIONS.find(opt => opt.value === watchedValues.visibility)?.description}
                  </p>
                </div>
              </div>

              {/* Tags */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tags * (Help users discover your template)
                </label>
                <div className="space-y-3">
                  {/* Current Tags */}
                  {watchedValues.tags.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {watchedValues.tags.map(tag => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                        >
                          {tag}
                          <button
                            type="button"
                            onClick={() => handleTagRemove(tag)}
                            className="ml-2 hover:text-blue-600"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Add New Tag */}
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleTagAdd())}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Add a tag"
                      maxLength={50}
                    />
                    <button
                      type="button"
                      onClick={handleTagAdd}
                      disabled={!tagInput.trim() || watchedValues.tags.length >= 10}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Suggested Tags */}
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Suggested tags:</p>
                    <div className="flex flex-wrap gap-1">
                      {SUGGESTED_TAGS.filter(tag => !watchedValues.tags.includes(tag)).slice(0, 10).map(tag => (
                        <button
                          key={tag}
                          type="button"
                          onClick={() => handleSuggestedTagAdd(tag)}
                          disabled={watchedValues.tags.length >= 10}
                          className="px-2 py-1 text-xs border border-gray-300 rounded hover:border-blue-300 hover:text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {tag}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                {errors.tags && (
                  <p className="mt-1 text-sm text-red-600">{errors.tags.message}</p>
                )}
              </div>

              {/* Search Keywords */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Search Keywords (Optional)
                </label>
                <div className="space-y-3">
                  {/* Current Keywords */}
                  {watchedValues.search_keywords.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {watchedValues.search_keywords.map(keyword => (
                        <span
                          key={keyword}
                          className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-700"
                        >
                          {keyword}
                          <button
                            type="button"
                            onClick={() => handleKeywordRemove(keyword)}
                            className="ml-1 hover:text-gray-600"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Add New Keyword */}
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={keywordInput}
                      onChange={(e) => setKeywordInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleKeywordAdd())}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Add search keyword"
                      maxLength={50}
                    />
                    <button
                      type="button"
                      onClick={handleKeywordAdd}
                      disabled={!keywordInput.trim() || watchedValues.search_keywords.length >= 20}
                      className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Workflow Upload */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Workflow Definition *
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
                  <div className="text-center">
                    <Upload className="mx-auto h-12 w-12 text-gray-400" />
                    <div className="mt-4">
                      <label className="cursor-pointer">
                        <span className="text-blue-600 hover:text-blue-500">Upload a JSON file</span>
                        <input
                          type="file"
                          accept=".json"
                          onChange={handleFileUpload}
                          className="sr-only"
                        />
                      </label>
                      <p className="text-sm text-gray-500">or drag and drop</p>
                    </div>
                  </div>

                  {watchedValues.workflow_definition && Object.keys(watchedValues.workflow_definition).length > 0 && (
                    <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded">
                      <p className="text-sm text-green-700">
                        ✓ Workflow loaded ({(watchedValues.workflow_definition as any).steps?.length || 0} steps)
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Optional Fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Preview Image URL (Optional)
                  </label>
                  <input
                    type="url"
                    {...register('preview_image_url')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="https://example.com/preview.png"
                  />
                  {errors.preview_image_url && (
                    <p className="mt-1 text-sm text-red-600">{errors.preview_image_url.message}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Changelog (Optional)
                  </label>
                  <textarea
                    {...register('changelog')}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="What's new in this version..."
                  />
                </div>
              </div>
            </form>
          )}
        </div>

        {/* Footer */}
        {!previewMode && (
          <div className="flex items-center justify-between p-6 border-t border-gray-200">
            <div className="text-sm text-gray-500">
              {workflowValidation && !workflowValidation.is_valid && (
                <span className="text-red-600">
                  Please fix workflow validation errors before publishing
                </span>
              )}
            </div>
            <div className="flex items-center space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit(onSubmit)}
                disabled={!isValid || !workflowValidation?.is_valid || isLoading}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
              >
                <Save className="w-4 h-4" />
                <span>{isLoading ? 'Publishing...' : isEditing ? 'Update Template' : 'Publish Template'}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};