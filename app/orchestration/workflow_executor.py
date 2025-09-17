"""
Workflow Executor

Motor de ejecución optimizado para workflows que maneja la ejecución
eficiente, monitoreo en tiempo real y recuperación de errores.
"""

from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import uuid
import json
from enum import Enum

from .workflow_schema import (
    WorkflowDefinition, WorkflowExecution, WorkflowStatus,
    StepStatus, StepType
)
from .orchestrator import AgentOrchestrator, OrchestrationContext, StepExecutionResult
from .dependency_resolver import DependencyResolver, ExecutionGraph

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Modos de ejecución de workflows"""
    SYNCHRONOUS = "synchronous"      # Ejecución síncrona - espera a completar
    ASYNCHRONOUS = "asynchronous"    # Ejecución asíncrona - retorna inmediatamente
    STREAMING = "streaming"          # Ejecución con streaming de resultados
    DEBUG = "debug"                  # Ejecución paso a paso para debug


class ExecutionPriority(Enum):
    """Prioridades de ejecución"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ExecutionContext:
    """Contexto extendido para ejecución de workflows"""
    execution_id: str
    workflow_id: str
    organization_id: str
    user_id: str
    mode: ExecutionMode
    priority: ExecutionPriority

    # Variables y estado
    input_variables: Dict[str, Any]
    runtime_variables: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    step_states: Dict[str, StepStatus] = field(default_factory=dict)

    # Configuración de ejecución
    timeout_seconds: int = 3600
    max_retries: int = 3
    retry_delays: List[int] = field(default_factory=lambda: [5, 15, 30])

    # Callbacks y hooks
    progress_callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    completion_callback: Optional[Callable] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None

    # Control de ejecución
    should_stop: bool = False
    paused: bool = False
    pause_at_step: Optional[str] = None


@dataclass
class ExecutionResult:
    """Resultado completo de ejecución de workflow"""
    execution_id: str
    workflow_id: str
    status: WorkflowStatus

    # Resultados
    final_variables: Dict[str, Any]
    step_results: Dict[str, Any]
    output_data: Any = None

    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Estadísticas
    steps_executed: int = 0
    steps_skipped: int = 0
    steps_failed: int = 0
    retries_performed: int = 0

    # Errores y logs
    error_message: Optional[str] = None
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepExecutionEvent:
    """Evento de ejecución de paso para streaming"""
    execution_id: str
    step_id: str
    step_name: str
    event_type: str  # started, progress, completed, failed, skipped
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)


class WorkflowExecutor:
    """
    Executor optimizado para workflows que proporciona:
    - Ejecución eficiente con paralelización
    - Monitoreo en tiempo real
    - Recuperación de errores
    - Diferentes modos de ejecución
    """

    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
        self.dependency_resolver = DependencyResolver()

        # Estado de ejecuciones
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.execution_history: Dict[str, ExecutionResult] = {}

        # Configuración de recursos
        self.max_concurrent_executions = 10
        self.max_concurrent_steps = 5

        # Locks para concurrencia
        self.execution_lock = asyncio.Lock()
        self.resource_semaphore = asyncio.Semaphore(self.max_concurrent_steps)

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        input_variables: Dict[str, Any],
        organization_id: str,
        user_id: str,
        mode: ExecutionMode = ExecutionMode.SYNCHRONOUS,
        priority: ExecutionPriority = ExecutionPriority.NORMAL,
        execution_config: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Ejecuta un workflow con configuración avanzada.

        Args:
            workflow: Definición del workflow
            input_variables: Variables de entrada
            organization_id: ID de organización
            user_id: ID de usuario
            mode: Modo de ejecución
            priority: Prioridad de ejecución
            execution_config: Configuración adicional

        Returns:
            ExecutionResult: Resultado de la ejecución
        """
        # Crear contexto de ejecución
        execution_id = str(uuid.uuid4())
        context = ExecutionContext(
            execution_id=execution_id,
            workflow_id=workflow.id,
            organization_id=organization_id,
            user_id=user_id,
            mode=mode,
            priority=priority,
            input_variables=input_variables.copy(),
            started_at=datetime.now()
        )

        # Aplicar configuración adicional
        if execution_config:
            context.timeout_seconds = execution_config.get("timeout_seconds", context.timeout_seconds)
            context.max_retries = execution_config.get("max_retries", context.max_retries)
            context.metadata.update(execution_config.get("metadata", {}))
            context.tags.extend(execution_config.get("tags", []))

        # Registrar ejecución
        async with self.execution_lock:
            if len(self.active_executions) >= self.max_concurrent_executions:
                raise RuntimeError("Maximum concurrent executions reached")

            self.active_executions[execution_id] = context

        try:
            # Ejecutar según el modo
            if mode == ExecutionMode.SYNCHRONOUS:
                result = await self._execute_synchronous(workflow, context)
            elif mode == ExecutionMode.ASYNCHRONOUS:
                # Iniciar en background y retornar resultado parcial
                asyncio.create_task(self._execute_asynchronous(workflow, context))
                result = self._create_pending_result(context)
            elif mode == ExecutionMode.DEBUG:
                result = await self._execute_debug(workflow, context)
            else:
                raise ValueError(f"Unsupported execution mode: {mode}")

            return result

        except Exception as e:
            logger.error(f"Workflow execution {execution_id} failed: {str(e)}")
            raise
        finally:
            # Limpiar ejecución activa
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]

    async def execute_workflow_streaming(
        self,
        workflow: WorkflowDefinition,
        input_variables: Dict[str, Any],
        organization_id: str,
        user_id: str,
        execution_config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StepExecutionEvent, None]:
        """
        Ejecuta un workflow con streaming de eventos en tiempo real.

        Yields:
            StepExecutionEvent: Eventos de progreso de ejecución
        """
        execution_id = str(uuid.uuid4())
        context = ExecutionContext(
            execution_id=execution_id,
            workflow_id=workflow.id,
            organization_id=organization_id,
            user_id=user_id,
            mode=ExecutionMode.STREAMING,
            priority=ExecutionPriority.NORMAL,
            input_variables=input_variables.copy(),
            started_at=datetime.now()
        )

        if execution_config:
            context.timeout_seconds = execution_config.get("timeout_seconds", context.timeout_seconds)
            context.metadata.update(execution_config.get("metadata", {}))

        async with self.execution_lock:
            self.active_executions[execution_id] = context

        try:
            async for event in self._execute_streaming(workflow, context):
                yield event

        finally:
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]

    async def _execute_synchronous(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext
    ) -> ExecutionResult:
        """Ejecuta workflow de forma síncrona"""

        start_time = datetime.now()

        try:
            # Validar workflow
            validation = workflow.validate_workflow()
            if not validation.is_valid:
                raise ValueError(f"Invalid workflow: {'; '.join(validation.errors)}")

            # Resolver dependencias
            execution_graph = self.dependency_resolver.resolve_dependencies(workflow)

            # Ejecutar pasos
            await self._execute_workflow_steps(workflow, execution_graph, context)

            # Crear resultado exitoso
            end_time = datetime.now()
            result = ExecutionResult(
                execution_id=context.execution_id,
                workflow_id=workflow.id,
                status=WorkflowStatus.COMPLETED,
                final_variables=context.runtime_variables,
                step_results=context.step_results,
                started_at=start_time,
                completed_at=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                steps_executed=len([s for s in context.step_states.values() if s == StepStatus.COMPLETED]),
                steps_failed=len([s for s in context.step_states.values() if s == StepStatus.FAILED]),
                steps_skipped=len([s for s in context.step_states.values() if s == StepStatus.SKIPPED])
            )

            # Guardar en historial
            self.execution_history[context.execution_id] = result

            return result

        except Exception as e:
            # Crear resultado de error
            end_time = datetime.now()
            result = ExecutionResult(
                execution_id=context.execution_id,
                workflow_id=workflow.id,
                status=WorkflowStatus.FAILED,
                final_variables=context.runtime_variables,
                step_results=context.step_results,
                started_at=start_time,
                completed_at=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                error_message=str(e),
                steps_executed=len([s for s in context.step_states.values() if s == StepStatus.COMPLETED]),
                steps_failed=len([s for s in context.step_states.values() if s == StepStatus.FAILED])
            )

            self.execution_history[context.execution_id] = result
            raise

    async def _execute_asynchronous(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext
    ):
        """Ejecuta workflow de forma asíncrona en background"""
        try:
            result = await self._execute_synchronous(workflow, context)

            # Llamar callback de completado si existe
            if context.completion_callback:
                await context.completion_callback(result)

        except Exception as e:
            # Llamar callback de error si existe
            if context.error_callback:
                await context.error_callback(context.execution_id, str(e))

    async def _execute_debug(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext
    ) -> ExecutionResult:
        """Ejecuta workflow en modo debug (paso a paso)"""

        # En modo debug, pausamos después de cada paso
        context.pause_at_step = workflow.start_step

        # Por ahora, ejecutamos normalmente pero con logging extra
        logger.info(f"Starting debug execution for workflow {workflow.id}")

        result = await self._execute_synchronous(workflow, context)
        result.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": "debug_execution_completed",
            "details": "Workflow executed in debug mode"
        })

        return result

    async def _execute_streaming(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext
    ) -> AsyncGenerator[StepExecutionEvent, None]:
        """Ejecuta workflow con streaming de eventos"""

        # Evento de inicio
        yield StepExecutionEvent(
            execution_id=context.execution_id,
            step_id="workflow",
            step_name=workflow.name,
            event_type="started",
            timestamp=datetime.now(),
            data={"total_steps": len(workflow.steps)}
        )

        try:
            # Validar y resolver dependencias
            validation = workflow.validate_workflow()
            if not validation.is_valid:
                yield StepExecutionEvent(
                    execution_id=context.execution_id,
                    step_id="workflow",
                    step_name=workflow.name,
                    event_type="failed",
                    timestamp=datetime.now(),
                    data={"error": f"Invalid workflow: {'; '.join(validation.errors)}"}
                )
                return

            execution_graph = self.dependency_resolver.resolve_dependencies(workflow)

            # Ejecutar pasos con eventos
            async for event in self._execute_steps_streaming(workflow, execution_graph, context):
                yield event

            # Evento de completado
            yield StepExecutionEvent(
                execution_id=context.execution_id,
                step_id="workflow",
                step_name=workflow.name,
                event_type="completed",
                timestamp=datetime.now(),
                data={
                    "final_variables": context.runtime_variables,
                    "steps_executed": len([s for s in context.step_states.values() if s == StepStatus.COMPLETED])
                }
            )

        except Exception as e:
            yield StepExecutionEvent(
                execution_id=context.execution_id,
                step_id="workflow",
                step_name=workflow.name,
                event_type="failed",
                timestamp=datetime.now(),
                data={"error": str(e)}
            )

    async def _execute_workflow_steps(
        self,
        workflow: WorkflowDefinition,
        execution_graph: ExecutionGraph,
        context: ExecutionContext
    ):
        """Ejecuta los pasos del workflow"""

        completed_steps = set()
        failed_steps = set()

        # Obtener niveles de ejecución
        execution_levels = execution_graph.get_execution_levels()

        for level in execution_levels:
            if context.should_stop:
                break

            # Ejecutar pasos del nivel actual en paralelo
            level_tasks = []

            for step_id in level.steps:
                if step_id in completed_steps or step_id in failed_steps:
                    continue

                step = next(s for s in workflow.steps if s.id == step_id)
                context.step_states[step_id] = StepStatus.PENDING

                # Crear tarea para el paso
                task = self._execute_step_with_retry(step, context)
                level_tasks.append((step_id, task))

            if not level_tasks:
                continue

            # Ejecutar con semáforo para limitar concurrencia
            async def execute_with_semaphore(step_id, task):
                async with self.resource_semaphore:
                    return await task

            # Ejecutar todas las tareas del nivel
            level_results = await asyncio.gather(
                *[execute_with_semaphore(step_id, task) for step_id, task in level_tasks],
                return_exceptions=True
            )

            # Procesar resultados del nivel
            for i, (step_id, _) in enumerate(level_tasks):
                result = level_results[i]

                if isinstance(result, Exception):
                    failed_steps.add(step_id)
                    context.step_states[step_id] = StepStatus.FAILED
                    logger.error(f"Step {step_id} failed: {str(result)}")

                    # Decidir si continuar
                    if not self._should_continue_on_failure(step_id, workflow):
                        raise result
                else:
                    completed_steps.add(step_id)
                    context.step_states[step_id] = StepStatus.COMPLETED
                    context.step_results[step_id] = result

                    # Actualizar variables si el paso genera output
                    step = next(s for s in workflow.steps if s.id == step_id)
                    if (step.agent_config and step.agent_config.output_variable and
                        isinstance(result, dict) and "response" in result):
                        context.runtime_variables[step.agent_config.output_variable] = result["response"]

    async def _execute_steps_streaming(
        self,
        workflow: WorkflowDefinition,
        execution_graph: ExecutionGraph,
        context: ExecutionContext
    ) -> AsyncGenerator[StepExecutionEvent, None]:
        """Ejecuta pasos con streaming de eventos"""

        completed_steps = set()
        execution_levels = execution_graph.get_execution_levels()

        for level in execution_levels:
            for step_id in level.steps:
                if step_id in completed_steps:
                    continue

                step = next(s for s in workflow.steps if s.id == step_id)

                # Evento de inicio de paso
                yield StepExecutionEvent(
                    execution_id=context.execution_id,
                    step_id=step_id,
                    step_name=step.name,
                    event_type="started",
                    timestamp=datetime.now(),
                    data={"step_type": step.type.value}
                )

                try:
                    result = await self._execute_step_with_retry(step, context)
                    completed_steps.add(step_id)
                    context.step_results[step_id] = result

                    # Evento de completado
                    yield StepExecutionEvent(
                        execution_id=context.execution_id,
                        step_id=step_id,
                        step_name=step.name,
                        event_type="completed",
                        timestamp=datetime.now(),
                        data={"result": result}
                    )

                except Exception as e:
                    # Evento de fallo
                    yield StepExecutionEvent(
                        execution_id=context.execution_id,
                        step_id=step_id,
                        step_name=step.name,
                        event_type="failed",
                        timestamp=datetime.now(),
                        data={"error": str(e)}
                    )

    async def _execute_step_with_retry(
        self,
        step: Any,
        context: ExecutionContext
    ) -> Any:
        """Ejecuta un paso con lógica de reintentos"""

        last_exception = None

        for attempt in range(context.max_retries + 1):
            try:
                # Crear contexto de orquestación
                orch_context = OrchestrationContext(
                    execution_id=context.execution_id,
                    workflow_id=context.workflow_id,
                    organization_id=context.organization_id,
                    user_id=context.user_id,
                    variables=context.runtime_variables,
                    step_results=context.step_results,
                    metadata=context.metadata,
                    started_at=context.started_at
                )

                # Ejecutar paso usando el orquestador
                result = await self.orchestrator._execute_single_step(step, orch_context)

                # Actualizar contexto con cambios
                context.runtime_variables.update(orch_context.variables)
                context.step_results.update(orch_context.step_results)

                return result.result

            except Exception as e:
                last_exception = e

                if attempt < context.max_retries:
                    # Esperar antes del siguiente intento
                    delay = context.retry_delays[min(attempt, len(context.retry_delays) - 1)]
                    logger.warning(f"Step {step.id} failed (attempt {attempt + 1}), retrying in {delay}s: {str(e)}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Step {step.id} failed after {context.max_retries + 1} attempts: {str(e)}")

        raise last_exception

    def _should_continue_on_failure(self, step_id: str, workflow: WorkflowDefinition) -> bool:
        """Determina si continuar cuando falla un paso"""
        # Por ahora, siempre fallar
        # En el futuro, esto podría ser configurable por paso
        return False

    def _create_pending_result(self, context: ExecutionContext) -> ExecutionResult:
        """Crea un resultado pendiente para ejecución asíncrona"""
        return ExecutionResult(
            execution_id=context.execution_id,
            workflow_id=context.workflow_id,
            status=WorkflowStatus.ACTIVE,
            final_variables={},
            step_results={},
            started_at=context.started_at or datetime.now(),
            steps_executed=0
        )

    # Métodos de gestión y consulta

    async def pause_execution(self, execution_id: str) -> bool:
        """Pausa una ejecución activa"""
        if execution_id in self.active_executions:
            self.active_executions[execution_id].paused = True
            logger.info(f"Execution {execution_id} paused")
            return True
        return False

    async def resume_execution(self, execution_id: str) -> bool:
        """Reanuda una ejecución pausada"""
        if execution_id in self.active_executions:
            self.active_executions[execution_id].paused = False
            logger.info(f"Execution {execution_id} resumed")
            return True
        return False

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancela una ejecución activa"""
        if execution_id in self.active_executions:
            self.active_executions[execution_id].should_stop = True
            logger.info(f"Execution {execution_id} cancelled")
            return True
        return False

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el estado de una ejecución"""
        if execution_id in self.active_executions:
            context = self.active_executions[execution_id]
            return {
                "execution_id": execution_id,
                "status": "active",
                "started_at": context.started_at.isoformat() if context.started_at else None,
                "step_states": {k: v.value for k, v in context.step_states.items()},
                "current_variables": context.runtime_variables,
                "paused": context.paused
            }

        if execution_id in self.execution_history:
            result = self.execution_history[execution_id]
            return {
                "execution_id": execution_id,
                "status": result.status.value,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "duration_seconds": result.duration_seconds,
                "steps_executed": result.steps_executed,
                "error_message": result.error_message
            }

        return None

    def get_active_executions(self) -> List[Dict[str, Any]]:
        """Obtiene todas las ejecuciones activas"""
        return [
            {
                "execution_id": execution_id,
                "workflow_id": context.workflow_id,
                "started_at": context.started_at.isoformat() if context.started_at else None,
                "mode": context.mode.value,
                "priority": context.priority.value,
                "step_count": len(context.step_states),
                "completed_steps": len([s for s in context.step_states.values() if s == StepStatus.COMPLETED])
            }
            for execution_id, context in self.active_executions.items()
        ]

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas del executor"""
        active_count = len(self.active_executions)
        history_count = len(self.execution_history)

        successful_executions = len([r for r in self.execution_history.values()
                                   if r.status == WorkflowStatus.COMPLETED])

        failed_executions = len([r for r in self.execution_history.values()
                               if r.status == WorkflowStatus.FAILED])

        avg_duration = 0.0
        if successful_executions > 0:
            durations = [r.duration_seconds for r in self.execution_history.values()
                        if r.status == WorkflowStatus.COMPLETED and r.duration_seconds]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "active_executions": active_count,
            "total_executions": history_count,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": successful_executions / max(history_count, 1),
            "average_duration_seconds": avg_duration,
            "max_concurrent_executions": self.max_concurrent_executions,
            "max_concurrent_steps": self.max_concurrent_steps
        }