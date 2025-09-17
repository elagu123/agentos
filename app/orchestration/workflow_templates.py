"""
Workflow Template Manager

Sistema para gestionar templates de workflows reutilizables,
incluyendo templates predefinidos y templates del marketplace.
"""

from typing import Dict, List, Any, Optional
import json
import uuid
from datetime import datetime
from pathlib import Path

from .workflow_schema import (
    WorkflowTemplate, WorkflowDefinition, WorkflowStep, WorkflowVariable,
    StepType, AgentTaskConfig, ConditionalConfig, StepConnection
)


class WorkflowTemplateManager:
    """
    Manager para templates de workflows que permite:
    - Crear y gestionar templates predefinidos
    - Instalar templates desde el marketplace
    - Customizar templates para organizaciones específicas
    """

    def __init__(self):
        self.built_in_templates = self._load_built_in_templates()
        self.custom_templates: Dict[str, WorkflowTemplate] = {}

    def _load_built_in_templates(self) -> Dict[str, WorkflowTemplate]:
        """Carga templates predefinidos del sistema"""
        templates = {}

        # Template: Content Creation Workflow
        templates["content_creation"] = self._create_content_creation_template()

        # Template: Customer Support Workflow
        templates["customer_support"] = self._create_customer_support_template()

        # Template: Research & Analysis Workflow
        templates["research_analysis"] = self._create_research_analysis_template()

        # Template: Email Campaign Workflow
        templates["email_campaign"] = self._create_email_campaign_template()

        # Template: Data Processing Workflow
        templates["data_processing"] = self._create_data_processing_template()

        # Template: Lead Qualification Workflow
        templates["lead_qualification"] = self._create_lead_qualification_template()

        return templates

    def _create_content_creation_template(self) -> WorkflowTemplate:
        """Template para creación de contenido automática"""

        # Variables del workflow
        variables = [
            WorkflowVariable(
                name="topic",
                type="string",
                required=True,
                description="Tema para el contenido"
            ),
            WorkflowVariable(
                name="target_audience",
                type="string",
                required=True,
                description="Audiencia objetivo"
            ),
            WorkflowVariable(
                name="content_type",
                type="string",
                default_value="blog_post",
                description="Tipo de contenido (blog_post, social_media, email)"
            ),
            WorkflowVariable(
                name="tone",
                type="string",
                default_value="professional",
                description="Tono del contenido"
            )
        ]

        # Pasos del workflow
        steps = [
            # Paso 1: Investigación del tema
            WorkflowStep(
                id="research_topic",
                name="Investigar Tema",
                type=StepType.AGENT_TASK,
                description="Investigar el tema para obtener información relevante",
                agent_config=AgentTaskConfig(
                    agent_type="researcher",
                    task_prompt="Investiga información relevante sobre: {topic}. Busca tendencias actuales, estadísticas y puntos clave para audiencia: {target_audience}",
                    parameters={"search_depth": "comprehensive"},
                    output_variable="research_data"
                )
            ),

            # Paso 2: Crear outline del contenido
            WorkflowStep(
                id="create_outline",
                name="Crear Outline",
                type=StepType.AGENT_TASK,
                description="Crear estructura del contenido basada en la investigación",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Basándote en esta investigación: {research_data}, crea un outline detallado para {content_type} sobre {topic} dirigido a {target_audience} con tono {tone}",
                    output_variable="content_outline"
                )
            ),

            # Paso 3: Escribir contenido principal
            WorkflowStep(
                id="write_content",
                name="Escribir Contenido",
                type=StepType.AGENT_TASK,
                description="Escribir el contenido completo",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Escribe el contenido completo siguiendo este outline: {content_outline}. Tipo: {content_type}, Audiencia: {target_audience}, Tono: {tone}",
                    parameters={"max_tokens": 3000},
                    output_variable="final_content"
                )
            ),

            # Paso 4: Crear variaciones para A/B testing
            WorkflowStep(
                id="create_variations",
                name="Crear Variaciones",
                type=StepType.AGENT_TASK,
                description="Crear variaciones del contenido para testing",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Crea 2 variaciones del siguiente contenido para A/B testing: {final_content}",
                    output_variable="content_variations"
                )
            )
        ]

        # Conexiones entre pasos
        connections = [
            StepConnection(from_step="research_topic", to_step="create_outline"),
            StepConnection(from_step="create_outline", to_step="write_content"),
            StepConnection(from_step="write_content", to_step="create_variations")
        ]

        # Crear workflow definition
        workflow_def = WorkflowDefinition(
            name="Content Creation Workflow",
            description="Workflow automatizado para crear contenido de alta calidad",
            variables=variables,
            steps=steps,
            connections=connections,
            start_step="research_topic",
            end_steps=["create_variations"],
            tags=["content", "marketing", "copywriting"],
            category="marketing"
        )

        return WorkflowTemplate(
            name="Content Creation Workflow",
            description="Automatiza la creación de contenido desde investigación hasta variaciones A/B",
            category="marketing",
            tags=["content", "copywriting", "research", "ab-testing"],
            workflow_definition=workflow_def,
            author="AgentOS Team",
            required_variables=variables,
            installation_notes="Este template requiere acceso a agentes de investigación y copywriting."
        )

    def _create_customer_support_template(self) -> WorkflowTemplate:
        """Template para atención al cliente automatizada"""

        variables = [
            WorkflowVariable(
                name="customer_email",
                type="object",
                required=True,
                description="Email completo del cliente"
            ),
            WorkflowVariable(
                name="urgency_threshold",
                type="number",
                default_value=0.8,
                description="Umbral de urgencia para escalación"
            )
        ]

        steps = [
            # Análisis del email
            WorkflowStep(
                id="analyze_email",
                name="Analizar Email",
                type=StepType.AGENT_TASK,
                description="Analizar el email del cliente",
                agent_config=AgentTaskConfig(
                    agent_type="email_responder",
                    task_prompt="Analiza este email de cliente: {customer_email}",
                    output_variable="email_analysis"
                )
            ),

            # Condición: ¿Requiere escalación?
            WorkflowStep(
                id="check_escalation",
                name="Verificar Escalación",
                type=StepType.CONDITION,
                description="Verificar si requiere escalación a humano",
                condition_config=ConditionalConfig(
                    conditions=[],  # Se configuraría con la lógica real
                    true_path="escalate_to_human",
                    false_path="generate_response"
                )
            ),

            # Escalación a humano
            WorkflowStep(
                id="escalate_to_human",
                name="Escalar a Humano",
                type=StepType.HUMAN_APPROVAL,
                description="Escalar a agente humano"
            ),

            # Generar respuesta automática
            WorkflowStep(
                id="generate_response",
                name="Generar Respuesta",
                type=StepType.AGENT_TASK,
                description="Generar respuesta automática",
                agent_config=AgentTaskConfig(
                    agent_type="email_responder",
                    task_prompt="Genera una respuesta profesional basada en este análisis: {email_analysis}",
                    output_variable="auto_response"
                )
            )
        ]

        connections = [
            StepConnection(from_step="analyze_email", to_step="check_escalation"),
            StepConnection(from_step="check_escalation", to_step="escalate_to_human"),
            StepConnection(from_step="check_escalation", to_step="generate_response")
        ]

        workflow_def = WorkflowDefinition(
            name="Customer Support Workflow",
            description="Workflow para atención automatizada al cliente",
            variables=variables,
            steps=steps,
            connections=connections,
            start_step="analyze_email",
            end_steps=["escalate_to_human", "generate_response"],
            tags=["support", "customer", "email"],
            category="customer_service"
        )

        return WorkflowTemplate(
            name="Customer Support Workflow",
            description="Automatiza la atención al cliente con escalación inteligente",
            category="customer_service",
            tags=["support", "email", "automation", "escalation"],
            workflow_definition=workflow_def,
            author="AgentOS Team",
            required_variables=variables
        )

    def _create_research_analysis_template(self) -> WorkflowTemplate:
        """Template para investigación y análisis comprehensivo"""

        variables = [
            WorkflowVariable(
                name="research_topic",
                type="string",
                required=True,
                description="Tema a investigar"
            ),
            WorkflowVariable(
                name="analysis_depth",
                type="string",
                default_value="standard",
                description="Profundidad del análisis (basic, standard, comprehensive)"
            ),
            WorkflowVariable(
                name="include_competitors",
                type="boolean",
                default_value=True,
                description="Incluir análisis competitivo"
            )
        ]

        steps = [
            # Investigación inicial
            WorkflowStep(
                id="initial_research",
                name="Investigación Inicial",
                type=StepType.AGENT_TASK,
                description="Realizar investigación inicial del tema",
                agent_config=AgentTaskConfig(
                    agent_type="researcher",
                    task_prompt="Realiza una investigación {analysis_depth} sobre: {research_topic}",
                    output_variable="initial_findings"
                )
            ),

            # Análisis competitivo (condicional)
            WorkflowStep(
                id="competitive_analysis",
                name="Análisis Competitivo",
                type=StepType.AGENT_TASK,
                description="Realizar análisis competitivo",
                agent_config=AgentTaskConfig(
                    agent_type="researcher",
                    task_prompt="Realiza un análisis competitivo para: {research_topic}",
                    output_variable="competitive_data"
                )
            ),

            # Análisis de datos
            WorkflowStep(
                id="data_analysis",
                name="Análisis de Datos",
                type=StepType.AGENT_TASK,
                description="Analizar los datos recopilados",
                agent_config=AgentTaskConfig(
                    agent_type="data_analyzer",
                    task_prompt="Analiza estos datos de investigación: {initial_findings}. Si hay datos competitivos, inclúyelos: {competitive_data}",
                    output_variable="analysis_results"
                )
            ),

            # Generar reporte final
            WorkflowStep(
                id="generate_report",
                name="Generar Reporte",
                type=StepType.AGENT_TASK,
                description="Generar reporte comprehensivo",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Crea un reporte ejecutivo basado en: {analysis_results}. Tema: {research_topic}",
                    output_variable="final_report"
                )
            )
        ]

        connections = [
            StepConnection(from_step="initial_research", to_step="competitive_analysis"),
            StepConnection(from_step="initial_research", to_step="data_analysis"),
            StepConnection(from_step="competitive_analysis", to_step="data_analysis"),
            StepConnection(from_step="data_analysis", to_step="generate_report")
        ]

        workflow_def = WorkflowDefinition(
            name="Research & Analysis Workflow",
            description="Workflow comprehensivo para investigación y análisis",
            variables=variables,
            steps=steps,
            connections=connections,
            start_step="initial_research",
            end_steps=["generate_report"],
            tags=["research", "analysis", "reporting"],
            category="research"
        )

        return WorkflowTemplate(
            name="Research & Analysis Workflow",
            description="Workflow comprehensivo para investigación, análisis competitivo y reportes",
            category="research",
            tags=["research", "analysis", "competitive", "reporting"],
            workflow_definition=workflow_def,
            author="AgentOS Team",
            required_variables=variables
        )

    def _create_email_campaign_template(self) -> WorkflowTemplate:
        """Template para campañas de email automatizadas"""

        variables = [
            WorkflowVariable(
                name="campaign_goal",
                type="string",
                required=True,
                description="Objetivo de la campaña"
            ),
            WorkflowVariable(
                name="target_segment",
                type="string",
                required=True,
                description="Segmento objetivo"
            ),
            WorkflowVariable(
                name="send_time",
                type="string",
                default_value="09:00",
                description="Hora de envío preferida"
            )
        ]

        steps = [
            # Research audience
            WorkflowStep(
                id="research_audience",
                name="Investigar Audiencia",
                type=StepType.AGENT_TASK,
                description="Investigar características de la audiencia",
                agent_config=AgentTaskConfig(
                    agent_type="researcher",
                    task_prompt="Investiga características y preferencias del segmento: {target_segment} para campaña con objetivo: {campaign_goal}",
                    output_variable="audience_insights"
                )
            ),

            # Create subject lines
            WorkflowStep(
                id="create_subjects",
                name="Crear Subject Lines",
                type=StepType.AGENT_TASK,
                description="Crear múltiples subject lines",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Crea 5 subject lines persuasivos para {target_segment} con objetivo {campaign_goal}. Audiencia: {audience_insights}",
                    output_variable="subject_lines"
                )
            ),

            # Create email content
            WorkflowStep(
                id="create_email_content",
                name="Crear Contenido Email",
                type=StepType.AGENT_TASK,
                description="Crear el contenido del email",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Crea contenido de email para {target_segment} con objetivo {campaign_goal}. Insights: {audience_insights}",
                    output_variable="email_content"
                )
            ),

            # Schedule campaign
            WorkflowStep(
                id="schedule_campaign",
                name="Programar Campaña",
                type=StepType.AGENT_TASK,
                description="Programar el envío de la campaña",
                agent_config=AgentTaskConfig(
                    agent_type="scheduler",
                    task_prompt="Programa el envío de campaña para las {send_time}. Subject lines: {subject_lines}, Contenido: {email_content}",
                    output_variable="campaign_schedule"
                )
            )
        ]

        connections = [
            StepConnection(from_step="research_audience", to_step="create_subjects"),
            StepConnection(from_step="research_audience", to_step="create_email_content"),
            StepConnection(from_step="create_subjects", to_step="schedule_campaign"),
            StepConnection(from_step="create_email_content", to_step="schedule_campaign")
        ]

        workflow_def = WorkflowDefinition(
            name="Email Campaign Workflow",
            description="Workflow para crear y programar campañas de email",
            variables=variables,
            steps=steps,
            connections=connections,
            start_step="research_audience",
            end_steps=["schedule_campaign"],
            tags=["email", "marketing", "campaign"],
            category="marketing"
        )

        return WorkflowTemplate(
            name="Email Campaign Workflow",
            description="Automatiza la creación y programación de campañas de email personalizadas",
            category="marketing",
            tags=["email", "campaign", "automation", "scheduling"],
            workflow_definition=workflow_def,
            author="AgentOS Team",
            required_variables=variables
        )

    def _create_data_processing_template(self) -> WorkflowTemplate:
        """Template para procesamiento de datos automatizado"""

        variables = [
            WorkflowVariable(
                name="data_source",
                type="string",
                required=True,
                description="Fuente de datos a procesar"
            ),
            WorkflowVariable(
                name="analysis_type",
                type="string",
                default_value="descriptive",
                description="Tipo de análisis a realizar"
            )
        ]

        steps = [
            # Procesar datos
            WorkflowStep(
                id="process_data",
                name="Procesar Datos",
                type=StepType.AGENT_TASK,
                description="Procesar y limpiar los datos",
                agent_config=AgentTaskConfig(
                    agent_type="data_analyzer",
                    task_prompt="Procesa y analiza los datos de: {data_source} con análisis tipo: {analysis_type}",
                    output_variable="processed_data"
                )
            ),

            # Generar insights
            WorkflowStep(
                id="generate_insights",
                name="Generar Insights",
                type=StepType.AGENT_TASK,
                description="Generar insights de los datos",
                agent_config=AgentTaskConfig(
                    agent_type="data_analyzer",
                    task_prompt="Genera insights y conclusiones de estos datos procesados: {processed_data}",
                    output_variable="data_insights"
                )
            ),

            # Crear reporte
            WorkflowStep(
                id="create_data_report",
                name="Crear Reporte",
                type=StepType.AGENT_TASK,
                description="Crear reporte visual de los datos",
                agent_config=AgentTaskConfig(
                    agent_type="copywriter",
                    task_prompt="Crea un reporte ejecutivo de estos insights: {data_insights} para fuente: {data_source}",
                    output_variable="data_report"
                )
            )
        ]

        connections = [
            StepConnection(from_step="process_data", to_step="generate_insights"),
            StepConnection(from_step="generate_insights", to_step="create_data_report")
        ]

        workflow_def = WorkflowDefinition(
            name="Data Processing Workflow",
            description="Workflow para procesamiento automatizado de datos",
            variables=variables,
            steps=steps,
            connections=connections,
            start_step="process_data",
            end_steps=["create_data_report"],
            tags=["data", "analysis", "reporting"],
            category="analytics"
        )

        return WorkflowTemplate(
            name="Data Processing Workflow",
            description="Automatiza el procesamiento de datos desde ingesta hasta reportes",
            category="analytics",
            tags=["data", "processing", "analytics", "reporting"],
            workflow_definition=workflow_def,
            author="AgentOS Team",
            required_variables=variables
        )

    def _create_lead_qualification_template(self) -> WorkflowTemplate:
        """Template para calificación automatizada de leads"""

        variables = [
            WorkflowVariable(
                name="lead_data",
                type="object",
                required=True,
                description="Datos del lead a calificar"
            ),
            WorkflowVariable(
                name="qualification_criteria",
                type="object",
                default_value={"budget": 10000, "timeline": "3_months", "authority": "decision_maker"},
                description="Criterios de calificación"
            )
        ]

        steps = [
            # Analizar lead
            WorkflowStep(
                id="analyze_lead",
                name="Analizar Lead",
                type=StepType.AGENT_TASK,
                description="Analizar información del lead",
                agent_config=AgentTaskConfig(
                    agent_type="data_analyzer",
                    task_prompt="Analiza este lead: {lead_data} contra criterios: {qualification_criteria}",
                    output_variable="lead_analysis"
                )
            ),

            # Research company
            WorkflowStep(
                id="research_company",
                name="Investigar Empresa",
                type=StepType.AGENT_TASK,
                description="Investigar la empresa del lead",
                agent_config=AgentTaskConfig(
                    agent_type="researcher",
                    task_prompt="Investiga la empresa del lead basándote en: {lead_data}",
                    output_variable="company_research"
                )
            ),

            # Score lead
            WorkflowStep(
                id="score_lead",
                name="Calificar Lead",
                type=StepType.AGENT_TASK,
                description="Asignar score al lead",
                agent_config=AgentTaskConfig(
                    agent_type="data_analyzer",
                    task_prompt="Asigna un score de 1-100 al lead basándote en: {lead_analysis} y {company_research}",
                    output_variable="lead_score"
                )
            ),

            # Schedule follow-up
            WorkflowStep(
                id="schedule_followup",
                name="Programar Seguimiento",
                type=StepType.AGENT_TASK,
                description="Programar seguimiento apropiado",
                agent_config=AgentTaskConfig(
                    agent_type="scheduler",
                    task_prompt="Programa seguimiento para lead con score: {lead_score} y datos: {lead_data}",
                    output_variable="followup_schedule"
                )
            )
        ]

        connections = [
            StepConnection(from_step="analyze_lead", to_step="research_company"),
            StepConnection(from_step="analyze_lead", to_step="score_lead"),
            StepConnection(from_step="research_company", to_step="score_lead"),
            StepConnection(from_step="score_lead", to_step="schedule_followup")
        ]

        workflow_def = WorkflowDefinition(
            name="Lead Qualification Workflow",
            description="Workflow para calificación automatizada de leads",
            variables=variables,
            steps=steps,
            connections=connections,
            start_step="analyze_lead",
            end_steps=["schedule_followup"],
            tags=["sales", "leads", "qualification"],
            category="sales"
        )

        return WorkflowTemplate(
            name="Lead Qualification Workflow",
            description="Automatiza la calificación de leads con scoring y seguimiento",
            category="sales",
            tags=["sales", "leads", "qualification", "scoring"],
            workflow_definition=workflow_def,
            author="AgentOS Team",
            required_variables=variables
        )

    # Métodos públicos del manager

    def get_available_templates(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        """Obtiene templates disponibles, opcionalmente filtrados por categoría"""
        templates = list(self.built_in_templates.values()) + list(self.custom_templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        return sorted(templates, key=lambda t: t.name)

    def get_template_by_id(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Obtiene un template específico por ID"""
        # Buscar en built-in
        if template_id in self.built_in_templates:
            return self.built_in_templates[template_id]

        # Buscar en custom
        if template_id in self.custom_templates:
            return self.custom_templates[template_id]

        return None

    def install_template(
        self,
        template: WorkflowTemplate,
        organization_id: str,
        customization: Optional[Dict[str, Any]] = None
    ) -> WorkflowDefinition:
        """
        Instala un template creando un workflow customizado para la organización

        Args:
            template: Template a instalar
            organization_id: ID de la organización
            customization: Customizaciones opcionales

        Returns:
            WorkflowDefinition: Workflow customizado listo para usar
        """
        # Crear copia del workflow definition
        workflow = template.workflow_definition.copy(deep=True)

        # Aplicar customizaciones
        if customization:
            # Actualizar variables por defecto
            if "variables" in customization:
                for var_name, var_value in customization["variables"].items():
                    for variable in workflow.variables:
                        if variable.name == var_name:
                            variable.default_value = var_value

            # Personalizar prompts
            if "prompts" in customization:
                for step_id, new_prompt in customization["prompts"].items():
                    for step in workflow.steps:
                        if step.id == step_id and step.agent_config:
                            step.agent_config.task_prompt = new_prompt

            # Actualizar metadata
            if "metadata" in customization:
                workflow.name = customization["metadata"].get("name", workflow.name)
                workflow.description = customization["metadata"].get("description", workflow.description)

        # Generar nuevo ID para la instalación
        workflow.id = str(uuid.uuid4())
        workflow.created_at = datetime.now()
        workflow.updated_at = datetime.now()

        # Marcar como instalado desde template
        workflow.metadata = {
            "template_id": template.id,
            "template_name": template.name,
            "organization_id": organization_id,
            "installed_at": datetime.now().isoformat()
        }

        return workflow

    def create_custom_template(
        self,
        workflow: WorkflowDefinition,
        template_metadata: Dict[str, Any],
        author: str
    ) -> WorkflowTemplate:
        """
        Crea un template custom desde un workflow existente

        Args:
            workflow: Workflow base
            template_metadata: Metadata del template
            author: Autor del template

        Returns:
            WorkflowTemplate: Nuevo template custom
        """
        # Crear template
        template = WorkflowTemplate(
            name=template_metadata["name"],
            description=template_metadata["description"],
            category=template_metadata.get("category", "custom"),
            tags=template_metadata.get("tags", []),
            workflow_definition=workflow,
            author=author,
            required_variables=workflow.variables.copy(),
            installation_notes=template_metadata.get("installation_notes")
        )

        # Guardar en custom templates
        self.custom_templates[template.id] = template

        return template

    def validate_template_compatibility(
        self,
        template: WorkflowTemplate,
        available_agents: List[str]
    ) -> Dict[str, Any]:
        """
        Valida que un template sea compatible con los agentes disponibles

        Args:
            template: Template a validar
            available_agents: Lista de agentes disponibles

        Returns:
            Resultado de validación con compatibilidad y requisitos faltantes
        """
        required_agents = set()
        missing_agents = []

        # Extraer agentes requeridos
        for step in template.workflow_definition.steps:
            if step.agent_config:
                required_agents.add(step.agent_config.agent_type)

        # Verificar disponibilidad
        for agent_type in required_agents:
            if agent_type not in available_agents:
                missing_agents.append(agent_type)

        is_compatible = len(missing_agents) == 0

        return {
            "compatible": is_compatible,
            "required_agents": list(required_agents),
            "missing_agents": missing_agents,
            "validation_message": (
                "Template is compatible" if is_compatible
                else f"Missing required agents: {', '.join(missing_agents)}"
            )
        }

    def get_templates_by_category(self) -> Dict[str, List[WorkflowTemplate]]:
        """Agrupa templates por categoría"""
        categories = {}
        all_templates = self.get_available_templates()

        for template in all_templates:
            category = template.category or "uncategorized"
            if category not in categories:
                categories[category] = []
            categories[category].append(template)

        return categories

    def search_templates(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[WorkflowTemplate]:
        """
        Busca templates por texto y filtros

        Args:
            query: Texto de búsqueda
            filters: Filtros opcionales (category, tags, author)

        Returns:
            Lista de templates que coinciden
        """
        templates = self.get_available_templates()
        results = []

        query_lower = query.lower()

        for template in templates:
            # Verificar si coincide con el query
            matches_query = (
                query_lower in template.name.lower() or
                query_lower in template.description.lower() or
                any(query_lower in tag.lower() for tag in template.tags)
            )

            if not matches_query:
                continue

            # Aplicar filtros
            if filters:
                if "category" in filters and template.category != filters["category"]:
                    continue

                if "tags" in filters:
                    filter_tags = filters["tags"]
                    if isinstance(filter_tags, str):
                        filter_tags = [filter_tags]
                    if not any(tag in template.tags for tag in filter_tags):
                        continue

                if "author" in filters and template.author != filters["author"]:
                    continue

            results.append(template)

        return results

    def export_template(self, template_id: str) -> str:
        """Exporta un template a formato JSON"""
        template = self.get_template_by_id(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        return template.json(indent=2, ensure_ascii=False)

    def import_template(self, template_json: str) -> WorkflowTemplate:
        """Importa un template desde JSON"""
        template_data = json.loads(template_json)
        template = WorkflowTemplate.parse_obj(template_data)

        # Asignar nuevo ID para evitar conflictos
        template.id = str(uuid.uuid4())
        template.created_at = datetime.now()
        template.updated_at = datetime.now()

        # Guardar en custom templates
        self.custom_templates[template.id] = template

        return template


# Instancia global del template manager
template_manager = WorkflowTemplateManager()