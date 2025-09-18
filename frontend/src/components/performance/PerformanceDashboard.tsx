/**
 * Performance Dashboard Component for AgentOS.
 *
 * Displays real-time performance metrics including:
 * - System resources (CPU, Memory, Disk)
 * - API response times
 * - Database performance
 * - WebSocket connections
 * - Cache statistics
 */
import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Activity, Server, Database, Wifi, Clock, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';
import { useOptimizedQuery } from '../../hooks/useOptimizedQuery';

interface PerformanceMetrics {
  timestamp: string;
  uptime_seconds: number;
  system: {
    cpu_percent: number;
    memory_percent: number;
    memory_used_mb: number;
    disk_usage_percent: number;
  };
  api: Record<string, {
    avg_response_time: number;
    p95_response_time: number;
    total_requests: number;
    error_rate: number;
    status_codes: Record<string, number>;
  }>;
  database: {
    avg_query_time: number;
    p95_query_time: number;
    total_queries: number;
    cache_hit_rate: number;
  };
  websocket: {
    active_connections: number;
    total_connections: number;
    messages_sent: number;
  };
}

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  status?: 'good' | 'warning' | 'critical';
  className?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit = '',
  icon,
  trend,
  status = 'good',
  className = ''
}) => {
  const statusColors = {
    good: 'border-green-200 bg-green-50',
    warning: 'border-yellow-200 bg-yellow-50',
    critical: 'border-red-200 bg-red-50'
  };

  const statusTextColors = {
    good: 'text-green-800',
    warning: 'text-yellow-800',
    critical: 'text-red-800'
  };

  return (
    <div className={`p-4 rounded-lg border-2 ${statusColors[status]} ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${statusTextColors[status]} bg-white`}>
            {icon}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-600">{title}</p>
            <div className="flex items-center space-x-2">
              <p className={`text-2xl font-bold ${statusTextColors[status]}`}>
                {typeof value === 'number' ? value.toFixed(1) : value}
                {unit && <span className="text-sm font-normal">{unit}</span>}
              </p>
              {trend && (
                <TrendingUp
                  className={`w-4 h-4 ${
                    trend === 'up' ? 'text-green-500 rotate-0' :
                    trend === 'down' ? 'text-red-500 rotate-180' :
                    'text-gray-500'
                  }`}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

const ChartCard: React.FC<ChartCardProps> = ({ title, children, className = '' }) => (
  <div className={`bg-white p-6 rounded-lg shadow-sm border ${className}`}>
    <h3 className="text-lg font-semibold text-gray-800 mb-4">{title}</h3>
    {children}
  </div>
);

export const PerformanceDashboard: React.FC = () => {
  const [refreshInterval, setRefreshInterval] = useState(30000); // 30 seconds

  // Fetch current performance summary
  const { data: summary, isLoading } = useOptimizedQuery(
    ['performance', 'summary'],
    async () => {
      const response = await fetch('/api/v1/performance/summary');
      if (!response.ok) throw new Error('Failed to fetch performance data');
      return response.json();
    },
    {
      refetchInterval: refreshInterval,
      staleTime: 10000, // 10 seconds
    }
  );

  // Fetch API metrics
  const { data: apiMetrics } = useOptimizedQuery(
    ['performance', 'api'],
    async () => {
      const response = await fetch('/api/v1/performance/api');
      if (!response.ok) throw new Error('Failed to fetch API metrics');
      return response.json();
    },
    {
      refetchInterval: refreshInterval,
    }
  );

  // Fetch historical CPU data for chart
  const { data: cpuHistory } = useOptimizedQuery(
    ['performance', 'metrics', 'cpu'],
    async () => {
      const response = await fetch('/api/v1/performance/metrics/system.cpu_percent?hours=1');
      if (!response.ok) throw new Error('Failed to fetch CPU history');
      return response.json();
    },
    {
      refetchInterval: refreshInterval,
    }
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <span className="ml-3 text-gray-600">Loading performance data...</span>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="text-center text-gray-500 py-8">
        <AlertTriangle className="w-12 h-12 mx-auto mb-4" />
        <p>Failed to load performance data</p>
      </div>
    );
  }

  const performanceData: PerformanceMetrics = summary;

  // Calculate health status
  const getHealthStatus = (value: number, threshold: number, invert = false) => {
    if (invert) {
      return value >= threshold ? 'good' : value >= threshold * 0.8 ? 'warning' : 'critical';
    }
    return value <= threshold ? 'good' : value <= threshold * 1.2 ? 'warning' : 'critical';
  };

  // Format uptime
  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  // Prepare chart data
  const cpuChartData = cpuHistory?.map((point: any) => ({
    time: new Date(point.timestamp).toLocaleTimeString(),
    cpu: point.value
  })) || [];

  // API response time data
  const apiResponseData = Object.entries(performanceData.api || {}).map(([endpoint, stats]) => ({
    name: endpoint.split(':')[1]?.split('/').pop() || endpoint,
    value: stats.avg_response_time,
    count: stats.total_requests
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Performance Dashboard</h1>
          <p className="text-gray-600">Real-time system performance monitoring</p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="border rounded-lg px-3 py-2 text-sm"
          >
            <option value={10000}>10s refresh</option>
            <option value={30000}>30s refresh</option>
            <option value={60000}>1m refresh</option>
            <option value={300000}>5m refresh</option>
          </select>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span>Uptime: {formatUptime(performanceData.uptime_seconds)}</span>
          </div>
        </div>
      </div>

      {/* System Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="CPU Usage"
          value={performanceData.system.cpu_percent}
          unit="%"
          icon={<Server className="w-5 h-5" />}
          status={getHealthStatus(performanceData.system.cpu_percent, 80)}
        />

        <MetricCard
          title="Memory Usage"
          value={performanceData.system.memory_percent}
          unit="%"
          icon={<Activity className="w-5 h-5" />}
          status={getHealthStatus(performanceData.system.memory_percent, 85)}
        />

        <MetricCard
          title="Database Cache Hit Rate"
          value={performanceData.database.cache_hit_rate}
          unit="%"
          icon={<Database className="w-5 h-5" />}
          status={getHealthStatus(performanceData.database.cache_hit_rate, 60, true)}
        />

        <MetricCard
          title="Active WebSocket Connections"
          value={performanceData.websocket.active_connections}
          icon={<Wifi className="w-5 h-5" />}
          status="good"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CPU Usage Chart */}
        <ChartCard title="CPU Usage (Last Hour)">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={cpuChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="cpu"
                stroke="#3B82F6"
                fill="#3B82F6"
                fillOpacity={0.3}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* API Response Times */}
        <ChartCard title="API Response Times">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={apiResponseData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip
                formatter={(value: number) => [`${value.toFixed(1)}ms`, 'Response Time']}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#10B981"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Detailed Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Database Performance */}
        <ChartCard title="Database Performance">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Average Query Time</span>
              <span className="font-semibold">{performanceData.database.avg_query_time?.toFixed(1)}ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">P95 Query Time</span>
              <span className="font-semibold">{performanceData.database.p95_query_time?.toFixed(1)}ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Total Queries</span>
              <span className="font-semibold">{performanceData.database.total_queries?.toLocaleString()}</span>
            </div>
          </div>
        </ChartCard>

        {/* API Statistics */}
        <ChartCard title="API Statistics">
          <div className="space-y-4">
            {Object.entries(performanceData.api || {}).slice(0, 3).map(([endpoint, stats]) => (
              <div key={endpoint} className="flex justify-between items-center">
                <span className="text-sm text-gray-600 truncate">
                  {endpoint.split(':')[1]?.split('/').pop() || endpoint}
                </span>
                <div className="text-right">
                  <div className="font-semibold">{stats.avg_response_time.toFixed(1)}ms</div>
                  <div className="text-xs text-gray-500">{stats.total_requests} req</div>
                </div>
              </div>
            ))}
          </div>
        </ChartCard>

        {/* WebSocket Activity */}
        <ChartCard title="WebSocket Activity">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Active Connections</span>
              <span className="font-semibold">{performanceData.websocket.active_connections}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Total Messages Sent</span>
              <span className="font-semibold">{performanceData.websocket.messages_sent?.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Total Connections</span>
              <span className="font-semibold">{performanceData.websocket.total_connections}</span>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  );
};

export default PerformanceDashboard;