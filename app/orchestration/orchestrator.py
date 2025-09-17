"""
Agent Orchestrator

Sistema central de orquestación que coordina múltiples agentes especializados
para ejecutar workflows complejos y multi-paso.
"""

from typing import Dict, List, Any, Optional, Set, Callable
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import uuid
import json

from .workflow_schema import (
    WorkflowDefinition, WorkflowStep, WorkflowExecution, WorkflowStatus,
    StepType, StepStatus, WorkflowValidationResult
)
from .dependency_resolver import DependencyResolver, ExecutionGraph
from ..agents import (
    BaseAgent, AgentContext, CopywriterAgent, ResearcherAgent,
    SchedulerAgent, EmailResponderAgent, DataAnalyzerAgent
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationContext:
    """Contexto de orquestación que se pasa entre pasos"""
    execution_id: str
    workflow_id: str
    organization_id: str
    user_id: str
    variables: Dict[str, Any]
    step_results: Dict[str, Any]
    metadata: Dict[str, Any]
    started_at: datetime

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Obtiene una variable del contexto"""
        return self.variables.get(name, default)

    def set_variable(self, name: str, value: Any):
        """Establece una variable en el contexto"""
        self.variables[name] = value

    def get_step_result(self, step_id: str) -> Any:
        """Obtiene el resultado de un paso específico"""
        return self.step_results.get(step_id)

    def set_step_result(self, step_id: str, result: Any):
        """Establece el resultado de un paso"""
        self.step_results[step_id] = result


@dataclass
class StepExecutionResult:
    """Resultado de ejecución de un paso"""
    step_id: str
    status: StepStatus
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AgentOrchestrator:
    """
    Orquestador principal que coordina la ejecución de workflows
    utilizando múltiples agentes especializados.
    """

    def __init__(self):
        self.agents = self._initialize_agents()
        self.dependency_resolver = DependencyResolver()
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.step_handlers: Dict[StepType, Callable] = self._initialize_step_handlers()

        # Hooks para extensibilidad
        self.pre_execution_hooks: List[Callable] = []
        self.post_execution_hooks: List[Callable] = []
        self.step_hooks: Dict[str, List[Callable]] = {}

    def _initialize_agents(self) -> Dict[str, BaseAgent]:
        """Inicializa todos los agentes especializados"""
        return {
            "copywriter": CopywriterAgent(),
            "researcher": ResearcherAgent(),
            "scheduler": SchedulerAgent(),
            "email_responder": EmailResponderAgent(),
            "data_analyzer": DataAnalyzerAgent()
        }

    def _initialize_step_handlers(self) -> Dict[StepType, Callable]:
        """Inicializa los manejadores para cada tipo de paso"""
        return {
            StepType.AGENT_TASK: self._execute_agent_task,
            StepType.CONDITION: self._execute_condition,
            StepType.PARALLEL: self._execute_parallel,
            StepType.LOOP: self._execute_loop,
            StepType.DELAY: self._execute_delay,
            StepType.WEBHOOK: self._execute_webhook,
            StepType.HUMAN_APPROVAL: self._execute_human_approval,
            StepType.DATA_TRANSFORM: self._execute_data_transform
        }

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        input_variables: Dict[str, Any],
        organization_id: str,
        user_id: str,
        execution_metadata: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecution:
        """
        Ejecuta un workflow completo de forma asíncrona.

        Args:
            workflow: Definición del workflow a ejecutar
            input_variables: Variables de entrada
            organization_id: ID de la organización
            user_id: ID del usuario que ejecuta
            execution_metadata: Metadata adicional

        Returns:
            WorkflowExecution: Registro completo de la ejecución
        """
        # Validar workflow antes de ejecutar
        validation = workflow.validate_workflow()
        if not validation.is_valid:
            raise ValueError(f"Invalid workflow: {'; '.join(validation.errors)}")

        # Crear contexto de ejecución
        execution_id = str(uuid.uuid4())
        context = OrchestrationContext(
            execution_id=execution_id,
            workflow_id=workflow.id,
            organization_id=organization_id,
            user_id=user_id,
            variables=input_variables.copy(),
            step_results={},
            metadata=execution_metadata or {},
            started_at=datetime.now()
        )

        # Crear registro de ejecución
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            status=WorkflowStatus.PENDING,
            input_variables=input_variables,
            triggered_by=user_id,
            organization_id=organization_id,
            started_at=datetime.now()
        )

        self.active_executions[execution_id] = execution

        try:
            # Ejecutar hooks pre-ejecución
            await self._run_pre_execution_hooks(workflow, context)

            # Resolver orden de ejecución
            execution_graph = self.dependency_resolver.resolve_dependencies(workflow)

            # Iniciar ejecución
            execution.status = WorkflowStatus.ACTIVE
            logger.info(f"Starting workflow execution {execution_id}")

            # Ejecutar pasos según dependencias
            await self._execute_workflow_steps(workflow, execution_graph, context)

            # Finalizar ejecución
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now()
            execution.duration_seconds = (execution.completed_at - execution.started_at).total_seconds()
            execution.runtime_variables = context.variables
            execution.step_results = context.step_results

            logger.info(f"Workflow execution {execution_id} completed successfully")

            # Ejecutar hooks post-ejecución
            await self._run_post_execution_hooks(workflow, context, execution)

        except Exception as e:
            # Manejar errores de ejecución
            execution.status = WorkflowStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
            execution.duration_seconds = (execution.completed_at - execution.started_at).total_seconds()

            logger.error(f"Workflow execution {execution_id} failed: {str(e)}")
            raise

        finally:
            # Limpiar ejecución activa
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]

        return execution

    async def _execute_workflow_steps(
        self,
        workflow: WorkflowDefinition,
        execution_graph: ExecutionGraph,
        context: OrchestrationContext
    ):
        """Ejecuta los pasos del workflow según el grafo de dependencias"""

        completed_steps: Set[str] = set()
        failed_steps: Set[str] = set()

        # Encontrar pasos que pueden ejecutarse inicialmente
        ready_steps = execution_graph.get_ready_steps(completed_steps)

        while ready_steps and len(completed_steps) < len(workflow.steps):
            # Ejecutar pasos listos en paralelo
            step_tasks = []
            current_batch = list(ready_steps)

            for step_id in current_batch:
                step = next(s for s in workflow.steps if s.id == step_id)
                task = self._execute_single_step(step, context)
                step_tasks.append((step_id, task))

            # Esperar a que terminen todos los pasos de esta iteración
            results = await asyncio.gather(
                *[task for _, task in step_tasks],
                return_exceptions=True
            )

            # Procesar resultados
            for i, (step_id, _) in enumerate(step_tasks):
                result = results[i]

                if isinstance(result, Exception):
                    failed_steps.add(step_id)
                    logger.error(f"Step {step_id} failed: {str(result)}")

                    # Decidir si continuar o fallar todo
                    step = next(s for s in workflow.steps if s.id == step_id)
                    if not self._should_continue_on_step_failure(step, result):
                        raise result
                else:
                    completed_steps.add(step_id)
                    context.set_step_result(step_id, result.result)
                    logger.info(f"Step {step_id} completed successfully")

            # Encontrar siguientes pasos listos
            ready_steps = execution_graph.get_ready_steps(completed_steps) - completed_steps - failed_steps

            # Verificar condiciones de parada
            if not ready_steps and len(completed_steps) + len(failed_steps) < len(workflow.steps):
                # Hay pasos que no se pueden ejecutar - posible deadlock
                remaining_steps = {s.id for s in workflow.steps} - completed_steps - failed_steps
                raise RuntimeError(f"Workflow deadlock: cannot execute remaining steps {remaining_steps}")

    async def _execute_single_step(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> StepExecutionResult:
        """Ejecuta un solo paso del workflow"""

        start_time = datetime.now()

        try:
            # Ejecutar hooks de paso
            await self._run_step_hooks(step.id, context, "before")

            # Obtener handler para el tipo de paso
            handler = self.step_handlers.get(step.type)
            if not handler:
                raise ValueError(f"No handler for step type: {step.type}")

            # Ejecutar el paso
            logger.info(f"Executing step {step.id} ({step.type.value})")
            result = await handler(step, context)

            execution_time = (datetime.now() - start_time).total_seconds()

            step_result = StepExecutionResult(
                step_id=step.id,
                status=StepStatus.COMPLETED,
                result=result,
                execution_time=execution_time,
                metadata={"step_name": step.name, "step_type": step.type.value}
            )

            # Ejecutar hooks de paso
            await self._run_step_hooks(step.id, context, "after", step_result)

            return step_result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            step_result = StepExecutionResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                result=None,
                error=str(e),
                execution_time=execution_time,
                metadata={"step_name": step.name, "step_type": step.type.value}
            )

            logger.error(f"Step {step.id} failed after {execution_time:.2f}s: {str(e)}")
            raise e

    async def _execute_agent_task(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta una tarea de agente"""

        if not step.agent_config:
            raise ValueError("Agent task step requires agent_config")

        config = step.agent_config

        # Obtener agente
        agent = self.agents.get(config.agent_type)
        if not agent:
            raise ValueError(f"Unknown agent type: {config.agent_type}")

        # Procesar prompt con variables del contexto
        processed_prompt = self._process_template_string(config.task_prompt, context.variables)

        # Crear contexto del agente
        agent_context = AgentContext(
            organization_id=context.organization_id,
            user_id=context.user_id,
            session_id=f"workflow_{context.execution_id}_{step.id}",
            metadata={
                "workflow_execution": context.execution_id,
                "step_id": step.id,
                **context.metadata
            }
        )

        # Ejecutar agente con timeout
        try:
            result = await asyncio.wait_for(
                agent.execute(processed_prompt, agent_context, **config.parameters),
                timeout=config.timeout
            )

            # Guardar resultado en variable si se especifica
            if config.output_variable:
                context.set_variable(config.output_variable, result.response)

            return {
                "response": result.response,
                "confidence": result.confidence,
                "metadata": result.metadata,
                "agent_type": config.agent_type
            }

        except asyncio.TimeoutError:
            raise TimeoutError(f"Agent task timed out after {config.timeout} seconds")

    async def _execute_condition(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta una condición lógica"""

        if not step.condition_config:
            raise ValueError("Condition step requires condition_config")

        config = step.condition_config

        # Evaluar todas las condiciones
        results = []
        for condition in config.conditions:
            variable_value = context.get_variable(condition.variable)
            condition_result = self._evaluate_condition(variable_value, condition)
            results.append(condition_result)

        # Aplicar lógica AND/OR (simplificado - asume AND por defecto)
        final_result = all(results)

        # Determinar siguiente paso
        next_step = config.true_path if final_result else config.false_path

        return {
            "condition_result": final_result,
            "next_step": next_step,
            "individual_results": results
        }

    async def _execute_parallel(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta pasos en paralelo"""

        if not step.parallel_config:
            raise ValueError("Parallel step requires parallel_config")

        config = step.parallel_config

        # Esta implementación es simplificada
        # En la práctica, los pasos paralelos se manejarían en el nivel superior

        return {
            "parallel_steps": config.steps,
            "wait_for_all": config.wait_for_all,
            "continue_on_error": config.continue_on_error
        }

    async def _execute_loop(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta un bucle"""

        if not step.loop_config:
            raise ValueError("Loop step requires loop_config")

        config = step.loop_config

        # Obtener datos para iterar
        data_source = context.get_variable(config.data_source)
        if not isinstance(data_source, (list, tuple)):
            raise ValueError(f"Data source {config.data_source} must be a list or tuple")

        results = []

        for i, item in enumerate(data_source):
            if i >= config.max_iterations:
                break

            # Establecer variable de iteración
            context.set_variable(config.iteration_variable, item)
            context.set_variable(f"{config.iteration_variable}_index", i)

            # Ejecutar pasos del bucle (simplificado)
            iteration_result = {
                "iteration": i,
                "item": item,
                "steps_executed": config.steps
            }
            results.append(iteration_result)

        return {
            "iterations": len(results),
            "results": results
        }

    async def _execute_delay(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta una pausa"""

        # Obtener duración del delay desde metadata o usar default
        delay_seconds = step.metadata.get("delay_seconds", 60)

        await asyncio.sleep(delay_seconds)

        return {"delayed_seconds": delay_seconds}

    async def _execute_webhook(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta una llamada webhook"""

        if not step.webhook_config:
            raise ValueError("Webhook step requires webhook_config")

        config = step.webhook_config

        # En una implementación real, haríamos la llamada HTTP
        # Por ahora, simulamos la respuesta

        processed_url = self._process_template_string(config.url, context.variables)

        # Simular respuesta webhook
        response = {
            "status_code": 200,
            "response": {
                "message": "Webhook executed successfully",
                "url": processed_url,
                "method": config.method
            }
        }

        # Guardar respuesta en variable si se especifica
        if config.output_variable:
            context.set_variable(config.output_variable, response["response"])

        return response

    async def _execute_human_approval(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta un paso de aprobación humana"""

        if not step.approval_config:
            raise ValueError("Human approval step requires approval_config")

        config = step.approval_config

        # En una implementación real, esto crearía una tarea de aprobación
        # y esperaría la respuesta del usuario

        processed_message = self._process_template_string(config.message, context.variables)

        # Por ahora, simulamos auto-aprobación
        approval_result = {
            "approved": config.auto_approve,
            "message": processed_message,
            "approvers": config.approvers,
            "approved_by": "system" if config.auto_approve else None,
            "approved_at": datetime.now().isoformat() if config.auto_approve else None
        }

        return approval_result

    async def _execute_data_transform(
        self,
        step: WorkflowStep,
        context: OrchestrationContext
    ) -> Any:
        """Ejecuta una transformación de datos"""

        if not step.transform_config:
            raise ValueError("Data transform step requires transform_config")

        config = step.transform_config

        # Obtener datos de entrada
        input_data = context.get_variable(config.input_variable)

        # Aplicar transformación (implementación básica)
        if config.transformation == "json_parse":
            if isinstance(input_data, str):
                transformed_data = json.loads(input_data)
            else:
                transformed_data = input_data
        elif config.transformation == "json_stringify":
            transformed_data = json.dumps(input_data)
        elif config.transformation == "uppercase":
            transformed_data = str(input_data).upper()
        elif config.transformation == "lowercase":
            transformed_data = str(input_data).lower()
        else:
            raise ValueError(f"Unknown transformation: {config.transformation}")

        # Guardar resultado
        context.set_variable(config.output_variable, transformed_data)

        return {
            "transformation": config.transformation,
            "input_variable": config.input_variable,
            "output_variable": config.output_variable,
            "transformed_data": transformed_data
        }

    def _evaluate_condition(self, value: Any, condition) -> bool:
        """Evalúa una condición individual"""
        from .workflow_schema import ConditionOperator

        op = condition.operator
        expected = condition.value

        if op == ConditionOperator.EQUALS:
            return value == expected
        elif op == ConditionOperator.NOT_EQUALS:
            return value != expected
        elif op == ConditionOperator.GREATER_THAN:
            return float(value) > float(expected)
        elif op == ConditionOperator.LESS_THAN:
            return float(value) < float(expected)
        elif op == ConditionOperator.CONTAINS:
            return str(expected) in str(value)
        elif op == ConditionOperator.NOT_CONTAINS:
            return str(expected) not in str(value)
        elif op == ConditionOperator.IS_EMPTY:
            return not value or len(str(value).strip()) == 0
        elif op == ConditionOperator.IS_NOT_EMPTY:
            return value and len(str(value).strip()) > 0
        else:
            raise ValueError(f"Unknown condition operator: {op}")

    def _process_template_string(self, template: str, variables: Dict[str, Any]) -> str:
        """Procesa un string template reemplazando variables"""
        result = template
        for name, value in variables.items():
            placeholder = f"{{{name}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def _should_continue_on_step_failure(self, step: WorkflowStep, error: Exception) -> bool:
        """Determina si continuar cuando falla un paso"""
        # Por ahora, fallar siempre que un paso falle
        # En el futuro, esto podría ser configurable por paso
        return False

    async def _run_pre_execution_hooks(self, workflow: WorkflowDefinition, context: OrchestrationContext):
        """Ejecuta hooks antes de la ejecución"""
        for hook in self.pre_execution_hooks:
            try:
                await hook(workflow, context)
            except Exception as e:
                logger.warning(f"Pre-execution hook failed: {str(e)}")

    async def _run_post_execution_hooks(
        self,
        workflow: WorkflowDefinition,
        context: OrchestrationContext,
        execution: WorkflowExecution
    ):
        """Ejecuta hooks después de la ejecución"""
        for hook in self.post_execution_hooks:
            try:
                await hook(workflow, context, execution)
            except Exception as e:
                logger.warning(f"Post-execution hook failed: {str(e)}")

    async def _run_step_hooks(
        self,
        step_id: str,
        context: OrchestrationContext,
        timing: str,
        result: Optional[StepExecutionResult] = None
    ):
        """Ejecuta hooks de paso"""
        hooks = self.step_hooks.get(step_id, [])
        for hook in hooks:
            try:
                await hook(step_id, context, timing, result)
            except Exception as e:
                logger.warning(f"Step hook failed for {step_id}: {str(e)}")

    # Métodos para gestión de hooks
    def add_pre_execution_hook(self, hook: Callable):
        """Añade un hook que se ejecuta antes del workflow"""
        self.pre_execution_hooks.append(hook)

    def add_post_execution_hook(self, hook: Callable):
        """Añade un hook que se ejecuta después del workflow"""
        self.post_execution_hooks.append(hook)

    def add_step_hook(self, step_id: str, hook: Callable):
        """Añade un hook para un paso específico"""
        if step_id not in self.step_hooks:
            self.step_hooks[step_id] = []
        self.step_hooks[step_id].append(hook)

    # Métodos de consulta
    def get_active_executions(self) -> List[WorkflowExecution]:
        """Obtiene todas las ejecuciones activas"""
        return list(self.active_executions.values())

    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Obtiene el estado de una ejecución específica"""
        return self.active_executions.get(execution_id)

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancela una ejecución activa"""
        if execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            execution.status = WorkflowStatus.CANCELLED
            execution.completed_at = datetime.now()
            execution.duration_seconds = (execution.completed_at - execution.started_at).total_seconds()

            # En una implementación completa, esto también detendría la ejecución
            logger.info(f"Cancelled workflow execution {execution_id}")
            return True

        return False


# Instancia global del orquestador
orchestrator_instance = AgentOrchestrator()