# 🎨 FASE 4: Constructor Visual de Workflows

## 📋 **OBJETIVO PRINCIPAL**
Crear una interfaz visual drag & drop usando React Flow para que los usuarios puedan diseñar workflows de forma intuitiva sin conocimiento técnico.

---

## 🏗️ **COMPONENTES A IMPLEMENTAR**

### **1. Frontend React App** 🔄
```
agentos-frontend/
├── src/
│   ├── components/
│   │   ├── WorkflowBuilder/           # 🔄 Main builder component
│   │   │   ├── WorkflowCanvas.tsx     # 🔄 React Flow canvas
│   │   │   ├── NodePalette.tsx        # 🔄 Drag & drop palette
│   │   │   ├── PropertyPanel.tsx      # 🔄 Node configuration panel
│   │   │   └── ValidationPanel.tsx    # 🔄 Real-time validation
│   │   │
│   │   ├── Nodes/                     # 🔄 Custom React Flow nodes
│   │   │   ├── AgentNode.tsx          # 🔄 Agent task nodes
│   │   │   ├── ConditionNode.tsx      # 🔄 Condition logic nodes
│   │   │   ├── ParallelNode.tsx       # 🔄 Parallel execution nodes
│   │   │   ├── LoopNode.tsx           # 🔄 Loop nodes
│   │   │   └── WebhookNode.tsx        # 🔄 Webhook nodes
│   │   │
│   │   ├── Templates/                 # 🔄 Template management
│   │   │   ├── TemplateGallery.tsx    # 🔄 Browse templates
│   │   │   ├── TemplatePreview.tsx    # 🔄 Preview templates
│   │   │   └── TemplateInstaller.tsx  # 🔄 Install & customize
│   │   │
│   │   └── Execution/                 # 🔄 Workflow execution
│   │       ├── ExecutionMonitor.tsx   # 🔄 Real-time monitoring
│   │       ├── ExecutionHistory.tsx   # 🔄 Execution history
│   │       └── ExecutionLogs.tsx      # 🔄 Detailed logs
│   │
│   ├── hooks/                         # 🔄 Custom React hooks
│   │   ├── useWorkflowBuilder.ts      # 🔄 Workflow state management
│   │   ├── useWorkflowValidation.ts   # 🔄 Real-time validation
│   │   ├── useTemplateManager.ts      # 🔄 Template operations
│   │   └── useExecutionMonitor.ts     # 🔄 Execution monitoring
│   │
│   ├── services/                      # 🔄 API integration
│   │   ├── orchestrationAPI.ts        # 🔄 Orchestration endpoints
│   │   ├── templatesAPI.ts            # 🔄 Template endpoints
│   │   └── executionAPI.ts            # 🔄 Execution endpoints
│   │
│   └── utils/                         # 🔄 Utilities
│       ├── workflowConverter.ts       # 🔄 Convert visual to JSON
│       ├── nodeFactory.ts             # 🔄 Create React Flow nodes
│       └── validationUtils.ts         # 🔄 Validation helpers
```

### **2. React Flow Integration** 🔄

#### **Custom Node Types**
```typescript
// AgentNode.tsx - Nodo para tareas de agentes
interface AgentNodeData {
  agentType: 'copywriter' | 'researcher' | 'scheduler' | 'email_responder' | 'data_analyzer';
  taskPrompt: string;
  parameters: Record<string, any>;
  outputVariable?: string;
  timeout: number;
}

// ConditionNode.tsx - Nodo para lógica condicional
interface ConditionNodeData {
  conditions: Array<{
    variable: string;
    operator: string;
    value: any;
  }>;
  truePath: string;
  falsePath?: string;
}

// ParallelNode.tsx - Nodo para ejecución paralela
interface ParallelNodeData {
  steps: string[];
  waitForAll: boolean;
  continueOnError: boolean;
}
```

#### **Custom Edge Types**
```typescript
// ConditionalEdge.tsx - Conexión condicional
interface ConditionalEdgeData {
  condition?: {
    variable: string;
    operator: string;
    value: any;
  };
  label: string;
  style: 'success' | 'error' | 'default';
}
```

### **3. Drag & Drop System** 🔄

#### **Node Palette Component**
```typescript
const NodePalette = () => {
  const nodeTypes = [
    {
      type: 'agent',
      category: 'Agents',
      items: [
        { id: 'copywriter', name: 'Copywriter', icon: '✍️', description: 'Create marketing content' },
        { id: 'researcher', name: 'Researcher', icon: '🔍', description: 'Research and analysis' },
        { id: 'scheduler', name: 'Scheduler', icon: '📅', description: 'Calendar management' },
        { id: 'email_responder', name: 'Email Responder', icon: '📧', description: 'Email automation' },
        { id: 'data_analyzer', name: 'Data Analyzer', icon: '📊', description: 'Data analysis' }
      ]
    },
    {
      type: 'logic',
      category: 'Logic',
      items: [
        { id: 'condition', name: 'Condition', icon: '🔀', description: 'Conditional branching' },
        { id: 'parallel', name: 'Parallel', icon: '⚡', description: 'Parallel execution' },
        { id: 'loop', name: 'Loop', icon: '🔄', description: 'Iterate over data' }
      ]
    },
    {
      type: 'integration',
      category: 'Integration',
      items: [
        { id: 'webhook', name: 'Webhook', icon: '🔗', description: 'HTTP requests' },
        { id: 'delay', name: 'Delay', icon: '⏱️', description: 'Wait/pause execution' },
        { id: 'human_approval', name: 'Human Approval', icon: '👤', description: 'Manual approval' }
      ]
    }
  ];

  return (
    <div className="node-palette">
      {nodeTypes.map(category => (
        <div key={category.type} className="palette-category">
          <h3>{category.category}</h3>
          {category.items.map(item => (
            <div
              key={item.id}
              className="palette-item"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/reactflow', JSON.stringify({
                  type: item.id,
                  category: category.type
                }));
              }}
            >
              <span className="icon">{item.icon}</span>
              <div>
                <div className="name">{item.name}</div>
                <div className="description">{item.description}</div>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};
```

### **4. Property Panel** 🔄

#### **Dynamic Configuration**
```typescript
const PropertyPanel = ({ selectedNode }) => {
  const [nodeData, setNodeData] = useState(selectedNode?.data || {});

  const renderAgentConfig = () => (
    <div className="agent-config">
      <div className="form-group">
        <label>Agent Type</label>
        <select value={nodeData.agentType} onChange={handleAgentTypeChange}>
          <option value="copywriter">Copywriter</option>
          <option value="researcher">Researcher</option>
          <option value="scheduler">Scheduler</option>
          <option value="email_responder">Email Responder</option>
          <option value="data_analyzer">Data Analyzer</option>
        </select>
      </div>

      <div className="form-group">
        <label>Task Prompt</label>
        <textarea
          value={nodeData.taskPrompt}
          onChange={handlePromptChange}
          placeholder="Describe the task for this agent..."
          rows={4}
        />
        <div className="prompt-variables">
          <small>Available variables: {availableVariables.join(', ')}</small>
        </div>
      </div>

      <div className="form-group">
        <label>Output Variable</label>
        <input
          type="text"
          value={nodeData.outputVariable}
          onChange={handleOutputVariableChange}
          placeholder="variable_name"
        />
      </div>

      <div className="form-group">
        <label>Parameters</label>
        <JsonEditor
          value={nodeData.parameters}
          onChange={handleParametersChange}
        />
      </div>

      <div className="form-group">
        <label>Timeout (seconds)</label>
        <input
          type="number"
          value={nodeData.timeout}
          onChange={handleTimeoutChange}
          min={10}
          max={3600}
        />
      </div>
    </div>
  );

  const renderConditionConfig = () => (
    <div className="condition-config">
      <div className="conditions-list">
        {nodeData.conditions?.map((condition, index) => (
          <div key={index} className="condition-item">
            <select
              value={condition.variable}
              onChange={(e) => updateCondition(index, 'variable', e.target.value)}
            >
              <option value="">Select variable...</option>
              {availableVariables.map(var => (
                <option key={var} value={var}>{var}</option>
              ))}
            </select>

            <select
              value={condition.operator}
              onChange={(e) => updateCondition(index, 'operator', e.target.value)}
            >
              <option value="equals">Equals</option>
              <option value="not_equals">Not Equals</option>
              <option value="greater_than">Greater Than</option>
              <option value="less_than">Less Than</option>
              <option value="contains">Contains</option>
              <option value="is_empty">Is Empty</option>
            </select>

            <input
              type="text"
              value={condition.value}
              onChange={(e) => updateCondition(index, 'value', e.target.value)}
              placeholder="Value"
            />

            <button onClick={() => removeCondition(index)}>Remove</button>
          </div>
        ))}
      </div>

      <button onClick={addCondition}>Add Condition</button>

      <div className="form-group">
        <label>True Path</label>
        <NodeSelector
          value={nodeData.truePath}
          onChange={handleTruePathChange}
          availableNodes={getAvailableNextNodes()}
        />
      </div>

      <div className="form-group">
        <label>False Path (Optional)</label>
        <NodeSelector
          value={nodeData.falsePath}
          onChange={handleFalsePathChange}
          availableNodes={getAvailableNextNodes()}
        />
      </div>
    </div>
  );

  return (
    <div className="property-panel">
      <h3>Node Configuration</h3>
      {selectedNode ? (
        <>
          <div className="node-header">
            <input
              type="text"
              value={nodeData.name}
              onChange={handleNameChange}
              className="node-name-input"
            />
          </div>

          <div className="node-description">
            <textarea
              value={nodeData.description}
              onChange={handleDescriptionChange}
              placeholder="Describe what this step does..."
              rows={2}
            />
          </div>

          <div className="node-config">
            {selectedNode.type === 'agent' && renderAgentConfig()}
            {selectedNode.type === 'condition' && renderConditionConfig()}
            {selectedNode.type === 'parallel' && renderParallelConfig()}
            {selectedNode.type === 'loop' && renderLoopConfig()}
            {selectedNode.type === 'webhook' && renderWebhookConfig()}
          </div>

          <div className="node-actions">
            <button onClick={duplicateNode}>Duplicate</button>
            <button onClick={deleteNode} className="danger">Delete</button>
          </div>
        </>
      ) : (
        <div className="no-selection">
          <p>Select a node to configure its properties</p>
        </div>
      )}
    </div>
  );
};
```

### **5. Real-time Validation** 🔄

#### **Validation Hook**
```typescript
const useWorkflowValidation = (nodes, edges) => {
  const [validation, setValidation] = useState({
    isValid: true,
    errors: [],
    warnings: [],
    suggestions: []
  });

  useEffect(() => {
    const validateWorkflow = async () => {
      // Convert visual workflow to JSON schema
      const workflowDefinition = convertNodesToWorkflow(nodes, edges);

      try {
        // Call backend validation API
        const response = await orchestrationAPI.validateWorkflow(workflowDefinition);
        setValidation(response);
      } catch (error) {
        setValidation({
          isValid: false,
          errors: [error.message],
          warnings: [],
          suggestions: []
        });
      }
    };

    // Debounce validation
    const timeoutId = setTimeout(validateWorkflow, 500);
    return () => clearTimeout(timeoutId);
  }, [nodes, edges]);

  return validation;
};
```

#### **Validation Panel Component**
```typescript
const ValidationPanel = ({ validation }) => {
  const { isValid, errors, warnings, suggestions } = validation;

  return (
    <div className={`validation-panel ${isValid ? 'valid' : 'invalid'}`}>
      <div className="validation-header">
        <span className={`status-icon ${isValid ? 'success' : 'error'}`}>
          {isValid ? '✅' : '❌'}
        </span>
        <h3>Workflow Validation</h3>
      </div>

      {errors.length > 0 && (
        <div className="validation-section errors">
          <h4>Errors</h4>
          <ul>
            {errors.map((error, index) => (
              <li key={index} className="error-item">
                <span className="icon">❌</span>
                {error}
              </li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="validation-section warnings">
          <h4>Warnings</h4>
          <ul>
            {warnings.map((warning, index) => (
              <li key={index} className="warning-item">
                <span className="icon">⚠️</span>
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="validation-section suggestions">
          <h4>Optimization Suggestions</h4>
          <ul>
            {suggestions.map((suggestion, index) => (
              <li key={index} className="suggestion-item">
                <span className="icon">💡</span>
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}

      {isValid && errors.length === 0 && warnings.length === 0 && (
        <div className="validation-success">
          <p>✅ Workflow is valid and ready to execute!</p>
        </div>
      )}
    </div>
  );
};
```

### **6. Template Integration** 🔄

#### **Template Gallery**
```typescript
const TemplateGallery = () => {
  const [templates, setTemplates] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const loadTemplates = async () => {
      const response = await templatesAPI.getTemplates();
      setTemplates(response);
    };
    loadTemplates();
  }, []);

  const filteredTemplates = templates.filter(template => {
    const matchesCategory = selectedCategory === 'all' || template.category === selectedCategory;
    const matchesSearch = template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         template.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="template-gallery">
      <div className="gallery-header">
        <h2>Workflow Templates</h2>
        <div className="gallery-controls">
          <input
            type="text"
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="category-filter"
          >
            <option value="all">All Categories</option>
            <option value="marketing">Marketing</option>
            <option value="customer_service">Customer Service</option>
            <option value="research">Research</option>
            <option value="sales">Sales</option>
            <option value="analytics">Analytics</option>
          </select>
        </div>
      </div>

      <div className="templates-grid">
        {filteredTemplates.map(template => (
          <TemplateCard
            key={template.id}
            template={template}
            onPreview={() => handlePreviewTemplate(template)}
            onInstall={() => handleInstallTemplate(template)}
          />
        ))}
      </div>
    </div>
  );
};

const TemplateCard = ({ template, onPreview, onInstall }) => (
  <div className="template-card">
    <div className="template-header">
      <h3>{template.name}</h3>
      <span className="template-category">{template.category}</span>
    </div>

    <p className="template-description">{template.description}</p>

    <div className="template-tags">
      {template.tags.map(tag => (
        <span key={tag} className="tag">{tag}</span>
      ))}
    </div>

    <div className="template-stats">
      <span className="downloads">📥 {template.download_count}</span>
      <span className="rating">⭐ {template.rating.toFixed(1)}</span>
    </div>

    <div className="template-actions">
      <button onClick={onPreview} className="btn-secondary">Preview</button>
      <button onClick={onInstall} className="btn-primary">Install</button>
    </div>
  </div>
);
```

### **7. Execution Monitoring** 🔄

#### **Real-time Execution Monitor**
```typescript
const ExecutionMonitor = ({ executionId }) => {
  const [execution, setExecution] = useState(null);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    if (!executionId) return;

    // Connect to WebSocket for real-time updates
    const ws = new WebSocket(`ws://localhost:8000/api/v1/orchestration/executions/${executionId}/stream`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents(prev => [...prev, data]);

      if (data.type === 'step_completed' || data.type === 'step_failed') {
        // Update execution status
        updateExecutionStatus(executionId);
      }
    };

    return () => ws.close();
  }, [executionId]);

  const updateExecutionStatus = async (id) => {
    const status = await executionAPI.getExecutionStatus(id);
    setExecution(status);
  };

  return (
    <div className="execution-monitor">
      <div className="execution-header">
        <h3>Workflow Execution</h3>
        {execution && (
          <div className="execution-status">
            <span className={`status-badge ${execution.status}`}>
              {execution.status}
            </span>
            {execution.duration_seconds && (
              <span className="duration">
                {formatDuration(execution.duration_seconds)}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="execution-timeline">
        {events.map((event, index) => (
          <div key={index} className={`timeline-event ${event.event_type}`}>
            <div className="event-time">
              {formatTime(event.timestamp)}
            </div>
            <div className="event-content">
              <div className="event-title">
                {getEventIcon(event.event_type)} {event.step_name}
              </div>
              <div className="event-details">
                {event.event_type === 'started' && 'Started execution'}
                {event.event_type === 'completed' && 'Completed successfully'}
                {event.event_type === 'failed' && `Failed: ${event.data?.error}`}
              </div>
            </div>
          </div>
        ))}
      </div>

      {execution?.status === 'active' && (
        <div className="execution-controls">
          <button
            onClick={() => executionAPI.pauseExecution(executionId)}
            className="btn-secondary"
          >
            Pause
          </button>
          <button
            onClick={() => executionAPI.cancelExecution(executionId)}
            className="btn-danger"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};
```

---

## 🎯 **FEATURES CLAVE A IMPLEMENTAR**

### **1. Drag & Drop Workflow Builder** 🔄
- **Visual Canvas**: React Flow con zoom, pan, minimap
- **Node Palette**: Biblioteca de nodos disponibles
- **Smart Connections**: Auto-conexión con validación
- **Grid Snap**: Alineación automática de nodos

### **2. Dynamic Node Configuration** 🔄
- **Property Panel**: Configuración contextual por tipo de nodo
- **Variable Management**: Sistema de variables workflow-wide
- **Prompt Templates**: Templates de prompts por agente
- **Parameter Validation**: Validación en tiempo real

### **3. Real-time Validation** 🔄
- **Syntax Validation**: Validación de estructura de workflow
- **Logic Validation**: Detección de loops, dead ends
- **Resource Validation**: Verificación de agentes disponibles
- **Performance Hints**: Sugerencias de optimización

### **4. Template System Integration** 🔄
- **Template Gallery**: Explorar templates disponibles
- **Preview Mode**: Vista previa de templates
- **Installation Wizard**: Customización durante instalación
- **Template Sharing**: Exportar workflows como templates

### **5. Execution Integration** 🔄
- **One-click Execution**: Ejecutar workflows desde el builder
- **Real-time Monitoring**: Seguimiento visual de ejecución
- **Debug Mode**: Ejecución paso a paso
- **Execution History**: Historial de ejecuciones

---

## 🛠️ **STACK TECNOLÓGICO**

### **Frontend** 🔄
- **Framework**: Next.js 14 + TypeScript
- **UI Library**: React Flow + Tailwind CSS
- **State Management**: Zustand
- **API Client**: React Query + Axios
- **WebSocket**: Native WebSocket API
- **Icons**: Lucide React

### **Components** 🔄
- **React Flow**: Para el canvas visual
- **React Hook Form**: Para formularios de configuración
- **React Query**: Para gestión de estado servidor
- **Framer Motion**: Para animaciones
- **React Hot Toast**: Para notificaciones

---

## 📊 **ENTREGABLES ESPERADOS**

1. **🎨 Workflow Builder UI**: Interfaz completa drag & drop
2. **🔧 Node Configuration System**: Panel de propiedades dinámico
3. **✅ Real-time Validation**: Validación visual en tiempo real
4. **📚 Template Integration**: Galería e instalación de templates
5. **📊 Execution Monitoring**: Monitor visual de ejecuciones
6. **🔄 WebSocket Integration**: Streaming en tiempo real
7. **📱 Responsive Design**: Funcional en desktop y tablet
8. **🧪 E2E Testing**: Tests de integración completos

---

## 🎯 **SUCCESS CRITERIA**

- **✅ Usabilidad**: Usuarios no técnicos pueden crear workflows
- **✅ Performance**: Canvas fluido con 100+ nodos
- **✅ Validation**: Errores detectados antes de ejecución
- **✅ Templates**: Instalación one-click de templates
- **✅ Monitoring**: Seguimiento visual en tiempo real
- **✅ Responsive**: Funcional en diferentes resoluciones

La FASE 4 transformará AgentOS en una plataforma verdaderamente visual y accesible para usuarios no técnicos. 🚀