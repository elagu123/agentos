import React from 'react';
import { Star, ThumbsUp, ThumbsDown, User, Calendar, Briefcase, Users as UsersIcon } from 'lucide-react';
import { clsx } from 'clsx';

interface Rating {
  id: string;
  rating: number;
  review_title?: string;
  review_text?: string;
  use_case?: string;
  industry?: string;
  team_size?: string;
  helpful_count: number;
  not_helpful_count: number;
  created_at: string;
  user_name: string;
  is_verified_purchase: boolean;
}

interface ReviewsListProps {
  ratings: Rating[];
  isLoading: boolean;
  templateRating: number;
  templateRatingCount: number;
}

export const ReviewsList: React.FC<ReviewsListProps> = ({
  ratings,
  isLoading,
  templateRating,
  templateRatingCount,
}) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const renderStars = (rating: number, size: 'sm' | 'md' = 'sm') => {
    const sizeClasses = {
      sm: 'w-4 h-4',
      md: 'w-5 h-5',
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

  const getRatingDistribution = () => {
    const distribution = [0, 0, 0, 0, 0]; // 1-5 stars
    ratings.forEach(rating => {
      if (rating.rating >= 1 && rating.rating <= 5) {
        distribution[rating.rating - 1]++;
      }
    });
    return distribution.reverse(); // 5-1 stars for display
  };

  const ratingDistribution = getRatingDistribution();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading reviews...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Rating Summary */}
      <div className="bg-gray-50 rounded-lg p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Overall Rating */}
          <div className="text-center md:text-left">
            <div className="flex items-center justify-center md:justify-start space-x-2 mb-2">
              <span className="text-4xl font-bold text-gray-900">
                {templateRating.toFixed(1)}
              </span>
              {renderStars(templateRating, 'md')}
            </div>
            <p className="text-gray-600">
              Based on {templateRatingCount} {templateRatingCount === 1 ? 'review' : 'reviews'}
            </p>
          </div>

          {/* Rating Distribution */}
          <div className="space-y-2">
            {[5, 4, 3, 2, 1].map((stars, index) => {
              const count = ratingDistribution[index];
              const percentage = templateRatingCount > 0 ? (count / templateRatingCount) * 100 : 0;

              return (
                <div key={stars} className="flex items-center space-x-3">
                  <div className="flex items-center space-x-1 w-16">
                    <span className="text-sm font-medium">{stars}</span>
                    <Star className="w-3 h-3 text-yellow-400 fill-current" />
                  </div>
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-yellow-400 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600 w-8">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Reviews List */}
      {ratings.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-gray-600">No reviews yet. Be the first to review this template!</p>
        </div>
      ) : (
        <div className="space-y-6">
          {ratings.map((rating) => (
            <div key={rating.id} className="border border-gray-200 rounded-lg p-6">
              {/* Review Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start space-x-4">
                  <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                    <User className="w-5 h-5 text-gray-600" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h4 className="font-medium text-gray-900">{rating.user_name}</h4>
                      {rating.is_verified_purchase && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          Verified
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-3 mt-1">
                      {renderStars(rating.rating)}
                      <span className="text-sm text-gray-500">
                        {formatDate(rating.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Review Title */}
              {rating.review_title && (
                <h5 className="text-lg font-medium text-gray-900 mb-2">
                  {rating.review_title}
                </h5>
              )}

              {/* Review Text */}
              {rating.review_text && (
                <p className="text-gray-700 leading-relaxed mb-4">
                  {rating.review_text}
                </p>
              )}

              {/* Review Context */}
              {(rating.use_case || rating.industry || rating.team_size) && (
                <div className="flex flex-wrap gap-4 mb-4 text-sm text-gray-600">
                  {rating.use_case && (
                    <div className="flex items-center space-x-1">
                      <Briefcase className="w-4 h-4" />
                      <span>Use case: {rating.use_case}</span>
                    </div>
                  )}
                  {rating.industry && (
                    <div className="flex items-center space-x-1">
                      <Briefcase className="w-4 h-4" />
                      <span>Industry: {rating.industry}</span>
                    </div>
                  )}
                  {rating.team_size && (
                    <div className="flex items-center space-x-1">
                      <UsersIcon className="w-4 h-4" />
                      <span>Team size: {rating.team_size}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Helpfulness */}
              <div className="flex items-center space-x-4 pt-4 border-t border-gray-100">
                <span className="text-sm text-gray-600">Was this review helpful?</span>
                <div className="flex items-center space-x-2">
                  <button className="flex items-center space-x-1 px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
                    <ThumbsUp className="w-3 h-3" />
                    <span>{rating.helpful_count}</span>
                  </button>
                  <button className="flex items-center space-x-1 px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
                    <ThumbsDown className="w-3 h-3" />
                    <span>{rating.not_helpful_count}</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};