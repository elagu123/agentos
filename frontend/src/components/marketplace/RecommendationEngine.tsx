import React, { useState } from 'react';
import {
  Sparkles,
  TrendingUp,
  Users,
  Clock,
  Star,
  Download,
  ThumbsUp,
  ArrowRight,
  Filter,
  Target,
  Brain,
  Lightbulb
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';

interface RecommendedTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  rating: number;
  download_count: number;
  author_name: string;
  recommendation_score: number;
  recommendation_reasons: string[];
  preview_image_url?: string;
  tags: string[];
  estimated_setup_time: number;
  difficulty_level: 'beginner' | 'intermediate' | 'advanced';
}

interface UserProfile {
  industry: string;
  team_size: string;
  experience_level: string;
  interests: string[];
  recent_downloads: string[];
  usage_patterns: {
    preferred_categories: string[];
    avg_complexity: string;
    time_of_day: string;
  };
}

interface RecommendationEngineProps {
  userId?: string;
  currentTemplate?: string;
  context?: 'browse' | 'post-install' | 'similar' | 'trending';
}

export const RecommendationEngine: React.FC<RecommendationEngineProps> = ({
  userId,
  currentTemplate,
  context = 'browse'
}) => {
  const [recommendationType, setRecommendationType] = useState<'personalized' | 'trending' | 'similar' | 'collaborative'>('personalized');

  const { data: userProfile } = useQuery({
    queryKey: ['user-profile', userId],
    queryFn: async (): Promise<UserProfile | null> => {
      if (!userId) return null;

      // Mock user profile data
      return {
        industry: 'Technology',
        team_size: '11-50',
        experience_level: 'intermediate',
        interests: ['automation', 'customer_service', 'analytics'],
        recent_downloads: ['template-1', 'template-3', 'template-7'],
        usage_patterns: {
          preferred_categories: ['Customer Service', 'Analytics', 'Marketing'],
          avg_complexity: 'intermediate',
          time_of_day: 'morning'
        }
      };
    },
    enabled: !!userId
  });

  const { data: recommendations = [], isLoading } = useQuery({
    queryKey: ['recommendations', userId, recommendationType, currentTemplate, context],
    queryFn: async (): Promise<RecommendedTemplate[]> => {
      // Mock recommendation data based on type
      const baseRecommendations: RecommendedTemplate[] = [
        {
          id: 'rec-1',
          name: 'Advanced Customer Analytics',
          description: 'Comprehensive customer behavior analysis and reporting system',
          category: 'Analytics',
          rating: 4.8,
          download_count: 1250,
          author_name: 'DataPro Solutions',
          recommendation_score: 0.92,
          recommendation_reasons: [
            'Matches your interest in analytics',
            'Popular in your industry',
            'Similar complexity to your recent downloads'
          ],
          tags: ['analytics', 'customer-service', 'reporting'],
          estimated_setup_time: 15,
          difficulty_level: 'intermediate'
        },
        {
          id: 'rec-2',
          name: 'Smart Email Automation',
          description: 'AI-powered email campaigns with personalization and optimization',
          category: 'Marketing',
          rating: 4.6,
          download_count: 890,
          author_name: 'Marketing Wizards',
          recommendation_score: 0.87,
          recommendation_reasons: [
            'Trending in your team size category',
            'High success rate for intermediate users',
            'Complements your existing workflows'
          ],
          tags: ['email', 'automation', 'marketing', 'ai'],
          estimated_setup_time: 20,
          difficulty_level: 'intermediate'
        },
        {
          id: 'rec-3',
          name: 'Support Ticket Classifier',
          description: 'Automatically categorize and prioritize customer support tickets',
          category: 'Customer Service',
          rating: 4.9,
          download_count: 2100,
          author_name: 'Support Hero',
          recommendation_score: 0.85,
          recommendation_reasons: [
            'Perfect match for customer service focus',
            'Most downloaded in your industry',
            'Easy integration with existing tools'
          ],
          tags: ['support', 'classification', 'automation'],
          estimated_setup_time: 10,
          difficulty_level: 'beginner'
        },
        {
          id: 'rec-4',
          name: 'Lead Scoring Engine',
          description: 'Machine learning-based lead qualification and scoring system',
          category: 'Sales',
          rating: 4.7,
          download_count: 1450,
          author_name: 'Sales Analytics Co',
          recommendation_score: 0.82,
          recommendation_reasons: [
            'High conversion rate for tech companies',
            'Recommended by similar users',
            'Integrates with popular CRM systems'
          ],
          tags: ['sales', 'lead-scoring', 'ml', 'crm'],
          estimated_setup_time: 25,
          difficulty_level: 'advanced'
        },
        {
          id: 'rec-5',
          name: 'Content Optimization Bot',
          description: 'SEO and content performance optimization with AI insights',
          category: 'Marketing',
          rating: 4.5,
          download_count: 670,
          author_name: 'ContentAI',
          recommendation_score: 0.78,
          recommendation_reasons: [
            'Rising popularity in your industry',
            'Good fit for your experience level',
            'Users like you also downloaded this'
          ],
          tags: ['seo', 'content', 'optimization', 'ai'],
          estimated_setup_time: 18,
          difficulty_level: 'intermediate'
        }
      ];

      // Filter based on recommendation type
      switch (recommendationType) {
        case 'trending':
          return baseRecommendations.sort((a, b) => b.download_count - a.download_count).slice(0, 3);
        case 'similar':
          return baseRecommendations.filter(rec =>
            currentTemplate ? rec.category === 'Customer Service' : true
          ).slice(0, 3);
        case 'collaborative':
          return baseRecommendations.filter(rec =>
            rec.recommendation_reasons.some(reason => reason.includes('similar users'))
          );
        default:
          return baseRecommendations;
      }
    }
  });

  const getRecommendationTypeIcon = (type: string) => {
    switch (type) {
      case 'personalized': return <Target className="w-4 h-4" />;
      case 'trending': return <TrendingUp className="w-4 h-4" />;
      case 'similar': return <Users className="w-4 h-4" />;
      case 'collaborative': return <Brain className="w-4 h-4" />;
      default: return <Sparkles className="w-4 h-4" />;
    }
  };

  const getDifficultyColor = (level: string) => {
    switch (level) {
      case 'beginner': return 'bg-green-100 text-green-800';
      case 'intermediate': return 'bg-yellow-100 text-yellow-800';
      case 'advanced': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getContextTitle = () => {
    switch (context) {
      case 'post-install': return 'Recommended Next Steps';
      case 'similar': return 'Similar Templates';
      case 'trending': return 'Trending Now';
      default: return 'Recommended for You';
    }
  };

  const RecommendationCard: React.FC<{ template: RecommendedTemplate }> = ({ template }) => (
    <div className="bg-white border border-gray-200 rounded-lg p-6 hover:border-blue-300 hover:shadow-md transition-all duration-200">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">{template.name}</h3>
          <p className="text-sm text-gray-600 mb-2">{template.description}</p>
        </div>
        <div className="ml-4 text-right">
          <div className="text-sm font-medium text-blue-600">
            {Math.round(template.recommendation_score * 100)}% match
          </div>
          <div className="text-xs text-gray-500">recommendation score</div>
        </div>
      </div>

      {/* Metadata */}
      <div className="flex items-center space-x-4 mb-3 text-sm text-gray-600">
        <div className="flex items-center space-x-1">
          <Star className="w-4 h-4 text-yellow-400 fill-current" />
          <span>{template.rating}</span>
        </div>
        <div className="flex items-center space-x-1">
          <Download className="w-4 h-4" />
          <span>{template.download_count.toLocaleString()}</span>
        </div>
        <div className="flex items-center space-x-1">
          <Clock className="w-4 h-4" />
          <span>{template.estimated_setup_time}m setup</span>
        </div>
        <span className={clsx(
          'px-2 py-1 rounded-full text-xs font-medium',
          getDifficultyColor(template.difficulty_level)
        )}>
          {template.difficulty_level}
        </span>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-4">
        {template.tags.slice(0, 3).map((tag, index) => (
          <span
            key={index}
            className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-md"
          >
            {tag}
          </span>
        ))}
        {template.tags.length > 3 && (
          <span className="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded-md">
            +{template.tags.length - 3} more
          </span>
        )}
      </div>

      {/* Recommendation Reasons */}
      <div className="mb-4">
        <div className="flex items-center space-x-2 mb-2">
          <Lightbulb className="w-4 h-4 text-yellow-500" />
          <span className="text-sm font-medium text-gray-900">Why we recommend this:</span>
        </div>
        <ul className="space-y-1">
          {template.recommendation_reasons.slice(0, 2).map((reason, index) => (
            <li key={index} className="text-sm text-gray-600 flex items-start space-x-2">
              <span className="w-1 h-1 bg-gray-400 rounded-full mt-2 flex-shrink-0" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        <div className="text-sm text-gray-600">
          by {template.author_name}
        </div>
        <div className="flex items-center space-x-2">
          <button className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
            Preview
          </button>
          <button className="flex items-center space-x-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">
            <span>Install</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Finding recommendations...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Sparkles className="w-6 h-6 text-blue-600" />
          <h2 className="text-xl font-semibold text-gray-900">{getContextTitle()}</h2>
        </div>

        {/* Recommendation Type Selector */}
        <div className="flex items-center space-x-2">
          {(['personalized', 'trending', 'similar', 'collaborative'] as const).map((type) => (
            <button
              key={type}
              onClick={() => setRecommendationType(type)}
              className={clsx(
                'flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                recommendationType === type
                  ? 'bg-blue-100 text-blue-700 border border-blue-200'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              )}
            >
              {getRecommendationTypeIcon(type)}
              <span className="capitalize">{type}</span>
            </button>
          ))}
        </div>
      </div>

      {/* User Context Info */}
      {userProfile && context === 'browse' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <Target className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="font-medium text-blue-900 mb-1">Personalized for you</h3>
              <p className="text-sm text-blue-700">
                Based on your industry ({userProfile.industry}), team size ({userProfile.team_size}),
                and recent activity in {userProfile.usage_patterns.preferred_categories.join(', ')} categories.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Recommendations Grid */}
      {recommendations.length === 0 ? (
        <div className="text-center py-8">
          <Sparkles className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No recommendations available</h3>
          <p className="text-gray-600">Check back later as we learn more about your preferences.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {recommendations.map((template) => (
            <RecommendationCard key={template.id} template={template} />
          ))}
        </div>
      )}

      {/* More Recommendations Link */}
      {recommendations.length > 0 && context !== 'browse' && (
        <div className="text-center pt-4">
          <button className="text-blue-600 hover:text-blue-700 font-medium">
            View all recommendations →
          </button>
        </div>
      )}
    </div>
  );
};