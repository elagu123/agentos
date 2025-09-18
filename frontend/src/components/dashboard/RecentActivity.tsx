import React from 'react';
import {
  CheckCircle,
  XCircle,
  Clock,
  MessageSquare,
  Workflow,
  AlertCircle
} from 'lucide-react';

interface Activity {
  id: number;
  type: string;
  title: string;
  description: string;
  timestamp: string;
  status: 'success' | 'error' | 'running' | 'pending';
}

interface RecentActivityProps {
  activities: Activity[];
}

const activityIcons = {
  workflow_completed: CheckCircle,
  workflow_failed: XCircle,
  workflow_started: Clock,
  agent_interaction: MessageSquare,
  default: Workflow
};

const statusColors = {
  success: 'text-green-600 bg-green-100',
  error: 'text-red-600 bg-red-100',
  running: 'text-blue-600 bg-blue-100',
  pending: 'text-yellow-600 bg-yellow-100'
};

export default function RecentActivity({ activities }: RecentActivityProps) {
  return (
    <div className="space-y-4">
      {activities.map((activity) => {
        const Icon = activityIcons[activity.type as keyof typeof activityIcons] || activityIcons.default;

        return (
          <div key={activity.id} className="flex items-start space-x-3">
            <div className={`flex-shrink-0 p-1.5 rounded-full ${statusColors[activity.status]}`}>
              <Icon className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-900">{activity.title}</p>
                <span className="text-xs text-gray-500">{activity.timestamp}</span>
              </div>
              <p className="text-sm text-gray-600">{activity.description}</p>
            </div>
          </div>
        );
      })}

      {activities.length === 0 && (
        <div className="text-center py-6">
          <AlertCircle className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No recent activity</h3>
          <p className="mt-1 text-sm text-gray-500">
            Your workflows and agent interactions will appear here.
          </p>
        </div>
      )}
    </div>
  );
}