import React, { useState } from 'react';
import {
  TrendingUp,
  Download,
  Star,
  Users,
  Calendar,
  BarChart3,
  PieChart,
  Activity,
  Target,
  Clock,
  ThumbsUp,
  Filter,
  RefreshCw
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';

interface AnalyticsData {
  overview: {
    total_downloads: number;
    avg_rating: number;
    total_reviews: number;
    active_users: number;
    conversion_rate: number;
  };
  downloads_over_time: Array<{
    date: string;
    downloads: number;
  }>;
  rating_distribution: Array<{
    rating: number;
    count: number;
  }>;
  category_performance: Array<{
    category: string;
    downloads: number;
    avg_rating: number;
    templates_count: number;
  }>;
  top_templates: Array<{
    id: string;
    name: string;
    downloads: number;
    rating: number;
    growth_rate: number;
  }>;
  user_engagement: {
    daily_active_users: number;
    weekly_active_users: number;
    monthly_active_users: number;
    avg_session_duration: number;
  };
}

interface TemplateAnalytics {
  template_id: string;
  template_name: string;
  total_downloads: number;
  total_views: number;
  conversion_rate: number;
  avg_rating: number;
  total_reviews: number;
  downloads_over_time: Array<{
    date: string;
    downloads: number;
    views: number;
  }>;
  user_demographics: {
    by_industry: Array<{ industry: string; count: number }>;
    by_team_size: Array<{ team_size: string; count: number }>;
  };
  retention_metrics: {
    day_1: number;
    day_7: number;
    day_30: number;
  };
}

export const AnalyticsDashboard: React.FC = () => {
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | '1y'>('30d');

  const { data: analytics, isLoading } = useQuery({
    queryKey: ['marketplace-analytics', timeRange],
    queryFn: async (): Promise<AnalyticsData> => {
      // Mock data - in real app would come from API
      return {
        overview: {
          total_downloads: 15420,
          avg_rating: 4.3,
          total_reviews: 892,
          active_users: 1250,
          conversion_rate: 12.5
        },
        downloads_over_time: [
          { date: '2024-01-01', downloads: 120 },
          { date: '2024-01-02', downloads: 145 },
          { date: '2024-01-03', downloads: 180 },
          { date: '2024-01-04', downloads: 165 },
          { date: '2024-01-05', downloads: 210 },
          { date: '2024-01-06', downloads: 195 },
          { date: '2024-01-07', downloads: 230 }
        ],
        rating_distribution: [
          { rating: 5, count: 450 },
          { rating: 4, count: 320 },
          { rating: 3, count: 89 },
          { rating: 2, count: 25 },
          { rating: 1, count: 8 }
        ],
        category_performance: [
          { category: 'Customer Service', downloads: 4200, avg_rating: 4.5, templates_count: 25 },
          { category: 'Data Analysis', downloads: 3800, avg_rating: 4.2, templates_count: 18 },
          { category: 'Marketing', downloads: 3100, avg_rating: 4.1, templates_count: 22 },
          { category: 'Sales', downloads: 2900, avg_rating: 4.4, templates_count: 16 },
          { category: 'HR', downloads: 1420, avg_rating: 4.0, templates_count: 12 }
        ],
        top_templates: [
          { id: '1', name: 'Customer Support Bot', downloads: 1250, rating: 4.8, growth_rate: 15.2 },
          { id: '2', name: 'Sales Lead Qualifier', downloads: 980, rating: 4.6, growth_rate: 12.8 },
          { id: '3', name: 'Data Analyzer Pro', downloads: 850, rating: 4.5, growth_rate: 9.4 },
          { id: '4', name: 'Content Creator', downloads: 720, rating: 4.3, growth_rate: 18.7 },
          { id: '5', name: 'Email Assistant', downloads: 690, rating: 4.4, growth_rate: 7.2 }
        ],
        user_engagement: {
          daily_active_users: 145,
          weekly_active_users: 680,
          monthly_active_users: 1250,
          avg_session_duration: 24.5
        }
      };
    }
  });

  const { data: templateAnalytics } = useQuery({
    queryKey: ['template-analytics', selectedTemplate],
    queryFn: async (): Promise<TemplateAnalytics | null> => {
      if (!selectedTemplate) return null;

      // Mock template-specific data
      return {
        template_id: selectedTemplate,
        template_name: 'Customer Support Bot',
        total_downloads: 1250,
        total_views: 5600,
        conversion_rate: 22.3,
        avg_rating: 4.8,
        total_reviews: 156,
        downloads_over_time: [
          { date: '2024-01-01', downloads: 15, views: 67 },
          { date: '2024-01-02', downloads: 18, views: 82 },
          { date: '2024-01-03', downloads: 22, views: 95 },
          { date: '2024-01-04', downloads: 19, views: 78 },
          { date: '2024-01-05', downloads: 25, views: 110 }
        ],
        user_demographics: {
          by_industry: [
            { industry: 'Technology', count: 45 },
            { industry: 'E-commerce', count: 38 },
            { industry: 'Healthcare', count: 29 },
            { industry: 'Finance', count: 22 },
            { industry: 'Other', count: 22 }
          ],
          by_team_size: [
            { team_size: '1-10', count: 65 },
            { team_size: '11-50', count: 52 },
            { team_size: '51-200', count: 28 },
            { team_size: '201-500', count: 8 },
            { team_size: '500+', count: 3 }
          ]
        },
        retention_metrics: {
          day_1: 85.2,
          day_7: 67.8,
          day_30: 45.3
        }
      };
    },
    enabled: !!selectedTemplate
  });

  const StatCard: React.FC<{
    icon: React.ReactNode;
    title: string;
    value: string | number;
    change?: string;
    changeType?: 'positive' | 'negative' | 'neutral';
  }> = ({ icon, title, value, change, changeType = 'neutral' }) => (
    <div className="bg-white p-6 rounded-lg border border-gray-200">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {change && (
            <p className={clsx(
              'text-sm flex items-center space-x-1 mt-1',
              changeType === 'positive' && 'text-green-600',
              changeType === 'negative' && 'text-red-600',
              changeType === 'neutral' && 'text-gray-600'
            )}>
              <TrendingUp className={clsx(
                'w-3 h-3',
                changeType === 'negative' && 'rotate-180'
              )} />
              <span>{change}</span>
            </p>
          )}
        </div>
        <div className="p-3 bg-blue-50 rounded-full">
          {icon}
        </div>
      </div>
    </div>
  );

  const SimpleBarChart: React.FC<{ data: Array<{ date: string; downloads: number }> }> = ({ data }) => {
    const maxValue = Math.max(...data.map(d => d.downloads));

    return (
      <div className="space-y-2">
        {data.map((item, index) => (
          <div key={index} className="flex items-center space-x-3">
            <span className="text-xs text-gray-500 w-16">
              {new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
            <div className="flex-1 bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(item.downloads / maxValue) * 100}%` }}
              />
            </div>
            <span className="text-xs text-gray-900 w-8">{item.downloads}</span>
          </div>
        ))}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading analytics...</span>
      </div>
    );
  }

  if (!analytics) {
    return <div>No analytics data available</div>;
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
          <p className="text-gray-600 mt-1">Monitor marketplace performance and user engagement</p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as any)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="1y">Last year</option>
          </select>
          <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
            <RefreshCw className="w-4 h-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        <StatCard
          icon={<Download className="w-5 h-5 text-blue-600" />}
          title="Total Downloads"
          value={analytics.overview.total_downloads.toLocaleString()}
          change="+12.5%"
          changeType="positive"
        />
        <StatCard
          icon={<Star className="w-5 h-5 text-yellow-600" />}
          title="Average Rating"
          value={analytics.overview.avg_rating.toFixed(1)}
          change="+0.2"
          changeType="positive"
        />
        <StatCard
          icon={<ThumbsUp className="w-5 h-5 text-green-600" />}
          title="Total Reviews"
          value={analytics.overview.total_reviews}
          change="+8.3%"
          changeType="positive"
        />
        <StatCard
          icon={<Users className="w-5 h-5 text-purple-600" />}
          title="Active Users"
          value={analytics.overview.active_users}
          change="+15.2%"
          changeType="positive"
        />
        <StatCard
          icon={<Target className="w-5 h-5 text-red-600" />}
          title="Conversion Rate"
          value={`${analytics.overview.conversion_rate}%`}
          change="+2.1%"
          changeType="positive"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Downloads Over Time */}
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Downloads Trend</h3>
          <SimpleBarChart data={analytics.downloads_over_time} />
        </div>

        {/* Rating Distribution */}
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Rating Distribution</h3>
          <div className="space-y-3">
            {analytics.rating_distribution.reverse().map((item) => (
              <div key={item.rating} className="flex items-center space-x-3">
                <div className="flex items-center space-x-1 w-12">
                  <span className="text-sm">{item.rating}</span>
                  <Star className="w-3 h-3 text-yellow-400 fill-current" />
                </div>
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-yellow-400 h-2 rounded-full"
                    style={{
                      width: `${(item.count / Math.max(...analytics.rating_distribution.map(d => d.count))) * 100}%`
                    }}
                  />
                </div>
                <span className="text-sm text-gray-600 w-8">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Category Performance */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Category Performance</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-900">Category</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Downloads</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Avg Rating</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Templates</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Performance</th>
              </tr>
            </thead>
            <tbody>
              {analytics.category_performance.map((category, index) => (
                <tr key={index} className="border-b border-gray-100">
                  <td className="py-3 px-4 font-medium text-gray-900">{category.category}</td>
                  <td className="py-3 px-4 text-gray-600">{category.downloads.toLocaleString()}</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center space-x-1">
                      <Star className="w-4 h-4 text-yellow-400 fill-current" />
                      <span className="text-gray-600">{category.avg_rating.toFixed(1)}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-gray-600">{category.templates_count}</td>
                  <td className="py-3 px-4">
                    <div className="w-24 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-green-500 h-2 rounded-full"
                        style={{
                          width: `${(category.downloads / Math.max(...analytics.category_performance.map(c => c.downloads))) * 100}%`
                        }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top Templates */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Performing Templates</h3>
        <div className="space-y-4">
          {analytics.top_templates.map((template, index) => (
            <div
              key={template.id}
              className="flex items-center justify-between p-4 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100"
              onClick={() => setSelectedTemplate(template.id)}
            >
              <div className="flex items-center space-x-4">
                <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold">
                  {index + 1}
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">{template.name}</h4>
                  <div className="flex items-center space-x-4 text-sm text-gray-600">
                    <span>{template.downloads} downloads</span>
                    <div className="flex items-center space-x-1">
                      <Star className="w-3 h-3 text-yellow-400 fill-current" />
                      <span>{template.rating}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className={clsx(
                  'text-sm font-medium',
                  template.growth_rate > 0 ? 'text-green-600' : 'text-red-600'
                )}>
                  {template.growth_rate > 0 ? '+' : ''}{template.growth_rate}%
                </div>
                <div className="text-xs text-gray-500">growth</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* User Engagement */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">User Engagement</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{analytics.user_engagement.daily_active_users}</div>
            <div className="text-sm text-gray-600">Daily Active Users</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{analytics.user_engagement.weekly_active_users}</div>
            <div className="text-sm text-gray-600">Weekly Active Users</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">{analytics.user_engagement.monthly_active_users}</div>
            <div className="text-sm text-gray-600">Monthly Active Users</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">{analytics.user_engagement.avg_session_duration}m</div>
            <div className="text-sm text-gray-600">Avg Session Duration</div>
          </div>
        </div>
      </div>

      {/* Template-Specific Analytics */}
      {selectedTemplate && templateAnalytics && (
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">
              Template Analytics: {templateAnalytics.template_name}
            </h3>
            <button
              onClick={() => setSelectedTemplate(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ×
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{templateAnalytics.conversion_rate}%</div>
              <div className="text-sm text-gray-600">Conversion Rate</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{templateAnalytics.total_views}</div>
              <div className="text-sm text-gray-600">Total Views</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{templateAnalytics.avg_rating}</div>
              <div className="text-sm text-gray-600">Average Rating</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Usage by Industry</h4>
              <div className="space-y-2">
                {templateAnalytics.user_demographics.by_industry.map((item, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">{item.industry}</span>
                    <span className="text-sm font-medium">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Retention Metrics</h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Day 1 Retention</span>
                  <span className="text-sm font-medium">{templateAnalytics.retention_metrics.day_1}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Day 7 Retention</span>
                  <span className="text-sm font-medium">{templateAnalytics.retention_metrics.day_7}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Day 30 Retention</span>
                  <span className="text-sm font-medium">{templateAnalytics.retention_metrics.day_30}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};