import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ClerkProvider, SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react';
import { Toaster } from 'react-hot-toast';

// Pages
import Dashboard from './pages/dashboard/index';
import ChatPage from './pages/dashboard/chat';
import WorkflowsPage from './pages/dashboard/workflows';
import AnalyticsPage from './pages/dashboard/analytics';

// Components
import { WorkflowBuilder } from './components/workflow-builder/WorkflowBuilder';

import './index.css';

// Clerk publishable key - in production this should come from environment variables
const CLERK_PUBLISHABLE_KEY = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || 'pk_test_your-key-here';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

function App() {
  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      <QueryClientProvider client={queryClient}>
        <Router>
          <div className="App">
            {/* Toast Notifications */}
            <Toaster
              position="top-right"
              toastOptions={{
                duration: 4000,
                style: {
                  background: '#363636',
                  color: '#fff',
                },
                success: {
                  duration: 3000,
                  iconTheme: {
                    primary: '#4ade80',
                    secondary: '#fff',
                  },
                },
                error: {
                  duration: 5000,
                  iconTheme: {
                    primary: '#ef4444',
                    secondary: '#fff',
                  },
                },
              }}
            />

            {/* Protected Routes */}
            <SignedIn>
              <Routes>
                {/* Dashboard Routes */}
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/dashboard/chat" element={<ChatPage />} />
                <Route path="/dashboard/workflows" element={<WorkflowsPage />} />
                <Route path="/dashboard/workflows/create" element={<WorkflowBuilderPage />} />
                <Route path="/dashboard/analytics" element={<AnalyticsPage />} />

                {/* Redirect root to dashboard */}
                <Route path="/" element={<Navigate to="/dashboard" replace />} />

                {/* Catch all - redirect to dashboard */}
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </SignedIn>

            {/* Redirect to sign in if not authenticated */}
            <SignedOut>
              <RedirectToSignIn />
            </SignedOut>
          </div>
        </Router>
      </QueryClientProvider>
    </ClerkProvider>
  );
}

// Wrapper component for the workflow builder
function WorkflowBuilderPage() {
  return (
    <div className="h-screen">
      <WorkflowBuilder
        mode="create"
        onSave={(workflow) => {
          console.log('Workflow saved:', workflow);
        }}
        onExecute={(workflowId, variables) => {
          console.log('Workflow executed:', workflowId, variables);
        }}
      />
    </div>
  );
}

export default App;