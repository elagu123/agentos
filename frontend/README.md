# AgentOS Frontend - Visual Workflow Builder

A React-based visual workflow builder for creating and managing multi-agent orchestration workflows.

## 🚀 Features

### ✅ **Visual Workflow Designer**
- **Drag & Drop Interface**: Intuitive node-based workflow creation
- **Custom Node Types**: 8+ specialized node types (agents, control flow, integrations)
- **Real-time Validation**: Live validation with visual feedback
- **Connection Editor**: Visual connection management with conditions

### ✅ **Agent Integration**
- **5 Specialized Agents**: Copywriter, Researcher, Scheduler, Email Responder, Data Analyzer
- **Custom Node Styling**: Color-coded nodes by agent type
- **Configuration Panel**: Dynamic property editing per node type
- **Capability Discovery**: Auto-discovery of agent capabilities

### ✅ **Template System**
- **Template Gallery**: Browse and install pre-built workflows
- **Category Filtering**: Filter by business use case
- **One-click Installation**: Install templates with customization
- **Template Preview**: Visual preview before installation

### ✅ **Execution Monitoring**
- **Real-time Tracking**: Live execution status with WebSocket
- **Step-by-step Progress**: Detailed step execution monitoring
- **Error Handling**: Visual error display and retry tracking
- **Performance Metrics**: Duration and success rate tracking

### ✅ **Import/Export**
- **Multiple Formats**: JSON and YAML export support
- **File Operations**: Import/export via file system
- **Clipboard Support**: Copy/paste workflow definitions
- **Validation**: Import validation with error reporting

## 🏗️ **Architecture**

```
frontend/
├── src/
│   ├── components/
│   │   └── workflow-builder/
│   │       ├── WorkflowBuilder.tsx      # Main canvas component
│   │       ├── NodeTypes.tsx            # Custom React Flow nodes
│   │       ├── NodePalette.tsx          # Drag & drop palette
│   │       ├── PropertiesPanel.tsx      # Node configuration
│   │       ├── TemplateGallery.tsx      # Template browser
│   │       └── ExecutionMonitor.tsx     # Real-time monitoring
│   │
│   ├── hooks/
│   │   └── useWorkflowAPI.ts            # React Query hooks
│   │
│   ├── types/
│   │   └── workflow.ts                  # TypeScript definitions
│   │
│   ├── utils/
│   │   ├── workflowValidation.ts        # Client-side validation
│   │   └── workflowImportExport.ts      # Import/export utilities
│   │
│   ├── App.tsx                          # Main application
│   └── index.tsx                        # Entry point
│
├── package.json                         # Dependencies
├── tailwind.config.js                   # Styling configuration
└── tsconfig.json                        # TypeScript configuration
```

## 🛠️ **Tech Stack**

### **Core Framework**
- **React 18**: Modern React with hooks and concurrent features
- **TypeScript**: Full type safety for workflow definitions
- **React Flow**: Professional graph visualization library

### **State Management**
- **React Query**: Server state management and caching
- **Zustand**: Lightweight client state management
- **React Hook Form**: Form state and validation

### **UI/UX**
- **Tailwind CSS**: Utility-first CSS framework
- **Headless UI**: Accessible UI components
- **Lucide Icons**: Consistent icon system
- **React Hot Toast**: User notifications

### **Validation & Schema**
- **Zod**: Runtime type validation
- **Client-side Validation**: Real-time workflow validation
- **Error Boundaries**: Graceful error handling

## 🎨 **Component System**

### **Node Types**
```typescript
// 8 different node types supported
- agent_task       // AI agent execution
- conditional      // Branching logic
- loop            // Iteration control
- parallel        // Concurrent execution
- webhook         // External API calls
- delay           // Time-based delays
- user_input      // Human interaction
- data_transformation // Data processing
```

### **Custom Styling**
- **Agent Colors**: Color-coded by agent type
- **Status Indicators**: Visual execution state
- **Validation Feedback**: Real-time error highlighting
- **Responsive Design**: Works on all screen sizes

## 🔧 **Development**

### **Installation**
```bash
cd frontend
npm install
```

### **Development Server**
```bash
npm start
# Opens http://localhost:3000
```

### **Build for Production**
```bash
npm run build
```

### **Testing**
```bash
npm test
```

## 🌟 **Key Features Detail**

### **1. Visual Workflow Builder**
- **React Flow Integration**: Professional node-graph editor
- **Custom Node Components**: Specialized UI for each agent type
- **Handle System**: Visual connection points for workflow links
- **Real-time Updates**: Live workflow state synchronization

### **2. Node Palette**
- **Categorized Nodes**: Organized by functionality
- **Drag & Drop**: Intuitive node placement
- **Search & Filter**: Quick node discovery
- **Usage Instructions**: Built-in help system

### **3. Properties Panel**
- **Dynamic Forms**: Context-aware configuration
- **Validation**: Real-time input validation
- **Type Safety**: TypeScript-enforced schemas
- **Auto-save**: Seamless configuration updates

### **4. Template Gallery**
- **Rich Preview**: Visual workflow representation
- **Metadata Display**: Author, ratings, download counts
- **Tag System**: Searchable categorization
- **Installation Flow**: One-click template deployment

### **5. Execution Monitor**
- **WebSocket Connection**: Real-time execution updates
- **Progress Tracking**: Step-by-step progress visualization
- **Error Display**: Detailed error information
- **Performance Metrics**: Execution time and success rates

## 🔌 **API Integration**

### **Backend Communication**
```typescript
// React Query hooks for API communication
useWorkflows()          // List workflows
useWorkflow(id)         // Get workflow details
useCreateWorkflow()     // Create new workflow
useExecuteWorkflow()    // Execute workflow
useTemplates()          // Browse templates
useExecution(id)        // Monitor execution
```

### **WebSocket Integration**
```typescript
// Real-time execution monitoring
const ws = new WebSocket('/api/v1/orchestration/executions/{id}/stream');
ws.onmessage = (event) => {
  const stepEvent = JSON.parse(event.data);
  updateExecutionState(stepEvent);
};
```

## 📱 **User Experience**

### **Workflow Creation Flow**
1. **Open Node Palette** → Browse available agents and components
2. **Drag Nodes** → Place nodes on the canvas
3. **Configure Properties** → Set up node-specific settings
4. **Connect Nodes** → Create workflow logic flow
5. **Validate Workflow** → Real-time validation feedback
6. **Save & Execute** → Deploy and monitor execution

### **Template Usage Flow**
1. **Browse Gallery** → Explore pre-built templates
2. **Preview Template** → See workflow structure
3. **Install Template** → One-click installation
4. **Customize** → Modify template to fit needs
5. **Execute** → Run customized workflow

## 🔍 **Advanced Features**

### **Real-time Validation**
- **Cycle Detection**: Prevents infinite loops
- **Dependency Validation**: Ensures proper step ordering
- **Configuration Validation**: Validates node-specific settings
- **Visual Feedback**: Instant error highlighting

### **Import/Export System**
- **JSON Format**: Standard workflow serialization
- **YAML Support**: Human-readable format option
- **File Operations**: Save/load from file system
- **Clipboard Integration**: Copy/paste workflows

### **Execution Monitoring**
- **Live Progress**: Real-time step execution tracking
- **Error Handling**: Detailed error information
- **Retry Logic**: Visual retry attempt tracking
- **Performance Metrics**: Duration and success analytics

## 🎯 **Future Enhancements**

### **Phase 5 Roadmap**
- **Collaborative Editing**: Multi-user workflow editing
- **Version Control**: Workflow versioning and history
- **Advanced Analytics**: Detailed execution analytics
- **Custom Themes**: User-customizable visual themes
- **Mobile Support**: Touch-optimized interface

This frontend implementation provides a complete visual workflow builder that seamlessly integrates with the AgentOS backend orchestration system.