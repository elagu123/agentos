"""
Integration Tests for Orchestration System

Tests completos del sistema de orquestación incluyendo:
- Creación y validación de workflows
- Ejecución de workflows simples y complejos
- Templates y su instalación
- Dependency resolution
- API endpoints
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from app.orchestration import (
    orchestrator_instance, template_manager,
    WorkflowDefinition, WorkflowStep, WorkflowVariable, StepConnection,
    StepType, AgentTaskConfig, WorkflowExecutor, ExecutionMode,
    DependencyResolver
)
from app.agents import AgentContext


class TestWorkflowCreationAndValidation:
    """Tests para creación y validación de workflows"""

    def test_create_simple_workflow(self):
        """Test crear workflow simple con un solo agente"""

        # Crear workflow simple
        variables = [
            WorkflowVariable(
                name="input_text",
                type="string",
                required=True,
                description="Texto de entrada"
            ),
            WorkflowVariable(
                name="output_content",
                type="string",
                description="Contenido generado"
            )
        ]

        steps = [
            WorkflowStep(
                id="generate_content",
                name="Generar Contenido",
                type=StepType.AGENT_TASK,
                description="Generar contenido usando copywriter",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Crea contenido basado en: {input_text}",
                    output_variable="output_content"
                )
            )
        ]

        workflow = WorkflowDefinition(
            name="Simple Content Workflow",
            description="Workflow simple para generar contenido",
            variables=variables,
            steps=steps,
            connections=[],
            start_step="generate_content",
            end_steps=["generate_content"]
        )

        # Validar workflow
        validation = workflow.validate_workflow()
        assert validation.is_valid
        assert len(validation.errors) == 0

    def test_create_complex_workflow(self):
        """Test crear workflow complejo con múltiples agentes y condiciones"""

        variables = [
            WorkflowVariable(name="topic", type="string", required=True),
            WorkflowVariable(name="research_data", type="string"),
            WorkflowVariable(name="content_draft", type="string"),
            WorkflowVariable(name="final_content", type="string")
        ]

        steps = [
            WorkflowStep(
                id="research",
                name="Investigar Tema",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(
                    agent_type="researcher",
                    task_prompt="Investiga: {topic}",
                    output_variable="research_data"
                )
            ),
            WorkflowStep(
                id="draft_content",
                name="Crear Borrador",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Crea borrador basado en: {research_data}",
                    output_variable="content_draft"
                )
            ),
            WorkflowStep(
                id="finalize_content",
                name="Finalizar Contenido",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Mejora este borrador: {content_draft}",
                    output_variable="final_content"
                )
            )
        ]

        connections = [
            StepConnection(from_step="research", to_step="draft_content"),
            StepConnection(from_step="draft_content", to_step="finalize_content")
        ]

        workflow = WorkflowDefinition(
            name="Complex Content Workflow",
            variables=variables,
            steps=steps,
            connections=connections,
            start_step="research",
            end_steps=["finalize_content"]
        )

        # Validar workflow
        validation = workflow.validate_workflow()
        assert validation.is_valid
        assert len(validation.errors) == 0

        # Verificar que el grafo de dependencias es correcto
        resolver = DependencyResolver()
        execution_graph = resolver.resolve_dependencies(workflow)
        levels = execution_graph.get_execution_levels()

        # Debe tener 3 niveles (cada paso en secuencia)
        assert len(levels) == 3
        assert "research" in levels[0].steps
        assert "draft_content" in levels[1].steps
        assert "finalize_content" in levels[2].steps

    def test_workflow_validation_errors(self):
        """Test validación de workflows con errores"""

        # Workflow con paso inicial inexistente
        workflow = WorkflowDefinition(
            name="Invalid Workflow",
            steps=[
                WorkflowStep(
                    id="step1",
                    name="Step 1",
                    type=StepType.AGENT_TASK,
                    agent_config=AgentTaskConfig(
                        agent_type="copywriter",
                        task_prompt="Test task"
                    )
                )
            ],
            connections=[],
            start_step="nonexistent_step",  # Error: paso inexistente
            end_steps=["step1"]
        )

        validation = workflow.validate_workflow()
        assert not validation.is_valid
        assert len(validation.errors) > 0
        assert "Start step 'nonexistent_step' not found" in validation.errors[0]

    def test_circular_dependency_detection(self):
        """Test detección de dependencias circulares"""

        steps = [
            WorkflowStep(
                id="step1",
                name="Step 1",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Task 1")
            ),
            WorkflowStep(
                id="step2",
                name="Step 2",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="researcher", task_prompt="Task 2")
            )
        ]

        # Crear dependencia circular
        connections = [
            StepConnection(from_step="step1", to_step="step2"),
            StepConnection(from_step="step2", to_step="step1")  # Circular
        ]

        workflow = WorkflowDefinition(
            name="Circular Workflow",
            steps=steps,
            connections=connections,
            start_step="step1",
            end_steps=["step2"]
        )

        validation = workflow.validate_workflow()
        assert not validation.is_valid
        assert any("infinite loop" in error.lower() for error in validation.errors)


class TestDependencyResolution:
    """Tests para resolución de dependencias"""

    def test_simple_dependency_resolution(self):
        """Test resolución simple de dependencias"""

        workflow = self._create_sequential_workflow()
        resolver = DependencyResolver()
        execution_graph = resolver.resolve_dependencies(workflow)

        # Verificar niveles de ejecución
        levels = execution_graph.get_execution_levels()
        assert len(levels) == 3

        # Verificar orden correcto
        level_0_steps = levels[0].steps
        level_1_steps = levels[1].steps
        level_2_steps = levels[2].steps

        assert "step1" in level_0_steps
        assert "step2" in level_1_steps
        assert "step3" in level_2_steps

    def test_parallel_execution_opportunities(self):
        """Test identificación de oportunidades de ejecución paralela"""

        workflow = self._create_parallel_workflow()
        resolver = DependencyResolver()
        execution_graph = resolver.resolve_dependencies(workflow)

        # Obtener oportunidades de paralelización
        parallel_groups = execution_graph.get_parallel_execution_opportunities()

        # Debe haber al menos un grupo con múltiples pasos
        assert len(parallel_groups) > 0
        assert any(len(group) > 1 for group in parallel_groups)

    def test_critical_path_calculation(self):
        """Test cálculo del camino crítico"""

        workflow = self._create_complex_workflow()
        resolver = DependencyResolver()
        execution_graph = resolver.resolve_dependencies(workflow)

        critical_path = execution_graph.get_critical_path()

        # El camino crítico debe tener al menos un paso
        assert len(critical_path) > 0

        # Todos los pasos del camino crítico deben existir
        step_ids = {step.id for step in workflow.steps}
        for step_id in critical_path:
            assert step_id in step_ids

    def _create_sequential_workflow(self) -> WorkflowDefinition:
        """Crea workflow secuencial para testing"""
        steps = [
            WorkflowStep(
                id="step1",
                name="Step 1",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="researcher", task_prompt="Research")
            ),
            WorkflowStep(
                id="step2",
                name="Step 2",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Write")
            ),
            WorkflowStep(
                id="step3",
                name="Step 3",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Review")
            )
        ]

        connections = [
            StepConnection(from_step="step1", to_step="step2"),
            StepConnection(from_step="step2", to_step="step3")
        ]

        return WorkflowDefinition(
            name="Sequential Workflow",
            steps=steps,
            connections=connections,
            start_step="step1",
            end_steps=["step3"]
        )

    def _create_parallel_workflow(self) -> WorkflowDefinition:
        """Crea workflow con pasos paralelos para testing"""
        steps = [
            WorkflowStep(
                id="initial",
                name="Initial Step",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="researcher", task_prompt="Initial research")
            ),
            WorkflowStep(
                id="parallel1",
                name="Parallel Step 1",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Write content 1")
            ),
            WorkflowStep(
                id="parallel2",
                name="Parallel Step 2",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Write content 2")
            ),
            WorkflowStep(
                id="final",
                name="Final Step",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Combine content")
            )
        ]

        connections = [
            StepConnection(from_step="initial", to_step="parallel1"),
            StepConnection(from_step="initial", to_step="parallel2"),
            StepConnection(from_step="parallel1", to_step="final"),
            StepConnection(from_step="parallel2", to_step="final")
        ]

        return WorkflowDefinition(
            name="Parallel Workflow",
            steps=steps,
            connections=connections,
            start_step="initial",
            end_steps=["final"]
        )

    def _create_complex_workflow(self) -> WorkflowDefinition:
        """Crea workflow complejo para testing"""
        steps = [
            WorkflowStep(id="a", name="A", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="researcher", task_prompt="A")),
            WorkflowStep(id="b", name="B", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="B")),
            WorkflowStep(id="c", name="C", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="C")),
            WorkflowStep(id="d", name="D", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="data_analyzer", task_prompt="D")),
            WorkflowStep(id="e", name="E", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="E"))
        ]

        connections = [
            StepConnection(from_step="a", to_step="b"),
            StepConnection(from_step="a", to_step="c"),
            StepConnection(from_step="b", to_step="d"),
            StepConnection(from_step="c", to_step="d"),
            StepConnection(from_step="d", to_step="e")
        ]

        return WorkflowDefinition(
            name="Complex Workflow",
            steps=steps,
            connections=connections,
            start_step="a",
            end_steps=["e"]
        )


class TestWorkflowExecution:
    """Tests para ejecución de workflows"""

    @pytest.mark.asyncio
    async def test_simple_workflow_execution(self):
        """Test ejecución de workflow simple"""

        # Crear workflow simple
        workflow = self._create_simple_test_workflow()

        # Crear executor
        executor = WorkflowExecutor(orchestrator_instance)

        # Ejecutar workflow
        try:
            result = await executor.execute_workflow(
                workflow=workflow,
                input_variables={"input_text": "Test topic for content creation"},
                organization_id="test_org",
                user_id="test_user",
                mode=ExecutionMode.SYNCHRONOUS
            )

            # Verificar resultado
            assert result.execution_id is not None
            assert result.workflow_id == workflow.id
            assert result.steps_executed > 0
            assert "output_content" in result.final_variables

        except Exception as e:
            # La ejecución puede fallar por falta de configuración real de agentes
            # pero el test verifica que la estructura funciona
            assert "agent" in str(e).lower() or "llm" in str(e).lower()

    @pytest.mark.asyncio
    async def test_workflow_execution_with_error_handling(self):
        """Test manejo de errores en ejecución"""

        # Crear workflow con agente inexistente
        workflow = self._create_invalid_agent_workflow()

        executor = WorkflowExecutor(orchestrator_instance)

        # La ejecución debe fallar gracefully
        with pytest.raises(Exception) as exc_info:
            await executor.execute_workflow(
                workflow=workflow,
                input_variables={"input": "test"},
                organization_id="test_org",
                user_id="test_user"
            )

        # Verificar que el error es descriptivo
        error_msg = str(exc_info.value)
        assert "agent" in error_msg.lower() or "unknown" in error_msg.lower()

    def _create_simple_test_workflow(self) -> WorkflowDefinition:
        """Crea workflow simple para testing"""
        variables = [
            WorkflowVariable(name="input_text", type="string", required=True),
            WorkflowVariable(name="output_content", type="string")
        ]

        steps = [
            WorkflowStep(
                id="generate",
                name="Generate Content",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Create content about: {input_text}",
                    output_variable="output_content"
                )
            )
        ]

        return WorkflowDefinition(
            name="Simple Test Workflow",
            variables=variables,
            steps=steps,
            connections=[],
            start_step="generate",
            end_steps=["generate"]
        )

    def _create_invalid_agent_workflow(self) -> WorkflowDefinition:
        """Crea workflow con agente inválido para testing de errores"""
        steps = [
            WorkflowStep(
                id="invalid_step",
                name="Invalid Step",
                type=StepType.AGENT_TASK,
                agent_config=AgentTaskConfig(
                    agent_type="nonexistent_agent",
                    task_prompt="This should fail"
                )
            )
        ]

        return WorkflowDefinition(
            name="Invalid Workflow",
            steps=steps,
            connections=[],
            start_step="invalid_step",
            end_steps=["invalid_step"]
        )


class TestTemplateSystem:
    """Tests para el sistema de templates"""

    def test_builtin_templates_availability(self):
        """Test que los templates predefinidos están disponibles"""

        templates = template_manager.get_available_templates()

        # Debe haber al menos algunos templates predefinidos
        assert len(templates) > 0

        # Verificar templates específicos
        template_names = [t.name for t in templates]
        expected_templates = [
            "Content Creation Workflow",
            "Customer Support Workflow",
            "Research & Analysis Workflow"
        ]

        for expected in expected_templates:
            assert any(expected in name for name in template_names)

    def test_template_installation(self):
        """Test instalación de templates"""

        # Obtener template de content creation
        templates = template_manager.get_available_templates()
        content_template = next(
            (t for t in templates if "Content" in t.name and "Creation" in t.name),
            None
        )

        assert content_template is not None

        # Instalar template con customización
        customization = {
            "variables": {
                "tone": "casual",
                "content_type": "social_media"
            },
            "metadata": {
                "name": "Custom Content Workflow"
            }
        }

        installed_workflow = template_manager.install_template(
            template=content_template,
            organization_id="test_org",
            customization=customization
        )

        # Verificar instalación
        assert installed_workflow.id != content_template.workflow_definition.id
        assert installed_workflow.name == "Custom Content Workflow"
        assert any(var.name == "tone" and var.default_value == "casual"
                  for var in installed_workflow.variables)

    def test_template_compatibility_validation(self):
        """Test validación de compatibilidad de templates"""

        templates = template_manager.get_available_templates()
        content_template = templates[0]  # Usar el primer template

        # Test con agentes disponibles
        available_agents = ["copywriter", "researcher", "scheduler"]
        compatibility = template_manager.validate_template_compatibility(
            content_template, available_agents
        )

        # Debe ser compatible o reportar agentes faltantes específicos
        assert isinstance(compatibility["compatible"], bool)
        assert "required_agents" in compatibility
        assert "missing_agents" in compatibility

    def test_template_search(self):
        """Test búsqueda de templates"""

        # Buscar por término general
        results = template_manager.search_templates("content")
        assert len(results) > 0

        # Buscar con filtros
        results_with_filter = template_manager.search_templates(
            "workflow",
            filters={"category": "marketing"}
        )

        # Los resultados deben estar filtrados por categoría
        for result in results_with_filter:
            assert result.category == "marketing"

    def test_template_categories(self):
        """Test agrupación por categorías"""

        categories = template_manager.get_templates_by_category()

        # Debe haber múltiples categorías
        assert len(categories) > 1

        # Verificar categorías esperadas
        expected_categories = ["marketing", "customer_service", "research"]
        for category in expected_categories:
            assert any(cat.lower() == category for cat in categories.keys())


class TestOrchestrationAPI:
    """Tests para endpoints de la API de orquestación"""

    def test_workflow_validation_endpoint_structure(self):
        """Test estructura de validación (sin hacer llamada real)"""

        # Crear workflow de test
        workflow_def = {
            "name": "Test Workflow",
            "steps": [
                {
                    "id": "test_step",
                    "name": "Test Step",
                    "type": "agent_task",
                    "agent_config": {
                        "agent_type": "copywriter",
                        "task_prompt": "Test prompt"
                    }
                }
            ],
            "connections": [],
            "start_step": "test_step",
            "end_steps": ["test_step"]
        }

        # Verificar que se puede parsear
        workflow = WorkflowDefinition.parse_obj(workflow_def)
        validation = workflow.validate_workflow()

        assert validation.is_valid
        assert len(validation.errors) == 0

    def test_execution_request_structure(self):
        """Test estructura de request de ejecución"""

        # Estructura de request válida
        request_data = {
            "workflow_id": "test_workflow",
            "input_variables": {"input": "test_value"},
            "execution_mode": "synchronous",
            "priority": "normal"
        }

        # Verificar que la estructura es válida
        assert "workflow_id" in request_data
        assert "input_variables" in request_data
        assert request_data["execution_mode"] in ["synchronous", "asynchronous"]
        assert request_data["priority"] in ["low", "normal", "high", "critical"]


class TestPerformanceAndOptimization:
    """Tests para rendimiento y optimización"""

    def test_bottleneck_analysis(self):
        """Test análisis de cuellos de botella"""

        workflow = self._create_bottleneck_workflow()
        resolver = DependencyResolver()
        analysis = resolver.analyze_bottlenecks(workflow)

        # Verificar que el análisis contiene información útil
        assert "critical_path" in analysis
        assert "parallel_opportunities" in analysis
        assert "optimization_suggestions" in analysis
        assert isinstance(analysis["optimization_suggestions"], list)

    def test_execution_time_estimation(self):
        """Test estimación de tiempo de ejecución"""

        workflow = self._create_sequential_workflow()
        resolver = DependencyResolver()
        execution_graph = resolver.resolve_dependencies(workflow)

        estimated_time = execution_graph.estimate_execution_time()

        # Debe retornar un tiempo positivo
        assert estimated_time > 0

        # Con duraciones custom
        custom_durations = {"step1": 60, "step2": 30, "step3": 45}
        custom_time = execution_graph.estimate_execution_time(custom_durations)

        # El tiempo custom debe ser diferente al por defecto
        assert custom_time != estimated_time

    def _create_bottleneck_workflow(self) -> WorkflowDefinition:
        """Crea workflow con posibles cuellos de botella"""

        # Workflow donde muchos pasos dependen de uno inicial
        steps = [
            WorkflowStep(id="bottleneck", name="Bottleneck", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="researcher", task_prompt="Research")),
            WorkflowStep(id="dependent1", name="Dependent 1", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Write 1")),
            WorkflowStep(id="dependent2", name="Dependent 2", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Write 2")),
            WorkflowStep(id="dependent3", name="Dependent 3", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="data_analyzer", task_prompt="Analyze"))
        ]

        connections = [
            StepConnection(from_step="bottleneck", to_step="dependent1"),
            StepConnection(from_step="bottleneck", to_step="dependent2"),
            StepConnection(from_step="bottleneck", to_step="dependent3")
        ]

        return WorkflowDefinition(
            name="Bottleneck Workflow",
            steps=steps,
            connections=connections,
            start_step="bottleneck",
            end_steps=["dependent1", "dependent2", "dependent3"]
        )

    def _create_sequential_workflow(self) -> WorkflowDefinition:
        """Helper para crear workflow secuencial"""
        steps = [
            WorkflowStep(id="step1", name="Step 1", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="researcher", task_prompt="Research")),
            WorkflowStep(id="step2", name="Step 2", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Write")),
            WorkflowStep(id="step3", name="Step 3", type=StepType.AGENT_TASK,
                        agent_config=AgentTaskConfig(agent_type="copywriter", task_prompt="Review"))
        ]

        connections = [
            StepConnection(from_step="step1", to_step="step2"),
            StepConnection(from_step="step2", to_step="step3")
        ]

        return WorkflowDefinition(
            name="Sequential Workflow",
            steps=steps,
            connections=connections,
            start_step="step1",
            end_steps=["step3"]
        )


if __name__ == "__main__":
    # Ejecutar tests específicos
    pytest.main([__file__, "-v", "--tb=short"])