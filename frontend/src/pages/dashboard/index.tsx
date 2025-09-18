import React from 'react';
import { Link } from 'react-router-dom';
import {
  MessageSquare,
  Workflow,
  BarChart3,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
  ArrowRight
} from 'lucide-react';
import DashboardLayout from '../../components/layout/DashboardLayout';
import MetricsCard from '../../components/dashboard/MetricsCard';
import QuickActions from '../../components/dashboard/QuickActions';
import RecentActivity from '../../components/dashboard/RecentActivity';

export default function Dashboard() {
  // Mock data - replace with real API calls
  const metrics = {
    totalWorkflows: 24,
    activeWorkflows: 8,
    completedToday: 15,
    averageExecutionTime: '2.3s',
    successRate: 94.2,
    tokensUsed: 125340,
    estimatedCost: 12.45
  };

  const quickActions = [
    {
      title: 'Chat with Agent',
      description: 'Start a conversation with your Principal Agent',
      href: '/dashboard/chat',
      icon: MessageSquare,
      color: 'bg-blue-500'
    },
    {
      title: 'Create Workflow',
      description: 'Build a new automated workflow',
      href: '/dashboard/workflows/create',
      icon: Workflow,
      color: 'bg-green-500'
    },
    {
      title: 'View Analytics',
      description: 'Check performance metrics and insights',
      href: '/dashboard/analytics',
      icon: BarChart3,
      color: 'bg-purple-500'
    }
  ];

  const recentActivities = [
    {
      id: 1,
      type: 'workflow_completed',
      title: 'Content Creation Workflow',
      description: 'Successfully generated 3 blog posts',
      timestamp: '5 minutes ago',
      status: 'success'
    },
    {
      id: 2,
      type: 'agent_interaction',
      title: 'Principal Agent Chat',
      description: 'Answered 4 customer service questions',
      timestamp: '15 minutes ago',
      status: 'success'
    },
    {
      id: 3,
      type: 'workflow_failed',
      title: 'Email Campaign Workflow',
      description: 'Failed due to missing template',
      timestamp: '1 hour ago',
      status: 'error'
    },
    {
      id: 4,
      type: 'workflow_started',
      title: 'Research & Analysis',
      description: 'Analyzing competitor data...',
      timestamp: '2 hours ago',
      status: 'running'
    }
  ];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-600">
            Overview of your AI agents and workflows
          </p>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricsCard
            title="Total Workflows"
            value={metrics.totalWorkflows}
            icon={Workflow}
            trend={+12}
            color="blue"
          />
          <MetricsCard
            title="Active Now"
            value={metrics.activeWorkflows}
            icon={TrendingUp}
            trend={+3}
            color="green"
          />
          <MetricsCard
            title="Completed Today"
            value={metrics.completedToday}
            icon={CheckCircle}
            trend={+25}
            color="emerald"
          />
          <MetricsCard
            title="Success Rate"
            value={`${metrics.successRate}%`}
            icon={BarChart3}
            trend={+2.1}
            color="purple"
          />
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Clock className="h-8 w-8 text-blue-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Avg. Execution Time</p>
                <p className="text-2xl font-bold text-gray-900">{metrics.averageExecutionTime}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <BarChart3 className="h-8 w-8 text-green-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Tokens Used</p>
                <p className="text-2xl font-bold text-gray-900">{metrics.tokensUsed.toLocaleString()}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <TrendingUp className="h-8 w-8 text-purple-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Estimated Cost</p>
                <p className="text-2xl font-bold text-gray-900">${metrics.estimatedCost}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions and Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Quick Actions */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Quick Actions</h3>
            </div>
            <div className="p-6">
              <QuickActions actions={quickActions} />
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">Recent Activity</h3>
              <Link
                to="/dashboard/workflows"
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
              >
                View all
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </div>
            <div className="p-6">
              <RecentActivity activities={recentActivities} />
            </div>
          </div>
        </div>

        {/* Agent Status */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Agent Status</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
              {[
                { name: 'Principal Agent', status: 'active', lastUsed: '2 min ago' },
                { name: 'Copywriter', status: 'active', lastUsed: '5 min ago' },
                { name: 'Researcher', status: 'idle', lastUsed: '1 hour ago' },
                { name: 'Scheduler', status: 'idle', lastUsed: '3 hours ago' },
                { name: 'Data Analyzer', status: 'active', lastUsed: '10 min ago' }
              ].map((agent) => (
                <div key={agent.name} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-gray-900">{agent.name}</h4>
                    <div className={`h-2 w-2 rounded-full ${
                      agent.status === 'active' ? 'bg-green-400' : 'bg-gray-300'
                    }`} />
                  </div>
                  <p className="text-xs text-gray-500">Last used: {agent.lastUsed}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}