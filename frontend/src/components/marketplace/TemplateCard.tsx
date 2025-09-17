import React from 'react';
import { Star, Download, Eye, User, Tag, Calendar, ArrowRight } from 'lucide-react';
import { WorkflowTemplate } from '../../types/workflow';
import { clsx } from 'clsx';

interface TemplateCardProps {
  template: WorkflowTemplate;
  viewMode: 'grid' | 'list';
  onSelect: () => void;
  onInstall: () => void;
}

export const TemplateCard: React.FC<TemplateCardProps> = ({
  template,
  viewMode,
  onSelect,
  onInstall,
}) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
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

  if (viewMode === 'list') {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2 mb-2">
              <h3 className="text-lg font-semibold text-gray-900 truncate">
                {template.name}
              </h3>
              <span className={clsx(
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
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
                  Certified
                </span>
              )}
            </div>

            <p className="text-gray-600 mb-4 line-clamp-2">
              {template.description}
            </p>

            <div className="flex items-center space-x-6 text-sm text-gray-500">
              <div className="flex items-center space-x-1">
                <User className="w-4 h-4" />
                <span>{template.author_name}</span>
              </div>

              <div className="flex items-center space-x-1">
                <Star className="w-4 h-4 text-yellow-400 fill-current" />
                <span>{template.rating_average.toFixed(1)}</span>
                <span>({template.rating_count})</span>
              </div>

              <div className="flex items-center space-x-1">
                <Download className="w-4 h-4" />
                <span>{template.download_count}</span>
              </div>

              <div className="flex items-center space-x-1">
                <Calendar className="w-4 h-4" />
                <span>{formatDate(template.created_at)}</span>
              </div>
            </div>

            {template.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-3">
                {template.tags.slice(0, 5).map(tag => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-700"
                  >
                    <Tag className="w-3 h-3 mr-1" />
                    {tag}
                  </span>
                ))}
                {template.tags.length > 5 && (
                  <span className="text-xs text-gray-500">
                    +{template.tags.length - 5} more
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2 ml-4">
            <button
              onClick={onSelect}
              className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            >
              View Details
            </button>
            <button
              onClick={onInstall}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors flex items-center space-x-1"
            >
              <Download className="w-4 h-4" />
              <span>Install</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Grid view
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow group">
      {/* Template Preview Image */}
      {template.preview_image_url ? (
        <div className="aspect-video bg-gray-100">
          <img
            src={template.preview_image_url}
            alt={template.name}
            className="w-full h-full object-cover"
          />
        </div>
      ) : (
        <div className="aspect-video bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600 mb-2">
              {template.name.charAt(0).toUpperCase()}
            </div>
            <div className="text-xs text-blue-500">
              {template.workflow_definition.steps.length} steps
            </div>
          </div>
        </div>
      )}

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
              {template.name}
            </h3>
            <span className={clsx(
              'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium mt-1',
              getCategoryColor(template.category)
            )}>
              {template.category.replace('_', ' ')}
            </span>
          </div>

          {/* Badges */}
          <div className="flex flex-col space-y-1 ml-2">
            {template.is_featured && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                Featured
              </span>
            )}
            {template.is_certified && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Certified
              </span>
            )}
          </div>
        </div>

        {/* Description */}
        <p className="text-gray-600 text-sm mb-4 line-clamp-2">
          {template.description}
        </p>

        {/* Author */}
        <div className="flex items-center space-x-2 mb-3">
          <User className="w-4 h-4 text-gray-400" />
          <span className="text-sm text-gray-600">{template.author_name}</span>
        </div>

        {/* Stats */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3 text-sm text-gray-500">
            <div className="flex items-center space-x-1">
              <Star className="w-4 h-4 text-yellow-400 fill-current" />
              <span>{template.rating_average.toFixed(1)}</span>
            </div>

            <div className="flex items-center space-x-1">
              <Download className="w-4 h-4" />
              <span>{template.download_count}</span>
            </div>

            <div className="flex items-center space-x-1">
              <Eye className="w-4 h-4" />
              <span>{template.view_count}</span>
            </div>
          </div>

          <div className="text-xs text-gray-500">
            {formatDate(template.created_at)}
          </div>
        </div>

        {/* Tags */}
        {template.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {template.tags.slice(0, 3).map(tag => (
              <span
                key={tag}
                className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-700"
              >
                <Tag className="w-3 h-3 mr-1" />
                {tag}
              </span>
            ))}
            {template.tags.length > 3 && (
              <span className="text-xs text-gray-500">
                +{template.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center space-x-2">
          <button
            onClick={onSelect}
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors flex items-center justify-center space-x-1"
          >
            <span>View Details</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            onClick={onInstall}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors flex items-center space-x-1"
          >
            <Download className="w-4 h-4" />
            <span>Install</span>
          </button>
        </div>
      </div>
    </div>
  );
};