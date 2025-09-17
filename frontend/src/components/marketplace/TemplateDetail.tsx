import React, { useState } from 'react';
import {
  X, Star, Download, Eye, Calendar, User, Tag, Share2,
  Flag, Heart, ArrowRight, CheckCircle, AlertCircle, Play
} from 'lucide-react';
import { WorkflowTemplate } from '../../types/workflow';
import { useTemplateRatings, useCreateRating } from '../../hooks/useMarketplaceAPI';
import { ReviewsList } from './ReviewsList';
import { RatingForm } from './RatingForm';
import { TemplatePreview } from './TemplatePreview';
import { clsx } from 'clsx';
import toast from 'react-hot-toast';

interface TemplateDetailProps {
  template: WorkflowTemplate;
  onClose: () => void;
  onInstall: (template: WorkflowTemplate) => void;
  onReport?: (template: WorkflowTemplate) => void;
}

export const TemplateDetail: React.FC<TemplateDetailProps> = ({
  template,
  onClose,
  onInstall,
  onReport,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'reviews' | 'preview'>('overview');
  const [showRatingForm, setShowRatingForm] = useState(false);

  const { data: ratingsData, isLoading: ratingsLoading } = useTemplateRatings(template.id);
  const createRatingMutation = useCreateRating();

  const ratings = ratingsData?.ratings || [];

  const handleRatingSubmit = async (ratingData: any) => {
    try {
      await createRatingMutation.mutateAsync({
        templateId: template.id,
        ...ratingData,
      });
      toast.success('Rating submitted successfully');
      setShowRatingForm(false);
    } catch (error) {
      toast.error('Failed to submit rating');
    }
  };

  const handleShare = async () => {
    try {
      await navigator.share({
        title: template.name,
        text: template.description,
        url: window.location.href,
      });
    } catch (error) {
      // Fallback to clipboard
      navigator.clipboard.writeText(window.location.href);
      toast.success('Link copied to clipboard');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getCategoryColor = (category: string) => {
    const colors = {
      'content_creation': 'bg-purple-100 text-purple-800',
      'customer_support': 'bg-blue-100 text-blue-800',
      'research_analysis': 'bg-green-100 text-green-800',
      'marketing': 'bg-orange-100 text-orange-800',
      'data_processing': 'bg-red-100 text-red-800',
      'automation': 'bg-indigo-100 text-indigo-800',
    };
    return colors[category as keyof typeof colors] || 'bg-gray-100 text-gray-800';
  };

  const renderStars = (rating: number, size: 'sm' | 'md' | 'lg' = 'md') => {
    const sizeClasses = {
      sm: 'w-3 h-3',
      md: 'w-4 h-4',
      lg: 'w-5 h-5',
    };

    return (
      <div className="flex items-center">
        {Array.from({ length: 5 }, (_, i) => (
          <Star
            key={i}
            className={clsx(
              sizeClasses[size],
              i < Math.floor(rating)
                ? 'text-yellow-400 fill-current'
                : 'text-gray-300'
            )}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl h-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-4 flex-1 min-w-0">
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold text-gray-900 truncate">
                {template.name}
              </h1>
              <div className="flex items-center space-x-3 mt-2">
                <span className={clsx(
                  'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium',
                  getCategoryColor(template.category)
                )}>
                  {template.category.replace('_', ' ')}
                </span>
                {template.is_featured && (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    Featured
                  </span>
                )}
                {template.is_certified && (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Certified
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={handleShare}
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                title="Share template"
              >
                <Share2 className="w-5 h-5" />
              </button>
              {onReport && (
                <button
                  onClick={() => onReport(template)}
                  className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                  title="Report template"
                >
                  <Flag className="w-5 h-5" />
                </button>
              )}
              <button
                onClick={onClose}
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>

        {/* Stats Bar */}
        <div className="flex items-center justify-between px-6 py-4 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-2">
              <User className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-600">{template.author_name}</span>
            </div>

            <div className="flex items-center space-x-2">
              {renderStars(template.rating_average)}
              <span className="text-sm font-medium">{template.rating_average.toFixed(1)}</span>
              <span className="text-sm text-gray-500">({template.rating_count} reviews)</span>
            </div>

            <div className="flex items-center space-x-2">
              <Download className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-600">{template.download_count} downloads</span>
            </div>

            <div className="flex items-center space-x-2">
              <Eye className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-600">{template.view_count} views</span>
            </div>

            <div className="flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-600">{formatDate(template.created_at)}</span>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {!showRatingForm && (
              <button
                onClick={() => setShowRatingForm(true)}
                className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Write Review
              </button>
            )}
            <button
              onClick={() => onInstall(template)}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors flex items-center space-x-2"
            >
              <Download className="w-4 h-4" />
              <span>Install Template</span>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          {[
            { id: 'overview', label: 'Overview' },
            { id: 'reviews', label: `Reviews (${template.rating_count})` },
            { id: 'preview', label: 'Preview Workflow' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={clsx(
                'px-6 py-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'overview' && (
            <div className="p-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Content */}
                <div className="lg:col-span-2 space-y-6">
                  {/* Description */}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">Description</h3>
                    <p className="text-gray-700 leading-relaxed">{template.description}</p>
                  </div>

                  {/* Workflow Steps Preview */}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">
                      Workflow Steps ({template.workflow_definition.steps.length})
                    </h3>
                    <div className="space-y-3">
                      {template.workflow_definition.steps.slice(0, 5).map((step, index) => (
                        <div key={step.id} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                          <div className="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-medium">
                            {index + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium text-gray-900">{step.name}</h4>
                            <p className="text-sm text-gray-600 capitalize">
                              {step.type.replace('_', ' ')}
                              {step.config.agent_type && ` - ${step.config.agent_type}`}
                            </p>
                          </div>
                          {index < template.workflow_definition.steps.length - 1 && (
                            <ArrowRight className="w-4 h-4 text-gray-400" />
                          )}
                        </div>
                      ))}
                      {template.workflow_definition.steps.length > 5 && (
                        <div className="text-center py-2">
                          <span className="text-sm text-gray-500">
                            +{template.workflow_definition.steps.length - 5} more steps
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Changelog */}
                  {template.changelog && (
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-3">Changelog</h3>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="flex items-center space-x-2 mb-2">
                          <span className="text-sm font-medium text-gray-900">
                            Version {template.version}
                          </span>
                          <span className="text-sm text-gray-500">
                            {formatDate(template.updated_at)}
                          </span>
                        </div>
                        <p className="text-sm text-gray-700">{template.changelog}</p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Sidebar */}
                <div className="space-y-6">
                  {/* Tags */}
                  {template.tags.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-3">Tags</h3>
                      <div className="flex flex-wrap gap-2">
                        {template.tags.map(tag => (
                          <span
                            key={tag}
                            className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                          >
                            <Tag className="w-3 h-3 mr-1" />
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Technical Details */}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">Technical Details</h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Version:</span>
                        <span className="font-medium">{template.version}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Steps:</span>
                        <span className="font-medium">{template.workflow_definition.steps.length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Connections:</span>
                        <span className="font-medium">{template.workflow_definition.connections.length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Input Variables:</span>
                        <span className="font-medium">{template.workflow_definition.input_variables.length}</span>
                      </div>
                    </div>
                  </div>

                  {/* Author Info */}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">Author</h3>
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                        <User className="w-5 h-5 text-gray-600" />
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">{template.author_name}</div>
                        <div className="text-sm text-gray-600">Template Author</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'reviews' && (
            <div className="p-6">
              {showRatingForm && (
                <div className="mb-6">
                  <RatingForm
                    onSubmit={handleRatingSubmit}
                    onCancel={() => setShowRatingForm(false)}
                    isSubmitting={createRatingMutation.isPending}
                  />
                </div>
              )}
              <ReviewsList
                ratings={ratings}
                isLoading={ratingsLoading}
                templateRating={template.rating_average}
                templateRatingCount={template.rating_count}
              />
            </div>
          )}

          {activeTab === 'preview' && (
            <div className="p-6">
              <TemplatePreview
                workflowDefinition={template.workflow_definition}
                templateName={template.name}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};