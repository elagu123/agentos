/**
 * Frontend Performance Optimization Utilities
 *
 * This module provides utilities for:
 * - Lazy loading components
 * - Request deduplication
 * - Virtual scrolling
 * - Image optimization
 * - Bundle optimization
 */
import { lazy, Suspense, useRef, useState, useEffect, useCallback } from 'react';
import { useVirtual } from '@tanstack/react-virtual';

// =============================================================================
// LAZY LOADING COMPONENTS
// =============================================================================

// Loading fallback component
const LoadingSpinner = () => (
  <div className="flex items-center justify-center p-8">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    <span className="ml-2 text-gray-600">Loading...</span>
  </div>
);

// Route-based code splitting with specific chunk names
export const LazyDashboard = lazy(() =>
  import(/* webpackChunkName: "dashboard" */ '../pages/dashboard').then(module => ({
    default: module.default
  }))
);

export const LazyWorkflowBuilder = lazy(() =>
  import(/* webpackChunkName: "workflow-builder" */ '../components/workflow-builder/WorkflowBuilder').then(module => ({
    default: module.WorkflowBuilder
  }))
);

export const LazyChat = lazy(() =>
  import(/* webpackChunkName: "chat" */ '../pages/dashboard/chat').then(module => ({
    default: module.default
  }))
);

export const LazyAnalytics = lazy(() =>
  import(/* webpackChunkName: "analytics" */ '../pages/dashboard/analytics').then(module => ({
    default: module.default
  }))
);

export const LazyMarketplace = lazy(() =>
  import(/* webpackChunkName: "marketplace" */ '../components/marketplace/MarketplaceDashboard').then(module => ({
    default: module.default
  }))
);

// Component wrapper with loading fallback and error boundary
interface LazyLoadProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const LazyLoad = ({ children, fallback }: LazyLoadProps) => (
  <Suspense fallback={fallback || <LoadingSpinner />}>
    {children}
  </Suspense>
);

// =============================================================================
// REQUEST DEDUPLICATION
// =============================================================================

/**
 * Request deduplication utility to prevent duplicate API calls
 */
class RequestDeduplicator {
  private pendingRequests: Map<string, Promise<any>> = new Map();
  private cache: Map<string, { data: any; timestamp: number; ttl: number }> = new Map();

  async dedupe<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: {
      ttl?: number; // Time to live in milliseconds
      forceRefresh?: boolean;
    } = {}
  ): Promise<T> {
    const { ttl = 30000, forceRefresh = false } = options; // Default 30 seconds TTL

    // Check cache first
    if (!forceRefresh) {
      const cached = this.cache.get(key);
      if (cached && Date.now() - cached.timestamp < cached.ttl) {
        return cached.data;
      }
    }

    // Check if request is already pending
    if (this.pendingRequests.has(key)) {
      return this.pendingRequests.get(key) as Promise<T>;
    }

    // Create new request
    const promise = fetcher()
      .then((data) => {
        // Cache the result
        this.cache.set(key, {
          data,
          timestamp: Date.now(),
          ttl
        });
        return data;
      })
      .finally(() => {
        // Clean up pending request
        this.pendingRequests.delete(key);
      });

    this.pendingRequests.set(key, promise);
    return promise;
  }

  /**
   * Clear cache for specific key or all cache
   */
  clearCache(key?: string) {
    if (key) {
      this.cache.delete(key);
    } else {
      this.cache.clear();
    }
  }

  /**
   * Get cache statistics
   */
  getCacheStats() {
    const now = Date.now();
    const entries = Array.from(this.cache.entries());
    const expired = entries.filter(([_, value]) => now - value.timestamp >= value.ttl);

    return {
      totalEntries: entries.length,
      expiredEntries: expired.length,
      pendingRequests: this.pendingRequests.size,
      cacheHitRate: entries.length > 0 ? ((entries.length - expired.length) / entries.length) * 100 : 0
    };
  }
}

export const requestDeduplicator = new RequestDeduplicator();

// =============================================================================
// VIRTUAL SCROLLING
// =============================================================================

interface VirtualListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  estimateSize?: () => number;
  overscan?: number;
  className?: string;
}

/**
 * Virtual scrolling component for large lists
 */
export function VirtualList<T>({
  items,
  renderItem,
  estimateSize = () => 60,
  overscan = 5,
  className = "h-full overflow-auto"
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtual({
    size: items.length,
    parentRef,
    estimateSize: useCallback(estimateSize, [estimateSize]),
    overscan
  });

  return (
    <div ref={parentRef} className={className}>
      <div
        style={{
          height: `${rowVirtualizer.totalSize}px`,
          width: '100%',
          position: 'relative'
        }}
      >
        {rowVirtualizer.virtualItems.map(virtualRow => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualRow.size}px`,
              transform: `translateY(${virtualRow.start}px)`
            }}
          >
            {renderItem(items[virtualRow.index], virtualRow.index)}
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// OPTIMIZED IMAGE LOADING
// =============================================================================

interface OptimizedImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  alt: string;
  placeholder?: string;
  threshold?: number;
}

/**
 * Optimized image component with lazy loading and intersection observer
 */
export const OptimizedImage = ({
  src,
  alt,
  placeholder = '/placeholder.svg',
  threshold = 0.1,
  className = '',
  ...props
}: OptimizedImageProps) => {
  const [imageSrc, setImageSrc] = useState<string>(placeholder);
  const [isLoaded, setIsLoaded] = useState(false);
  const [isError, setIsError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          // Preload the image
          const img = new Image();
          img.onload = () => {
            setImageSrc(src);
            setIsLoaded(true);
          };
          img.onerror = () => {
            setIsError(true);
          };
          img.src = src;

          observer.disconnect();
        }
      },
      { threshold }
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }

    return () => observer.disconnect();
  }, [src, threshold]);

  return (
    <div className={`relative ${className}`}>
      <img
        ref={imgRef}
        src={imageSrc}
        alt={alt}
        loading="lazy"
        className={`transition-opacity duration-300 ${
          isLoaded ? 'opacity-100' : 'opacity-70'
        } ${className}`}
        {...props}
      />

      {!isLoaded && !isError && (
        <div className="absolute inset-0 bg-gray-200 animate-pulse rounded" />
      )}

      {isError && (
        <div className="absolute inset-0 bg-gray-100 flex items-center justify-center">
          <span className="text-gray-400 text-sm">Failed to load image</span>
        </div>
      )}
    </div>
  );
};

// =============================================================================
// PERFORMANCE MONITORING
// =============================================================================

/**
 * Performance monitoring utility
 */
export class PerformanceMonitor {
  private metrics: Map<string, number[]> = new Map();

  /**
   * Mark the start of a performance measurement
   */
  mark(name: string): () => void {
    const startTime = performance.now();

    return () => {
      const duration = performance.now() - startTime;

      if (!this.metrics.has(name)) {
        this.metrics.set(name, []);
      }

      this.metrics.get(name)!.push(duration);

      // Keep only last 100 measurements
      const measurements = this.metrics.get(name)!;
      if (measurements.length > 100) {
        measurements.shift();
      }
    };
  }

  /**
   * Get performance statistics for a metric
   */
  getStats(name: string) {
    const measurements = this.metrics.get(name) || [];

    if (measurements.length === 0) {
      return null;
    }

    const sorted = [...measurements].sort((a, b) => a - b);
    const avg = measurements.reduce((a, b) => a + b, 0) / measurements.length;
    const p50 = sorted[Math.floor(sorted.length * 0.5)];
    const p95 = sorted[Math.floor(sorted.length * 0.95)];
    const p99 = sorted[Math.floor(sorted.length * 0.99)];

    return {
      count: measurements.length,
      avg: Math.round(avg * 100) / 100,
      min: Math.min(...measurements),
      max: Math.max(...measurements),
      p50: Math.round(p50 * 100) / 100,
      p95: Math.round(p95 * 100) / 100,
      p99: Math.round(p99 * 100) / 100
    };
  }

  /**
   * Get all performance metrics
   */
  getAllStats() {
    const stats: Record<string, any> = {};

    for (const [name] of this.metrics) {
      stats[name] = this.getStats(name);
    }

    return stats;
  }

  /**
   * Clear all metrics
   */
  clear() {
    this.metrics.clear();
  }
}

export const performanceMonitor = new PerformanceMonitor();

// =============================================================================
// DEBOUNCE AND THROTTLE UTILITIES
// =============================================================================

/**
 * Debounce hook for performance optimization
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Throttle hook for performance optimization
 */
export function useThrottle<T>(value: T, limit: number): T {
  const [throttledValue, setThrottledValue] = useState(value);
  const lastRan = useRef(Date.now());

  useEffect(() => {
    const handler = setTimeout(() => {
      if (Date.now() - lastRan.current >= limit) {
        setThrottledValue(value);
        lastRan.current = Date.now();
      }
    }, limit - (Date.now() - lastRan.current));

    return () => {
      clearTimeout(handler);
    };
  }, [value, limit]);

  return throttledValue;
}

// =============================================================================
// BUNDLE SIZE MONITORING
// =============================================================================

/**
 * Log bundle size information (development only)
 */
export const logBundleSize = () => {
  if (process.env.NODE_ENV === 'development') {
    // This will be replaced by webpack-bundle-analyzer in build
    console.log('📦 Bundle analysis available in build mode');
  }
};

/**
 * Memory usage monitoring (development only)
 */
export const monitorMemoryUsage = () => {
  if (process.env.NODE_ENV === 'development' && 'memory' in performance) {
    const memory = (performance as any).memory;
    console.log('🧠 Memory Usage:', {
      used: Math.round(memory.usedJSHeapSize / 1024 / 1024) + ' MB',
      total: Math.round(memory.totalJSHeapSize / 1024 / 1024) + ' MB',
      limit: Math.round(memory.jsHeapSizeLimit / 1024 / 1024) + ' MB'
    });
  }
};

// Export all utilities
export {
  LoadingSpinner,
  requestDeduplicator,
  performanceMonitor
};