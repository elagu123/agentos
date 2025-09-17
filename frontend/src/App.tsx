import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { WorkflowBuilder } from './components/workflow-builder/WorkflowBuilder';
import './index.css';

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
    <QueryClientProvider client={queryClient}>
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

        {/* Main Workflow Builder */}
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
    </QueryClientProvider>
  );
}

export default App;