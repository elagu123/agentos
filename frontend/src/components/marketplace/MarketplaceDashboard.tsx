import React, { useState, useMemo } from 'react';
import { Search, Filter, Star, Download, Eye, TrendingUp, Grid, List } from 'lucide-react';
import { useTemplates, useTemplateCategories, useMarketplaceStats } from '../../hooks/useMarketplaceAPI';
import { TemplateCard } from './TemplateCard';
import { TemplateFilters } from './TemplateFilters';
import { MarketplaceStats } from './MarketplaceStats';
import { WorkflowTemplate } from '../../types/workflow';
import { clsx } from 'clsx';

interface MarketplaceDashboardProps {
  onTemplateSelect: (template: WorkflowTemplate) => void;
  onTemplateInstall: (template: WorkflowTemplate) => void;
}

export const MarketplaceDashboard: React.FC<MarketplaceDashboardProps> = ({
  onTemplateSelect,
  onTemplateInstall,
}) => {
  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [minRating, setMinRating] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<string>('desc');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage] = useState(1);

  // Build search params
  const searchParams = useMemo(() => ({
    query: searchQuery || undefined,
    category: selectedCategory === 'all' ? undefined : selectedCategory,
    tags: selectedTags.length > 0 ? selectedTags : undefined,
    min_rating: minRating,
    sort_by: sortBy,
    sort_order: sortOrder,
    page,
    page_size: 20,
  }), [searchQuery, selectedCategory, selectedTags, minRating, sortBy, sortOrder, page]);

  // API hooks
  const { data: templatesData, isLoading, error } = useTemplates(searchParams);
  const { data: categories = [] } = useTemplateCategories();
  const { data: stats } = useMarketplaceStats();

  const templates = templatesData?.templates || [];
  const pagination = templatesData?.pagination;

  // Filter handlers
  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
    setPage(1);
  };

  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
    setPage(1);
  };

  const handleTagsChange = (tags: string[]) => {
    setSelectedTags(tags);
    setPage(1);
  };

  const handleRatingChange = (rating: number | null) => {
    setMinRating(rating);
    setPage(1);
  };

  const handleSortChange = (newSortBy: string, newSortOrder: string) => {
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
    setPage(1);
  };

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedCategory('all');
    setSelectedTags([]);
    setMinRating(null);
    setSortBy('created_at');
    setSortOrder('desc');
    setPage(1);
  };

  const hasActiveFilters = searchQuery || selectedCategory !== 'all' || selectedTags.length > 0 || minRating !== null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <div className="flex flex-col space-y-4 md:flex-row md:items-center md:justify-between md:space-y-0">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Template Marketplace</h1>
                <p className="mt-2 text-gray-600">
                  Discover and install workflow templates created by the community
                </p>
              </div>

              {/* View Toggle */}
              <div className="flex items-center space-x-2">
                <div className="flex rounded-lg border border-gray-300 p-1">
                  <button
                    onClick={() => setViewMode('grid')}
                    className={clsx(
                      'p-2 rounded-md transition-colors',
                      viewMode === 'grid'
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-500 hover:text-gray-700'
                    )}
                  >
                    <Grid className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => setViewMode('list')}
                    className={clsx(
                      'p-2 rounded-md transition-colors',
                      viewMode === 'list'
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-500 hover:text-gray-700'
                    )}
                  >
                    <List className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>

            {/* Marketplace Stats */}
            {stats && <MarketplaceStats stats={stats} />}

            {/* Search and Filters */}
            <div className="mt-6 space-y-4">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search templates..."
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              {/* Filter Controls */}
              <div className="flex flex-col space-y-2 sm:flex-row sm:items-center sm:justify-between sm:space-y-0">
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={clsx(
                      'flex items-center space-x-2 px-4 py-2 border rounded-lg transition-colors',
                      showFilters
                        ? 'border-blue-300 bg-blue-50 text-blue-700'
                        : 'border-gray-300 hover:bg-gray-50'
                    )}
                  >
                    <Filter className="w-4 h-4" />
                    <span>Filters</span>
                    {hasActiveFilters && (
                      <span className="bg-blue-600 text-white text-xs rounded-full px-2 py-0.5">
                        {[
                          searchQuery && 'search',
                          selectedCategory !== 'all' && 'category',
                          selectedTags.length > 0 && 'tags',
                          minRating && 'rating'
                        ].filter(Boolean).length}
                      </span>
                    )}
                  </button>

                  {hasActiveFilters && (
                    <button
                      onClick={clearFilters}
                      className="text-sm text-gray-500 hover:text-gray-700"
                    >
                      Clear filters
                    </button>
                  )}
                </div>

                {/* Sort Controls */}
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-600">Sort by:</span>
                  <select
                    value={`${sortBy}-${sortOrder}`}
                    onChange={(e) => {
                      const [newSortBy, newSortOrder] = e.target.value.split('-');
                      handleSortChange(newSortBy, newSortOrder);
                    }}
                    className="text-sm border border-gray-300 rounded px-3 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="created_at-desc">Newest First</option>
                    <option value="created_at-asc">Oldest First</option>
                    <option value="rating_average-desc">Highest Rated</option>
                    <option value="download_count-desc">Most Downloaded</option>
                    <option value="name-asc">Name A-Z</option>
                    <option value="name-desc">Name Z-A</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <TemplateFilters
          categories={categories}
          selectedCategory={selectedCategory}
          selectedTags={selectedTags}
          minRating={minRating}
          onCategoryChange={handleCategoryChange}
          onTagsChange={handleTagsChange}
          onRatingChange={handleRatingChange}
        />
      )}

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-2 text-gray-600">Loading templates...</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="text-center py-12">
            <div className="text-red-600 mb-2">Failed to load templates</div>
            <button
              onClick={() => window.location.reload()}
              className="text-blue-600 hover:text-blue-700"
            >
              Try again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && templates.length === 0 && (
          <div className="text-center py-12">
            <div className="text-gray-500 mb-2">
              {hasActiveFilters ? 'No templates match your filters' : 'No templates available'}
            </div>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-blue-600 hover:text-blue-700"
              >
                Clear filters
              </button>
            )}
          </div>
        )}

        {/* Templates Grid */}
        {!isLoading && !error && templates.length > 0 && (
          <>
            <div className="mb-4 text-sm text-gray-600">
              Showing {templates.length} of {pagination?.total_count || 0} templates
            </div>

            <div className={clsx(
              viewMode === 'grid'
                ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6'
                : 'space-y-4'
            )}>
              {templates.map((template) => (
                <TemplateCard
                  key={template.id}
                  template={template}
                  viewMode={viewMode}
                  onSelect={() => onTemplateSelect(template)}
                  onInstall={() => onTemplateInstall(template)}
                />
              ))}
            </div>

            {/* Pagination */}
            {pagination && pagination.total_pages > 1 && (
              <div className="mt-8 flex items-center justify-center space-x-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="px-3 py-2 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                >
                  Previous
                </button>

                <div className="flex space-x-1">
                  {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                    const pageNum = Math.max(1, Math.min(
                      pagination.total_pages - 4,
                      page - 2
                    )) + i;

                    return (
                      <button
                        key={pageNum}
                        onClick={() => setPage(pageNum)}
                        className={clsx(
                          'px-3 py-2 border border-gray-300 rounded-md',
                          page === pageNum
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'hover:bg-gray-50'
                        )}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>

                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= pagination.total_pages}
                  className="px-3 py-2 border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};