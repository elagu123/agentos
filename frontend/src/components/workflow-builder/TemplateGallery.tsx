import React, { useState } from 'react';
import { X, Search, Star, Download, Tag, Clock, User, ArrowRight } from 'lucide-react';
import { WorkflowTemplate } from '../../types/workflow';
import { useTemplates, useInstallTemplate } from '../../hooks/useWorkflowAPI';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';

interface TemplateGalleryProps {
  onClose: () => void;
  onSelectTemplate: (template: WorkflowTemplate) => void;
}

const CATEGORIES = [
  { id: 'all', label: 'All Templates', color: 'text-gray-600' },
  { id: 'content_creation', label: 'Content Creation', color: 'text-purple-600' },
  { id: 'customer_support', label: 'Customer Support', color: 'text-blue-600' },
  { id: 'research_analysis', label: 'Research & Analysis', color: 'text-green-600' },
  { id: 'marketing', label: 'Marketing', color: 'text-orange-600' },
  { id: 'data_processing', label: 'Data Processing', color: 'text-red-600' },
  { id: 'automation', label: 'Automation', color: 'text-indigo-600' },
];

export const TemplateGallery: React.FC<TemplateGalleryProps> = ({
  onClose,
  onSelectTemplate,
}) => {
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(null);

  const { data: templates = [], isLoading } = useTemplates({
    category: selectedCategory === 'all' ? undefined : selectedCategory,
    search: searchQuery || undefined,
  });

  const installTemplateMutation = useInstallTemplate();

  const handleInstallTemplate = async (template: WorkflowTemplate) => {
    try {
      const result = await installTemplateMutation.mutateAsync({
        templateId: template.id,
      });

      onSelectTemplate({
        ...template,
        workflow_definition: result.data,
      });

      toast.success(`Template "${template.name}" installed successfully`);
    } catch (error) {
      toast.error('Failed to install template');
      console.error('Install error:', error);
    }
  };

  const filteredTemplates = templates.filter(template => {
    const matchesSearch = !searchQuery ||
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCategory = selectedCategory === 'all' || template.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatDuration = (steps: number) => {
    return `~${steps * 30}s`;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl h-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Template Gallery</h2>
            <p className="text-gray-600 mt-1">Choose from pre-built workflow templates</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Search and Filters */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center space-x-4 mb-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search templates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Category Filter */}
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map(category => (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.id)}
                className={clsx(
                  'px-4 py-2 rounded-full text-sm font-medium transition-colors',
                  selectedCategory === category.id
                    ? 'bg-blue-100 text-blue-700 border border-blue-200'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                )}
              >
                {category.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Template List */}
          <div className="w-1/2 border-r border-gray-200 overflow-y-auto">
            {isLoading ? (
              <div className="p-6 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                <p className="text-gray-600 mt-2">Loading templates...</p>
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="p-6 text-center">
                <p className="text-gray-600">No templates found</p>
              </div>
            ) : (
              <div className="p-6 space-y-4">
                {filteredTemplates.map(template => (
                  <div
                    key={template.id}
                    onClick={() => setSelectedTemplate(template)}
                    className={clsx(
                      'p-4 border rounded-lg cursor-pointer transition-all hover:shadow-md',
                      selectedTemplate?.id === template.id
                        ? 'border-blue-300 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    )}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold text-gray-900">{template.name}</h3>
                      <div className="flex items-center space-x-1 text-sm text-gray-500">
                        <Star className="w-4 h-4 text-yellow-400 fill-current" />
                        <span>{template.rating.toFixed(1)}</span>
                      </div>
                    </div>

                    <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                      {template.description}
                    </p>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3 text-sm text-gray-500">
                        <div className="flex items-center space-x-1">
                          <User className="w-4 h-4" />
                          <span>{template.author}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <Download className="w-4 h-4" />
                          <span>{template.downloads}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <Clock className="w-4 h-4" />
                          <span>{formatDuration(template.workflow_definition.steps.length)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-1 mt-2">
                      {template.tags.slice(0, 3).map(tag => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                        >
                          <Tag className="w-3 h-3 mr-1" />
                          {tag}
                        </span>
                      ))}
                      {template.tags.length > 3 && (
                        <span className="text-xs text-gray-500">
                          +{template.tags.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Template Details */}
          <div className="w-1/2 overflow-y-auto">
            {selectedTemplate ? (
              <div className="p-6">
                <div className="mb-6">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">
                    {selectedTemplate.name}
                  </h3>
                  <p className="text-gray-600 mb-4">
                    {selectedTemplate.description}
                  </p>

                  <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
                    <div>
                      <span className="font-medium text-gray-700">Author:</span>
                      <span className="ml-2 text-gray-600">{selectedTemplate.author}</span>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Category:</span>
                      <span className="ml-2 text-gray-600 capitalize">
                        {selectedTemplate.category.replace('_', ' ')}
                      </span>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Downloads:</span>
                      <span className="ml-2 text-gray-600">{selectedTemplate.downloads}</span>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Updated:</span>
                      <span className="ml-2 text-gray-600">
                        {formatDate(selectedTemplate.updated_at)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 mb-4">
                    <Star className="w-5 h-5 text-yellow-400 fill-current" />
                    <span className="font-medium">{selectedTemplate.rating.toFixed(1)}</span>
                    <span className="text-gray-500 text-sm">rating</span>
                  </div>
                </div>

                {/* Workflow Steps Preview */}
                <div className="mb-6">
                  <h4 className="font-semibold text-gray-900 mb-3">Workflow Steps</h4>
                  <div className="space-y-2">
                    {selectedTemplate.workflow_definition.steps.map((step, index) => (
                      <div key={step.id} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                        <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-medium">
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <h5 className="font-medium text-gray-900">{step.name}</h5>
                          <p className="text-sm text-gray-600 capitalize">
                            {step.type.replace('_', ' ')}
                            {step.config.agent_type && ` - ${step.config.agent_type}`}
                          </p>
                        </div>
                        {index < selectedTemplate.workflow_definition.steps.length - 1 && (
                          <ArrowRight className="w-4 h-4 text-gray-400" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Tags */}
                <div className="mb-6">
                  <h4 className="font-semibold text-gray-900 mb-3">Tags</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedTemplate.tags.map(tag => (
                      <span
                        key={tag}
                        className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800"
                      >
                        <Tag className="w-3 h-3 mr-1" />
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Action Button */}
                <button
                  onClick={() => handleInstallTemplate(selectedTemplate)}
                  disabled={installTemplateMutation.isPending}
                  className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
                >
                  {installTemplateMutation.isPending ? 'Installing...' : 'Use This Template'}
                </button>
              </div>
            ) : (
              <div className="p-6 flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Search className="w-8 h-8 text-gray-400" />
                  </div>
                  <p className="text-gray-600">Select a template to see details</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};