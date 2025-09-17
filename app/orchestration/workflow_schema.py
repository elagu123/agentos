"""
Workflow Schema Definitions

Define la estructura y validación de workflows para el sistema de orquestación.
"""

from typing import Dict, List, Any, Optional, Union, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid
import json
from pydantic import BaseModel, Field, validator


class StepType(Enum):
    """Tipos de pasos en workflows"""
    AGENT_TASK = "agent_task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"
    DELAY = "delay"
    WEBHOOK = "webhook"
    HUMAN_APPROVAL = "human_approval"
    DATA_TRANSFORM = "data_transform"


class ConditionOperator(Enum):
    """Operadores para condiciones"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    REGEX_MATCH = "regex_match"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"


class WorkflowStatus(Enum):
    """Estados de workflows"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Estados de pasos individuales"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


class WorkflowVariable(BaseModel):
    """Variable de workflow"""
    name: str = Field(..., description="Nombre de la variable")
    type: Literal["string", "number", "boolean", "object", "array"] = Field(..., description="Tipo de dato")
    default_value: Optional[Any] = Field(None, description="Valor por defecto")
    required: bool = Field(False, description="Si es requerida")
    description: Optional[str] = Field(None, description="Descripción de la variable")

    @validator('name')
    def validate_name(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Variable name must be alphanumeric with underscores')
        return v


class StepCondition(BaseModel):
    """Condición para ejecutar un paso"""
    variable: str = Field(..., description="Variable a evaluar")
    operator: ConditionOperator = Field(..., description="Operador de comparación")
    value: Any = Field(..., description="Valor a comparar")
    logical_operator: Optional[Literal["AND", "OR"]] = Field(None, description="Operador lógico para múltiples condiciones")


class StepConnection(BaseModel):
    """Conexión entre pasos"""
    from_step: str = Field(..., description="ID del paso origen")
    to_step: str = Field(..., description="ID del paso destino")
    condition: Optional[StepCondition] = Field(None, description="Condición para la conexión")
    label: Optional[str] = Field(None, description="Etiqueta de la conexión")


class AgentTaskConfig(BaseModel):
    """Configuración para tarea de agente"""
    agent_type: str = Field(..., description="Tipo de agente")
    task_prompt: str = Field(..., description="Prompt para la tarea")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parámetros adicionales")
    timeout: int = Field(300, description="Timeout en segundos")
    retry_attempts: int = Field(3, description="Intentos de reintento")
    output_variable: Optional[str] = Field(None, description="Variable donde guardar el resultado")


class ConditionalConfig(BaseModel):
    """Configuración para paso condicional"""
    conditions: List[StepCondition] = Field(..., description="Lista de condiciones")
    true_path: str = Field(..., description="Paso a ejecutar si es verdadero")
    false_path: Optional[str] = Field(None, description="Paso a ejecutar si es falso")


class LoopConfig(BaseModel):
    """Configuración para bucle"""
    iteration_variable: str = Field(..., description="Variable de iteración")
    data_source: str = Field(..., description="Fuente de datos para iterar")
    steps: List[str] = Field(..., description="Pasos a ejecutar en cada iteración")
    max_iterations: int = Field(100, description="Máximo número de iteraciones")


class ParallelConfig(BaseModel):
    """Configuración para ejecución paralela"""
    steps: List[str] = Field(..., description="Pasos a ejecutar en paralelo")
    wait_for_all: bool = Field(True, description="Esperar a que terminen todos")
    continue_on_error: bool = Field(False, description="Continuar si uno falla")


class WebhookConfig(BaseModel):
    """Configuración para webhook"""
    url: str = Field(..., description="URL del webhook")
    method: Literal["GET", "POST", "PUT", "DELETE"] = Field("POST", description="Método HTTP")
    headers: Dict[str, str] = Field(default_factory=dict, description="Headers HTTP")
    payload: Optional[Dict[str, Any]] = Field(None, description="Payload del request")
    output_variable: Optional[str] = Field(None, description="Variable donde guardar la respuesta")


class HumanApprovalConfig(BaseModel):
    """Configuración para aprobación humana"""
    message: str = Field(..., description="Mensaje para el humano")
    approvers: List[str] = Field(..., description="Lista de usuarios que pueden aprobar")
    timeout_hours: int = Field(24, description="Horas antes de timeout")
    auto_approve: bool = Field(False, description="Auto-aprobar después del timeout")


class DataTransformConfig(BaseModel):
    """Configuración para transformación de datos"""
    input_variable: str = Field(..., description="Variable de entrada")
    output_variable: str = Field(..., description="Variable de salida")
    transformation: str = Field(..., description="Tipo de transformación")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parámetros de transformación")


class WorkflowStep(BaseModel):
    """Definición de paso en workflow"""
    id: str = Field(..., description="ID único del paso")
    name: str = Field(..., description="Nombre descriptivo")
    type: StepType = Field(..., description="Tipo de paso")
    description: Optional[str] = Field(None, description="Descripción del paso")

    # Configuraciones específicas por tipo
    agent_config: Optional[AgentTaskConfig] = Field(None, description="Config para agente")
    condition_config: Optional[ConditionalConfig] = Field(None, description="Config para condición")
    loop_config: Optional[LoopConfig] = Field(None, description="Config para bucle")
    parallel_config: Optional[ParallelConfig] = Field(None, description="Config para paralelo")
    webhook_config: Optional[WebhookConfig] = Field(None, description="Config para webhook")
    approval_config: Optional[HumanApprovalConfig] = Field(None, description="Config para aprobación")
    transform_config: Optional[DataTransformConfig] = Field(None, description="Config para transformación")

    # Metadata
    position: Dict[str, float] = Field(default_factory=dict, description="Posición en editor visual")
    tags: List[str] = Field(default_factory=list, description="Tags del paso")

    @validator('id')
    def validate_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Step ID cannot be empty')
        return v.strip()

    def validate_config(self) -> List[str]:
        """Valida que la configuración sea correcta para el tipo de paso"""
        errors = []

        if self.type == StepType.AGENT_TASK and not self.agent_config:
            errors.append("Agent task requires agent_config")
        elif self.type == StepType.CONDITION and not self.condition_config:
            errors.append("Condition step requires condition_config")
        elif self.type == StepType.LOOP and not self.loop_config:
            errors.append("Loop step requires loop_config")
        elif self.type == StepType.PARALLEL and not self.parallel_config:
            errors.append("Parallel step requires parallel_config")
        elif self.type == StepType.WEBHOOK and not self.webhook_config:
            errors.append("Webhook step requires webhook_config")
        elif self.type == StepType.HUMAN_APPROVAL and not self.approval_config:
            errors.append("Human approval step requires approval_config")
        elif self.type == StepType.DATA_TRANSFORM and not self.transform_config:
            errors.append("Data transform step requires transform_config")

        return errors


class WorkflowDefinition(BaseModel):
    """Definición completa de workflow"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único del workflow")
    name: str = Field(..., description="Nombre del workflow")
    description: Optional[str] = Field(None, description="Descripción del workflow")
    version: str = Field("1.0.0", description="Versión del workflow")

    # Estructura del workflow
    variables: List[WorkflowVariable] = Field(default_factory=list, description="Variables del workflow")
    steps: List[WorkflowStep] = Field(..., description="Pasos del workflow")
    connections: List[StepConnection] = Field(default_factory=list, description="Conexiones entre pasos")

    # Configuración de ejecución
    start_step: str = Field(..., description="ID del paso inicial")
    end_steps: List[str] = Field(default_factory=list, description="IDs de pasos finales")
    timeout_minutes: int = Field(60, description="Timeout total en minutos")
    max_retries: int = Field(3, description="Máximo reintentos globales")

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags del workflow")
    category: Optional[str] = Field(None, description="Categoría del workflow")
    author: Optional[str] = Field(None, description="Autor del workflow")
    created_at: datetime = Field(default_factory=datetime.now, description="Fecha de creación")
    updated_at: datetime = Field(default_factory=datetime.now, description="Fecha de actualización")

    # Estados
    status: WorkflowStatus = Field(WorkflowStatus.DRAFT, description="Estado del workflow")
    is_template: bool = Field(False, description="Si es un template")
    is_public: bool = Field(False, description="Si es público")

    def validate_workflow(self) -> "WorkflowValidationResult":
        """Valida la estructura completa del workflow"""
        errors = []
        warnings = []

        # Validar que existe el paso inicial
        step_ids = {step.id for step in self.steps}
        if self.start_step not in step_ids:
            errors.append(f"Start step '{self.start_step}' not found in steps")

        # Validar pasos finales
        for end_step in self.end_steps:
            if end_step not in step_ids:
                errors.append(f"End step '{end_step}' not found in steps")

        # Validar conexiones
        for conn in self.connections:
            if conn.from_step not in step_ids:
                errors.append(f"Connection from unknown step: {conn.from_step}")
            if conn.to_step not in step_ids:
                errors.append(f"Connection to unknown step: {conn.to_step}")

        # Validar configuraciones de pasos
        for step in self.steps:
            step_errors = step.validate_config()
            errors.extend([f"Step '{step.id}': {error}" for error in step_errors])

        # Validar variables referenciadas
        variable_names = {var.name for var in self.variables}
        for step in self.steps:
            if step.agent_config and step.agent_config.output_variable:
                if step.agent_config.output_variable not in variable_names:
                    warnings.append(f"Step '{step.id}' outputs to undefined variable: {step.agent_config.output_variable}")

        # Verificar alcanzabilidad de pasos
        reachable_steps = self._find_reachable_steps()
        unreachable = step_ids - reachable_steps
        if unreachable:
            warnings.extend([f"Unreachable step: {step_id}" for step_id in unreachable])

        # Detectar ciclos infinitos
        if self._has_infinite_loops():
            errors.append("Workflow contains potential infinite loops")

        return WorkflowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_at=datetime.now()
        )

    def _find_reachable_steps(self) -> set:
        """Encuentra todos los pasos alcanzables desde el inicio"""
        reachable = set()
        to_visit = {self.start_step}

        connection_map = {}
        for conn in self.connections:
            if conn.from_step not in connection_map:
                connection_map[conn.from_step] = []
            connection_map[conn.from_step].append(conn.to_step)

        while to_visit:
            current = to_visit.pop()
            if current in reachable:
                continue
            reachable.add(current)

            # Agregar pasos conectados
            if current in connection_map:
                for next_step in connection_map[current]:
                    if next_step not in reachable:
                        to_visit.add(next_step)

        return reachable

    def _has_infinite_loops(self) -> bool:
        """Detecta si hay bucles infinitos potenciales"""
        # Implementación simplificada - detecta ciclos sin salida
        connection_map = {}
        for conn in self.connections:
            if conn.from_step not in connection_map:
                connection_map[conn.from_step] = []
            connection_map[conn.from_step].append(conn.to_step)

        # Usar DFS para detectar ciclos
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in connection_map.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for step_id in {step.id for step in self.steps}:
            if step_id not in visited:
                if has_cycle(step_id):
                    return True

        return False


class WorkflowValidationResult(BaseModel):
    """Resultado de validación de workflow"""
    is_valid: bool = Field(..., description="Si el workflow es válido")
    errors: List[str] = Field(default_factory=list, description="Lista de errores")
    warnings: List[str] = Field(default_factory=list, description="Lista de advertencias")
    validated_at: datetime = Field(..., description="Cuando se validó")


class WorkflowTemplate(BaseModel):
    """Template de workflow reutilizable"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único del template")
    name: str = Field(..., description="Nombre del template")
    description: str = Field(..., description="Descripción del template")
    category: str = Field(..., description="Categoría del template")
    tags: List[str] = Field(default_factory=list, description="Tags del template")

    # Definición del workflow
    workflow_definition: WorkflowDefinition = Field(..., description="Definición del workflow")

    # Metadata del template
    author: str = Field(..., description="Autor del template")
    version: str = Field("1.0.0", description="Versión del template")
    license: Optional[str] = Field(None, description="Licencia del template")

    # Configuración de instalación
    required_variables: List[WorkflowVariable] = Field(default_factory=list, description="Variables requeridas para instalar")
    installation_notes: Optional[str] = Field(None, description="Notas de instalación")

    # Estadísticas
    download_count: int = Field(0, description="Número de descargas")
    rating: float = Field(0.0, description="Rating promedio")
    rating_count: int = Field(0, description="Número de ratings")

    # Estados
    is_public: bool = Field(True, description="Si es público")
    is_verified: bool = Field(False, description="Si está verificado")

    created_at: datetime = Field(default_factory=datetime.now, description="Fecha de creación")
    updated_at: datetime = Field(default_factory=datetime.now, description="Fecha de actualización")


class WorkflowExecution(BaseModel):
    """Registro de ejecución de workflow"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único de ejecución")
    workflow_id: str = Field(..., description="ID del workflow ejecutado")
    workflow_version: str = Field(..., description="Versión del workflow")

    # Estado de ejecución
    status: WorkflowStatus = Field(WorkflowStatus.PENDING, description="Estado de ejecución")
    current_step: Optional[str] = Field(None, description="Paso actual")

    # Datos de ejecución
    input_variables: Dict[str, Any] = Field(default_factory=dict, description="Variables de entrada")
    runtime_variables: Dict[str, Any] = Field(default_factory=dict, description="Variables en runtime")
    step_results: Dict[str, Any] = Field(default_factory=dict, description="Resultados de pasos")

    # Timing
    started_at: Optional[datetime] = Field(None, description="Inicio de ejecución")
    completed_at: Optional[datetime] = Field(None, description="Fin de ejecución")
    duration_seconds: Optional[float] = Field(None, description="Duración en segundos")

    # Metadata
    triggered_by: str = Field(..., description="Usuario que ejecutó")
    organization_id: str = Field(..., description="ID de la organización")

    # Errores y logs
    error_message: Optional[str] = Field(None, description="Mensaje de error si falló")
    execution_log: List[Dict[str, Any]] = Field(default_factory=list, description="Log de ejecución")

    created_at: datetime = Field(default_factory=datetime.now, description="Fecha de creación")


# Esquemas para exportar/importar workflows
class WorkflowExportFormat(BaseModel):
    """Formato para exportar workflows"""
    format_version: str = Field("1.0", description="Versión del formato")
    exported_at: datetime = Field(default_factory=datetime.now, description="Fecha de exportación")
    exported_by: str = Field(..., description="Usuario que exportó")

    workflow: WorkflowDefinition = Field(..., description="Definición del workflow")
    dependencies: List[str] = Field(default_factory=list, description="Dependencias requeridas")

    def to_json(self) -> str:
        """Convierte a JSON para exportar"""
        return self.json(indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowExportFormat":
        """Crea desde JSON importado"""
        return cls.parse_raw(json_str)