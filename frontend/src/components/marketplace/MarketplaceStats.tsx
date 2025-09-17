import React from 'react';
import { FileText, Download, Users, Star } from 'lucide-react';

interface MarketplaceStatsProps {
  stats: {
    total_templates: number;
    total_downloads: number;
    total_authors: number;
    average_rating: number;
  };
}

export const MarketplaceStats: React.FC<MarketplaceStatsProps> = ({ stats }) => {
  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  };

  const statItems = [
    {
      icon: FileText,
      label: 'Templates',
      value: formatNumber(stats.total_templates),
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      icon: Download,
      label: 'Downloads',
      value: formatNumber(stats.total_downloads),
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      icon: Users,
      label: 'Authors',
      value: formatNumber(stats.total_authors),
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
    {
      icon: Star,
      label: 'Avg Rating',
      value: stats.average_rating.toFixed(1),
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100',
    },
  ];

  return (
    <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
      {statItems.map((item, index) => (
        <div key={index} className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${item.bgColor}`}>
            <item.icon className={`w-5 h-5 ${item.color}`} />
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900">{item.value}</div>
            <div className="text-sm text-gray-600">{item.label}</div>
          </div>
        </div>
      ))}
    </div>
  );
};