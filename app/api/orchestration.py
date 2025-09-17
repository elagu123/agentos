"""
API endpoints for workflow orchestration
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
import asyncio
import json
from datetime import datetime

from app.utils.clerk_auth import get_current_user, require_permission
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from sqlalchemy import select

from app.orchestration import (
    orchestrator_instance, template_manager,
    WorkflowDefinition, WorkflowTemplate, WorkflowExecution,
    WorkflowExecutor, ExecutionMode, ExecutionPriority,
    DependencyResolver
)

router = APIRouter(prefix="/orchestration", tags=["orchestration"])
security = HTTPBearer()


# Request/Response Models
class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., description="Nombre del workflow")
    description: Optional[str] = Field(None, description="Descripción del workflow")
    workflow_definition: Dict[str, Any] = Field(..., description="Definición completa del workflow")


class WorkflowExecuteRequest(BaseModel):
    workflow_id: str = Field(..., description="ID del workflow a ejecutar")
    input_variables: Dict[str, Any] = Field(default_factory=dict, description="Variables de entrada")
    execution_mode: str = Field("synchronous", description="Modo de ejecución")
    priority: str = Field("normal", description="Prioridad de ejecución")
    execution_config: Optional[Dict[str, Any]] = Field(None, description="Configuración adicional")


class TemplateInstallRequest(BaseModel):
    template_id: str = Field(..., description="ID del template a instalar")
    customization: Optional[Dict[str, Any]] = Field(None, description="Customizaciones del template")
    workflow_name: Optional[str] = Field(None, description="Nombre personalizado para el workflow")


class WorkflowValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: Optional[List[str]] = None


class ExecutionStatusResponse(BaseModel):
    execution_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    current_step: Optional[str] = None
    progress_percentage: Optional[float] = None
    error_message: Optional[str] = None


class WorkflowMetricsResponse(BaseModel):
    workflow_id: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration: float
    last_execution: Optional[str] = None


# Global workflow executor instance
workflow_executor = WorkflowExecutor(orchestrator_instance)


# WebSocket manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, execution_id: str):
        await websocket.accept()
        self.active_connections[execution_id] = websocket

    def disconnect(self, execution_id: str):
        if execution_id in self.active_connections:
            del self.active_connections[execution_id]

    async def send_update(self, execution_id: str, message: dict):
        if execution_id in self.active_connections:
            try:
                await self.active_connections[execution_id].send_text(json.dumps(message))
            except:
                self.disconnect(execution_id)


manager = ConnectionManager()


# Workflow Management Endpoints

@router.post("/workflows", response_model=Dict[str, Any])
async def create_workflow(
    request: WorkflowCreateRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Crea un nuevo workflow personalizado"""
    try:
        # Validar definición del workflow
        workflow_def = WorkflowDefinition.parse_obj(request.workflow_definition)

        # Asignar metadata adicional
        workflow_def.name = request.name
        workflow_def.description = request.description
        workflow_def.author = f"{current_user.first_name} {current_user.last_name}"
        workflow_def.created_at = datetime.now()

        # Validar workflow
        validation = workflow_def.validate_workflow()
        if not validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid workflow: {'; '.join(validation.errors)}"
            )

        # En una implementación completa, aquí se guardaría en base de datos
        # Por ahora, retornamos la definición validada

        return {
            "workflow_id": workflow_def.id,
            "name": workflow_def.name,
            "status": "created",
            "validation": {
                "is_valid": validation.is_valid,
                "warnings": validation.warnings
            },
            "created_at": workflow_def.created_at.isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}")


@router.post("/workflows/validate", response_model=WorkflowValidationResponse)
async def validate_workflow(
    workflow_definition: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Valida un workflow sin crearlo"""
    try:
        workflow_def = WorkflowDefinition.parse_obj(workflow_definition)
        validation = workflow_def.validate_workflow()

        # Obtener sugerencias adicionales
        dependency_resolver = DependencyResolver()
        bottleneck_analysis = dependency_resolver.analyze_bottlenecks(workflow_def)

        return WorkflowValidationResponse(
            is_valid=validation.is_valid,
            errors=validation.errors,
            warnings=validation.warnings,
            suggestions=bottleneck_analysis["optimization_suggestions"]
        )

    except Exception as e:
        return WorkflowValidationResponse(
            is_valid=False,
            errors=[f"Validation error: {str(e)}"],
            warnings=[],
            suggestions=[]
        )


@router.get("/workflows/{workflow_id}/visualization")
async def get_workflow_visualization(
    workflow_id: str,
    current_user: User = Depends(get_current_user)
):
    """Obtiene datos de visualización para el workflow"""
    try:
        # En implementación completa, obtener workflow de BD
        # Por ahora, usar un template como ejemplo
        template = template_manager.get_template_by_id("content_creation")
        if not template:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow_def = template.workflow_definition

        # Generar datos de visualización
        dependency_resolver = DependencyResolver()
        execution_graph = dependency_resolver.resolve_dependencies(workflow_def)
        visualization_data = execution_graph.visualize_graph()

        return visualization_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate visualization: {str(e)}")


# Execution Endpoints

@router.post("/execute", response_model=Dict[str, Any])
async def execute_workflow(
    request: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Ejecuta un workflow"""
    try:
        # Obtener organización
        organization = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = organization.scalar_one_or_none()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Por ahora, usar template como workflow de ejemplo
        template = template_manager.get_template_by_id(request.workflow_id)
        if not template:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow_def = template.workflow_definition

        # Configurar ejecución
        execution_mode = ExecutionMode(request.execution_mode)
        priority = ExecutionPriority(request.priority)

        # Ejecutar workflow
        if execution_mode == ExecutionMode.ASYNCHRONOUS:
            # Ejecución asíncrona
            execution_task = workflow_executor.execute_workflow(
                workflow=workflow_def,
                input_variables=request.input_variables,
                organization_id=str(organization.id),
                user_id=str(current_user.id),
                mode=execution_mode,
                priority=priority,
                execution_config=request.execution_config
            )

            background_tasks.add_task(lambda: asyncio.create_task(execution_task))

            return {
                "execution_id": "pending",  # Se generaría en la ejecución real
                "status": "queued",
                "mode": execution_mode.value,
                "message": "Workflow execution started in background"
            }

        else:
            # Ejecución síncrona
            result = await workflow_executor.execute_workflow(
                workflow=workflow_def,
                input_variables=request.input_variables,
                organization_id=str(organization.id),
                user_id=str(current_user.id),
                mode=execution_mode,
                priority=priority,
                execution_config=request.execution_config
            )

            return {
                "execution_id": result.execution_id,
                "status": result.status.value,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "duration_seconds": result.duration_seconds,
                "steps_executed": result.steps_executed,
                "final_variables": result.final_variables,
                "step_results": result.step_results
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@router.get("/executions/{execution_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(
    execution_id: str,
    current_user: User = Depends(get_current_user)
):
    """Obtiene el estado de una ejecución"""
    try:
        status = workflow_executor.get_execution_status(execution_id)
        if not status:
            raise HTTPException(status_code=404, detail="Execution not found")

        return ExecutionStatusResponse(
            execution_id=execution_id,
            status=status["status"],
            started_at=status.get("started_at"),
            completed_at=status.get("completed_at"),
            duration_seconds=status.get("duration_seconds"),
            current_step=status.get("current_step"),
            error_message=status.get("error_message")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get execution status: {str(e)}")


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user)
):
    """Cancela una ejecución activa"""
    try:
        cancelled = await workflow_executor.cancel_execution(execution_id)
        if not cancelled:
            raise HTTPException(status_code=404, detail="Execution not found or already completed")

        return {
            "execution_id": execution_id,
            "status": "cancelled",
            "message": "Execution cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel execution: {str(e)}")


@router.get("/executions", response_model=List[Dict[str, Any]])
async def list_executions(
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0
):
    """Lista ejecuciones del usuario"""
    try:
        # Obtener ejecuciones activas
        active_executions = workflow_executor.get_active_executions()

        # En implementación completa, esto consultaría la base de datos
        # con filtros por usuario/organización, paginación, etc.

        return active_executions[offset:offset + limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list executions: {str(e)}")


# Template Management Endpoints

@router.get("/templates", response_model=List[Dict[str, Any]])
async def list_templates(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Lista templates disponibles"""
    try:
        templates = template_manager.get_available_templates(category)

        return [
            {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "tags": template.tags,
                "author": template.author,
                "version": template.version,
                "download_count": template.download_count,
                "rating": template.rating,
                "created_at": template.created_at.isoformat()
            }
            for template in templates
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@router.get("/templates/{template_id}", response_model=Dict[str, Any])
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """Obtiene detalles de un template"""
    try:
        template = template_manager.get_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "tags": template.tags,
            "author": template.author,
            "version": template.version,
            "workflow_definition": template.workflow_definition.dict(),
            "required_variables": [var.dict() for var in template.required_variables],
            "installation_notes": template.installation_notes,
            "download_count": template.download_count,
            "rating": template.rating,
            "created_at": template.created_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get template: {str(e)}")


@router.post("/templates/{template_id}/install", response_model=Dict[str, Any])
async def install_template(
    template_id: str,
    request: TemplateInstallRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Instala un template creando un workflow customizado"""
    try:
        # Obtener template
        template = template_manager.get_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Obtener organización
        organization = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = organization.scalar_one_or_none()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Validar compatibilidad
        available_agents = ["copywriter", "researcher", "scheduler", "email_responder", "data_analyzer"]
        compatibility = template_manager.validate_template_compatibility(template, available_agents)

        if not compatibility["compatible"]:
            raise HTTPException(
                status_code=400,
                detail=f"Template not compatible: {compatibility['validation_message']}"
            )

        # Instalar template
        workflow = template_manager.install_template(
            template=template,
            organization_id=str(organization.id),
            customization=request.customization
        )

        # Aplicar nombre personalizado si se proporciona
        if request.workflow_name:
            workflow.name = request.workflow_name

        # En implementación completa, guardar workflow en BD

        return {
            "workflow_id": workflow.id,
            "name": workflow.name,
            "template_id": template_id,
            "template_name": template.name,
            "status": "installed",
            "customizations_applied": bool(request.customization),
            "created_at": workflow.created_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to install template: {str(e)}")


@router.get("/templates/categories")
async def get_template_categories(
    current_user: User = Depends(get_current_user)
):
    """Obtiene templates agrupados por categoría"""
    try:
        categories = template_manager.get_templates_by_category()

        return {
            category: [
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "tags": template.tags,
                    "rating": template.rating
                }
                for template in templates
            ]
            for category, templates in categories.items()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/templates/search")
async def search_templates(
    q: str,
    category: Optional[str] = None,
    tags: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Busca templates por texto y filtros"""
    try:
        filters = {}
        if category:
            filters["category"] = category
        if tags:
            filters["tags"] = tags.split(",")

        results = template_manager.search_templates(q, filters)

        return [
            {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "tags": template.tags,
                "rating": template.rating
            }
            for template in results
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# Analytics and Monitoring Endpoints

@router.get("/metrics/executor")
async def get_executor_metrics(
    current_user: User = Depends(get_current_user)
):
    """Obtiene métricas del executor"""
    try:
        metrics = workflow_executor.get_execution_metrics()
        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/workflows/{workflow_id}/metrics", response_model=WorkflowMetricsResponse)
async def get_workflow_metrics(
    workflow_id: str,
    current_user: User = Depends(get_current_user)
):
    """Obtiene métricas de un workflow específico"""
    try:
        # En implementación completa, esto consultaría métricas de BD
        # Por ahora, retornar datos simulados

        return WorkflowMetricsResponse(
            workflow_id=workflow_id,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            average_duration=0.0,
            last_execution=None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow metrics: {str(e)}")


# WebSocket endpoint for real-time execution updates

@router.websocket("/executions/{execution_id}/stream")
async def execution_stream(websocket: WebSocket, execution_id: str):
    """WebSocket para streaming de ejecución en tiempo real"""
    await manager.connect(websocket, execution_id)

    try:
        # Enviar estado inicial
        await manager.send_update(execution_id, {
            "type": "connection_established",
            "execution_id": execution_id,
            "timestamp": datetime.now().isoformat()
        })

        # Mantener conexión activa
        while True:
            # En implementación real, esto escucharía eventos de ejecución
            # y los enviaría al cliente
            await asyncio.sleep(1)

            # Ejemplo de update
            await manager.send_update(execution_id, {
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat()
            })

    except WebSocketDisconnect:
        manager.disconnect(execution_id)


# Advanced execution endpoint with streaming

@router.post("/execute-stream")
async def execute_workflow_stream(
    request: WorkflowExecuteRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Ejecuta workflow con streaming de eventos"""
    try:
        # Obtener organización
        organization = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = organization.scalar_one_or_none()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Obtener template/workflow
        template = template_manager.get_template_by_id(request.workflow_id)
        if not template:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow_def = template.workflow_definition

        # Ejecutar con streaming (simulado)
        execution_id = f"exec_{datetime.now().timestamp()}"

        # En implementación real, esto iniciaría la ejecución streaming
        # y retornaría el execution_id para conectar via WebSocket

        return {
            "execution_id": execution_id,
            "status": "started",
            "websocket_url": f"/api/v1/orchestration/executions/{execution_id}/stream",
            "message": "Connect to WebSocket URL for real-time updates"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming execution failed: {str(e)}")


# Utility endpoints

@router.post("/workflows/{workflow_id}/clone")
async def clone_workflow(
    workflow_id: str,
    new_name: str,
    current_user: User = Depends(get_current_user)
):
    """Clona un workflow existente"""
    try:
        # Obtener workflow original (por ahora usar template)
        template = template_manager.get_template_by_id(workflow_id)
        if not template:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Crear copia
        workflow_copy = template.workflow_definition.copy(deep=True)
        workflow_copy.name = new_name
        workflow_copy.id = f"clone_{datetime.now().timestamp()}"
        workflow_copy.created_at = datetime.now()

        return {
            "workflow_id": workflow_copy.id,
            "name": workflow_copy.name,
            "cloned_from": workflow_id,
            "status": "cloned",
            "created_at": workflow_copy.created_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clone workflow: {str(e)}")


@router.get("/workflows/{workflow_id}/export")
async def export_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user)
):
    """Exporta un workflow en formato JSON"""
    try:
        template = template_manager.get_template_by_id(workflow_id)
        if not template:
            raise HTTPException(status_code=404, detail="Workflow not found")

        export_data = template_manager.export_template(workflow_id)

        return {
            "workflow_id": workflow_id,
            "export_data": json.loads(export_data),
            "exported_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export workflow: {str(e)}")


def include_orchestration_router(app):
    """Include orchestration router in main app"""
    app.include_router(router)