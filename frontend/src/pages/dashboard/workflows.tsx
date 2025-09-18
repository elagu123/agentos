import React from 'react';
import DashboardLayout from '../../components/layout/DashboardLayout';

export default function WorkflowsPage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <p className="mt-1 text-sm text-gray-600">
            Manage and monitor your automated workflows
          </p>
        </div>

        {/* Placeholder content */}
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600">Workflows management interface coming soon...</p>
        </div>
      </div>
    </DashboardLayout>
  );
}