import React, { useState } from 'react';
import {
  Eye,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Flag,
  User,
  Calendar,
  MessageSquare,
  MoreVertical,
  Search,
  Filter
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';

interface ReportedTemplate {
  id: string;
  template_id: string;
  template_name: string;
  template_author: string;
  reason: string;
  description: string;
  reporter_name: string;
  created_at: string;
  status: 'pending' | 'reviewed' | 'resolved' | 'dismissed';
  severity: 'low' | 'medium' | 'high';
}

interface PendingTemplate {
  id: string;
  name: string;
  description: string;
  author_name: string;
  category: string;
  created_at: string;
  status: 'pending' | 'approved' | 'rejected';
  security_scan_results?: {
    passed: boolean;
    issues: string[];
  };
}

export const ModerationDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'reports' | 'pending' | 'users'>('reports');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const queryClient = useQueryClient();

  // Mock data - in real app would come from API
  const { data: reports = [], isLoading: reportsLoading } = useQuery({
    queryKey: ['moderation-reports', statusFilter],
    queryFn: async () => {
      // Simulate API call
      const mockReports: ReportedTemplate[] = [
        {
          id: '1',
          template_id: 'template-1',
          template_name: 'Customer Service Bot',
          template_author: 'john_doe',
          reason: 'inappropriate_content',
          description: 'Contains inappropriate language in responses',
          reporter_name: 'jane_smith',
          created_at: '2024-01-15T10:30:00Z',
          status: 'pending',
          severity: 'medium'
        },
        {
          id: '2',
          template_id: 'template-2',
          template_name: 'Data Scraper',
          template_author: 'bot_creator',
          reason: 'security_concern',
          description: 'Potentially accessing unauthorized endpoints',
          reporter_name: 'security_team',
          created_at: '2024-01-14T15:45:00Z',
          status: 'pending',
          severity: 'high'
        }
      ];
      return mockReports;
    }
  });

  const { data: pendingTemplates = [], isLoading: pendingLoading } = useQuery({
    queryKey: ['moderation-pending'],
    queryFn: async () => {
      const mockPending: PendingTemplate[] = [
        {
          id: '1',
          name: 'Advanced Analytics Bot',
          description: 'AI-powered analytics and reporting system',
          author_name: 'analytics_pro',
          category: 'Analytics',
          created_at: '2024-01-16T09:00:00Z',
          status: 'pending',
          security_scan_results: {
            passed: true,
            issues: []
          }
        },
        {
          id: '2',
          name: 'Social Media Manager',
          description: 'Automated social media posting and engagement',
          author_name: 'social_guru',
          category: 'Marketing',
          created_at: '2024-01-15T14:30:00Z',
          status: 'pending',
          security_scan_results: {
            passed: false,
            issues: ['External API calls without validation', 'Potential data exposure']
          }
        }
      ];
      return mockPending;
    }
  });

  const handleReportAction = useMutation({
    mutationFn: async ({ reportId, action }: { reportId: string; action: string }) => {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      return { success: true };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-reports'] });
    }
  });

  const handleTemplateAction = useMutation({
    mutationFn: async ({ templateId, action }: { templateId: string; action: string }) => {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      return { success: true };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-pending'] });
    }
  });

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'bg-red-100 text-red-800 border-red-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'approved': return 'bg-green-100 text-green-800';
      case 'rejected': return 'bg-red-100 text-red-800';
      case 'reviewed': return 'bg-blue-100 text-blue-800';
      case 'resolved': return 'bg-green-100 text-green-800';
      case 'dismissed': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const renderReportsTab = () => (
    <div className="space-y-6">
      {/* Reports Filters */}
      <div className="flex items-center space-x-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search reports..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="reviewed">Reviewed</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      {/* Reports List */}
      <div className="space-y-4">
        {reports.map((report) => (
          <div key={report.id} className="bg-white border border-gray-200 rounded-lg p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <Flag className="w-5 h-5 text-red-500" />
                  <h3 className="text-lg font-semibold text-gray-900">
                    {report.template_name}
                  </h3>
                  <span className={clsx(
                    'px-2 py-1 rounded-full text-xs font-medium border',
                    getSeverityColor(report.severity)
                  )}>
                    {report.severity.toUpperCase()}
                  </span>
                  <span className={clsx(
                    'px-2 py-1 rounded-full text-xs font-medium',
                    getStatusColor(report.status)
                  )}>
                    {report.status.toUpperCase()}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
                  <div>
                    <span className="font-medium">Template Author:</span> {report.template_author}
                  </div>
                  <div>
                    <span className="font-medium">Reported by:</span> {report.reporter_name}
                  </div>
                  <div>
                    <span className="font-medium">Reason:</span> {report.reason.replace('_', ' ')}
                  </div>
                  <div>
                    <span className="font-medium">Date:</span> {new Date(report.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="mt-3">
                  <span className="font-medium text-sm text-gray-900">Description:</span>
                  <p className="text-sm text-gray-700 mt-1">{report.description}</p>
                </div>
              </div>
              <div className="ml-4">
                <button className="p-2 text-gray-400 hover:text-gray-600">
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>
            </div>

            {report.status === 'pending' && (
              <div className="flex items-center space-x-3 pt-4 border-t border-gray-200">
                <button
                  onClick={() => handleReportAction.mutate({ reportId: report.id, action: 'view_template' })}
                  className="flex items-center space-x-2 px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  <Eye className="w-4 h-4" />
                  <span>View Template</span>
                </button>
                <button
                  onClick={() => handleReportAction.mutate({ reportId: report.id, action: 'resolve' })}
                  className="flex items-center space-x-2 px-4 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
                >
                  <CheckCircle className="w-4 h-4" />
                  <span>Resolve</span>
                </button>
                <button
                  onClick={() => handleReportAction.mutate({ reportId: report.id, action: 'dismiss' })}
                  className="flex items-center space-x-2 px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
                >
                  <XCircle className="w-4 h-4" />
                  <span>Dismiss</span>
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  const renderPendingTab = () => (
    <div className="space-y-6">
      <div className="space-y-4">
        {pendingTemplates.map((template) => (
          <div key={template.id} className="bg-white border border-gray-200 rounded-lg p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <h3 className="text-lg font-semibold text-gray-900">{template.name}</h3>
                  <span className={clsx(
                    'px-2 py-1 rounded-full text-xs font-medium',
                    getStatusColor(template.status)
                  )}>
                    {template.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-gray-700 mb-3">{template.description}</p>
                <div className="grid grid-cols-3 gap-4 text-sm text-gray-600">
                  <div>
                    <span className="font-medium">Author:</span> {template.author_name}
                  </div>
                  <div>
                    <span className="font-medium">Category:</span> {template.category}
                  </div>
                  <div>
                    <span className="font-medium">Submitted:</span> {new Date(template.created_at).toLocaleDateString()}
                  </div>
                </div>

                {/* Security Scan Results */}
                {template.security_scan_results && (
                  <div className="mt-4 p-3 bg-gray-50 rounded-md">
                    <div className="flex items-center space-x-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-yellow-500" />
                      <span className="font-medium text-sm">Security Scan Results</span>
                    </div>
                    <div className="text-sm">
                      <div className={clsx(
                        'flex items-center space-x-2',
                        template.security_scan_results.passed ? 'text-green-600' : 'text-red-600'
                      )}>
                        {template.security_scan_results.passed ? (
                          <CheckCircle className="w-4 h-4" />
                        ) : (
                          <XCircle className="w-4 h-4" />
                        )}
                        <span>
                          {template.security_scan_results.passed ? 'Passed' : 'Failed'}
                        </span>
                      </div>
                      {template.security_scan_results.issues.length > 0 && (
                        <div className="mt-2">
                          <span className="font-medium">Issues:</span>
                          <ul className="list-disc list-inside ml-4 mt-1">
                            {template.security_scan_results.issues.map((issue, index) => (
                              <li key={index} className="text-red-600">{issue}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {template.status === 'pending' && (
              <div className="flex items-center space-x-3 pt-4 border-t border-gray-200">
                <button
                  onClick={() => handleTemplateAction.mutate({ templateId: template.id, action: 'preview' })}
                  className="flex items-center space-x-2 px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  <Eye className="w-4 h-4" />
                  <span>Preview</span>
                </button>
                <button
                  onClick={() => handleTemplateAction.mutate({ templateId: template.id, action: 'approve' })}
                  className="flex items-center space-x-2 px-4 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
                  disabled={!template.security_scan_results?.passed}
                >
                  <CheckCircle className="w-4 h-4" />
                  <span>Approve</span>
                </button>
                <button
                  onClick={() => handleTemplateAction.mutate({ templateId: template.id, action: 'reject' })}
                  className="flex items-center space-x-2 px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
                >
                  <XCircle className="w-4 h-4" />
                  <span>Reject</span>
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  const renderUsersTab = () => (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">User Management</h3>
        <p className="text-gray-600">User moderation features coming soon...</p>
      </div>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Moderation Dashboard</h1>
        <p className="text-gray-600 mt-1">Manage reports, review templates, and moderate community content</p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('reports')}
            className={clsx(
              'py-2 px-1 border-b-2 font-medium text-sm',
              activeTab === 'reports'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            <div className="flex items-center space-x-2">
              <Flag className="w-4 h-4" />
              <span>Reports ({reports.length})</span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab('pending')}
            className={clsx(
              'py-2 px-1 border-b-2 font-medium text-sm',
              activeTab === 'pending'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Pending Templates ({pendingTemplates.length})</span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={clsx(
              'py-2 px-1 border-b-2 font-medium text-sm',
              activeTab === 'users'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            <div className="flex items-center space-x-2">
              <User className="w-4 h-4" />
              <span>Users</span>
            </div>
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'reports' && renderReportsTab()}
      {activeTab === 'pending' && renderPendingTab()}
      {activeTab === 'users' && renderUsersTab()}
    </div>
  );
};