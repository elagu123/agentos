import React from 'react';
import { Star, X } from 'lucide-react';
import { clsx } from 'clsx';

interface TemplateFiltersProps {
  categories: Array<{ category: string; count: number; slug: string }>;
  selectedCategory: string;
  selectedTags: string[];
  minRating: number | null;
  onCategoryChange: (category: string) => void;
  onTagsChange: (tags: string[]) => void;
  onRatingChange: (rating: number | null) => void;
}

const POPULAR_TAGS = [
  'marketing', 'automation', 'content', 'analysis', 'email', 'research',
  'customer-service', 'data-processing', 'lead-generation', 'reporting'
];

const RATING_OPTIONS = [
  { value: 4, label: '4+ Stars' },
  { value: 3, label: '3+ Stars' },
  { value: 2, label: '2+ Stars' },
  { value: 1, label: '1+ Stars' },
];

export const TemplateFilters: React.FC<TemplateFiltersProps> = ({
  categories,
  selectedCategory,
  selectedTags,
  minRating,
  onCategoryChange,
  onTagsChange,
  onRatingChange,
}) => {
  const handleTagToggle = (tag: string) => {
    if (selectedTags.includes(tag)) {
      onTagsChange(selectedTags.filter(t => t !== tag));
    } else {
      onTagsChange([...selectedTags, tag]);
    }
  };

  const handleTagRemove = (tag: string) => {
    onTagsChange(selectedTags.filter(t => t !== tag));
  };

  return (
    <div className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Categories */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Categories</h3>
            <div className="space-y-2">
              <button
                onClick={() => onCategoryChange('all')}
                className={clsx(
                  'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
                  selectedCategory === 'all'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                All Categories
              </button>
              {categories.map(category => (
                <button
                  key={category.category}
                  onClick={() => onCategoryChange(category.category)}
                  className={clsx(
                    'w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex justify-between',
                    selectedCategory === category.category
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <span>{category.category.replace('_', ' ')}</span>
                  <span className="text-gray-400">{category.count}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Tags */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Tags</h3>

            {/* Selected Tags */}
            {selectedTags.length > 0 && (
              <div className="mb-3">
                <div className="flex flex-wrap gap-2">
                  {selectedTags.map(tag => (
                    <span
                      key={tag}
                      className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                    >
                      {tag}
                      <button
                        onClick={() => handleTagRemove(tag)}
                        className="ml-2 hover:text-blue-600"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Available Tags */}
            <div className="flex flex-wrap gap-2">
              {POPULAR_TAGS.filter(tag => !selectedTags.includes(tag)).map(tag => (
                <button
                  key={tag}
                  onClick={() => handleTagToggle(tag)}
                  className="px-3 py-1 rounded-full text-sm border border-gray-300 text-gray-700 hover:border-blue-300 hover:text-blue-700 transition-colors"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          {/* Rating Filter */}
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Minimum Rating</h3>
            <div className="space-y-2">
              <button
                onClick={() => onRatingChange(null)}
                className={clsx(
                  'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
                  minRating === null
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                Any Rating
              </button>
              {RATING_OPTIONS.map(option => (
                <button
                  key={option.value}
                  onClick={() => onRatingChange(option.value)}
                  className={clsx(
                    'w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center space-x-2',
                    minRating === option.value
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <div className="flex items-center">
                    {Array.from({ length: 5 }, (_, i) => (
                      <Star
                        key={i}
                        className={clsx(
                          'w-4 h-4',
                          i < option.value
                            ? 'text-yellow-400 fill-current'
                            : 'text-gray-300'
                        )}
                      />
                    ))}
                  </div>
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};