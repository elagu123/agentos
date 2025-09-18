import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

interface MetricsCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: number;
  color: 'blue' | 'green' | 'emerald' | 'purple' | 'red' | 'yellow';
}

const colorClasses = {
  blue: 'text-blue-500',
  green: 'text-green-500',
  emerald: 'text-emerald-500',
  purple: 'text-purple-500',
  red: 'text-red-500',
  yellow: 'text-yellow-500'
};

export default function MetricsCard({ title, value, icon: Icon, trend, color }: MetricsCardProps) {
  const isPositiveTrend = trend && trend > 0;
  const isNegativeTrend = trend && trend < 0;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center">
        <div className={`flex-shrink-0 ${colorClasses[color]}`}>
          <Icon className="h-8 w-8" />
        </div>
        <div className="ml-4 flex-1">
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <div className="flex items-baseline">
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            {trend !== undefined && (
              <div className={`ml-2 flex items-center text-sm ${
                isPositiveTrend ? 'text-green-600' : isNegativeTrend ? 'text-red-600' : 'text-gray-500'
              }`}>
                {isPositiveTrend && <TrendingUp className="h-4 w-4 mr-1" />}
                {isNegativeTrend && <TrendingDown className="h-4 w-4 mr-1" />}
                {Math.abs(trend)}%
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}