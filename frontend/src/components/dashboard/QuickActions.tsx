import React from 'react';
import { Link } from 'react-router-dom';
import { LucideIcon, ArrowRight } from 'lucide-react';

interface QuickAction {
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
  color: string;
}

interface QuickActionsProps {
  actions: QuickAction[];
}

export default function QuickActions({ actions }: QuickActionsProps) {
  return (
    <div className="space-y-4">
      {actions.map((action, index) => (
        <Link
          key={index}
          to={action.href}
          className="block p-4 border border-gray-200 rounded-lg hover:border-gray-300 hover:shadow-sm transition-all group"
        >
          <div className="flex items-center">
            <div className={`flex-shrink-0 ${action.color} p-2 rounded-lg`}>
              <action.icon className="h-6 w-6 text-white" />
            </div>
            <div className="ml-4 flex-1">
              <h4 className="text-sm font-medium text-gray-900 group-hover:text-gray-700">
                {action.title}
              </h4>
              <p className="text-sm text-gray-600">{action.description}</p>
            </div>
            <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-gray-600" />
          </div>
        </Link>
      ))}
    </div>
  );
}