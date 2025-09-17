"""
Dependency Resolver

Sistema para resolver dependencias entre pasos de workflows y determinar
el orden óptimo de ejecución.
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
import networkx as nx
from collections import deque, defaultdict

from .workflow_schema import WorkflowDefinition, WorkflowStep, StepConnection


@dataclass
class ExecutionLevel:
    """Nivel de ejecución con pasos que pueden ejecutarse en paralelo"""
    level: int
    steps: Set[str]
    dependencies_satisfied: Set[str]


class ExecutionGraph:
    """Grafo de ejecución que representa las dependencias entre pasos"""

    def __init__(self, workflow: WorkflowDefinition):
        self.workflow = workflow
        self.graph = nx.DiGraph()
        self.step_map = {step.id: step for step in workflow.steps}
        self.connection_map = self._build_connection_map()
        self._build_graph()

    def _build_connection_map(self) -> Dict[str, List[StepConnection]]:
        """Construye un mapa de conexiones organizadas por paso origen"""
        connection_map = defaultdict(list)
        for connection in self.workflow.connections:
            connection_map[connection.from_step].append(connection)
        return dict(connection_map)

    def _build_graph(self):
        """Construye el grafo dirigido de dependencias"""
        # Añadir todos los pasos como nodos
        for step in self.workflow.steps:
            self.graph.add_node(step.id, step=step)

        # Añadir conexiones como aristas
        for connection in self.workflow.connections:
            self.graph.add_edge(
                connection.from_step,
                connection.to_step,
                connection=connection
            )

        # Validar que el grafo sea acíclico
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            raise ValueError(f"Workflow contains cycles: {cycles}")

    def get_execution_levels(self) -> List[ExecutionLevel]:
        """
        Obtiene los niveles de ejecución ordenados.
        Cada nivel contiene pasos que pueden ejecutarse en paralelo.
        """
        # Usar topological sort para ordenar los pasos
        topo_order = list(nx.topological_sort(self.graph))

        # Calcular niveles basados en la longitud del camino más largo desde el inicio
        levels = {}
        for step_id in topo_order:
            # Calcular el nivel máximo de todos los predecesores + 1
            predecessors = list(self.graph.predecessors(step_id))
            if not predecessors:
                levels[step_id] = 0
            else:
                max_pred_level = max(levels[pred] for pred in predecessors)
                levels[step_id] = max_pred_level + 1

        # Agrupar pasos por nivel
        level_groups = defaultdict(set)
        for step_id, level in levels.items():
            level_groups[level].add(step_id)

        # Crear objetos ExecutionLevel
        execution_levels = []
        for level in sorted(level_groups.keys()):
            steps_at_level = level_groups[level]
            dependencies = set()

            # Encontrar todas las dependencias satisfechas hasta este nivel
            for step_id in steps_at_level:
                step_dependencies = set(self.graph.predecessors(step_id))
                dependencies.update(step_dependencies)

            execution_levels.append(ExecutionLevel(
                level=level,
                steps=steps_at_level,
                dependencies_satisfied=dependencies
            ))

        return execution_levels

    def get_ready_steps(self, completed_steps: Set[str]) -> Set[str]:
        """
        Obtiene los pasos que están listos para ejecutarse dado un conjunto
        de pasos ya completados.
        """
        ready_steps = set()

        for step_id in self.graph.nodes():
            if step_id in completed_steps:
                continue

            # Verificar si todas las dependencias están completadas
            dependencies = set(self.graph.predecessors(step_id))
            if dependencies.issubset(completed_steps):
                ready_steps.add(step_id)

        return ready_steps

    def get_step_dependencies(self, step_id: str) -> Set[str]:
        """Obtiene todas las dependencias directas de un paso"""
        return set(self.graph.predecessors(step_id))

    def get_step_dependents(self, step_id: str) -> Set[str]:
        """Obtiene todos los pasos que dependen de este paso"""
        return set(self.graph.successors(step_id))

    def get_critical_path(self) -> List[str]:
        """
        Calcula el camino crítico del workflow (el camino más largo).
        Este es el tiempo mínimo requerido para completar el workflow.
        """
        # Encontrar pasos sin dependencias (nodos fuente)
        source_nodes = [n for n in self.graph.nodes() if self.graph.in_degree(n) == 0]

        # Encontrar pasos sin dependientes (nodos sumidero)
        sink_nodes = [n for n in self.graph.nodes() if self.graph.out_degree(n) == 0]

        if not source_nodes or not sink_nodes:
            return []

        # Calcular el camino más largo desde cualquier fuente a cualquier sumidero
        longest_path = []
        max_length = 0

        for source in source_nodes:
            for sink in sink_nodes:
                try:
                    # NetworkX no tiene longest_path directamente para DAGs,
                    # así que usamos todos los caminos simples y tomamos el más largo
                    paths = list(nx.all_simple_paths(self.graph, source, sink))
                    if paths:
                        current_longest = max(paths, key=len)
                        if len(current_longest) > max_length:
                            max_length = len(current_longest)
                            longest_path = current_longest
                except nx.NetworkXNoPath:
                    continue

        return longest_path

    def estimate_execution_time(self, step_durations: Optional[Dict[str, float]] = None) -> float:
        """
        Estima el tiempo total de ejecución del workflow.

        Args:
            step_durations: Diccionario con duraciones estimadas por paso.
                          Si no se proporciona, usa estimaciones por defecto.
        """
        if step_durations is None:
            # Duraciones por defecto basadas en tipo de paso
            step_durations = {}
            for step in self.workflow.steps:
                step_durations[step.id] = self._get_default_duration(step)

        # Calcular tiempo acumulado por nivel
        levels = self.get_execution_levels()
        total_time = 0.0

        for level in levels:
            # En cada nivel, los pasos se ejecutan en paralelo,
            # así que el tiempo del nivel es el máximo de sus pasos
            level_time = 0.0
            for step_id in level.steps:
                step_duration = step_durations.get(step_id, 60.0)  # Default 1 minuto
                level_time = max(level_time, step_duration)

            total_time += level_time

        return total_time

    def _get_default_duration(self, step: WorkflowStep) -> float:
        """Obtiene duración estimada por defecto para un tipo de paso"""
        from .workflow_schema import StepType

        duration_map = {
            StepType.AGENT_TASK: 120.0,  # 2 minutos
            StepType.CONDITION: 5.0,     # 5 segundos
            StepType.PARALLEL: 0.0,      # No añade tiempo directo
            StepType.LOOP: 300.0,        # 5 minutos
            StepType.DELAY: 60.0,        # 1 minuto por defecto
            StepType.WEBHOOK: 30.0,      # 30 segundos
            StepType.HUMAN_APPROVAL: 3600.0,  # 1 hora
            StepType.DATA_TRANSFORM: 10.0     # 10 segundos
        }

        return duration_map.get(step.type, 60.0)

    def validate_execution_flow(self) -> List[str]:
        """
        Valida que el flujo de ejecución sea válido.
        Retorna una lista de problemas encontrados.
        """
        issues = []

        # Verificar que hay un paso inicial válido
        if self.workflow.start_step not in self.step_map:
            issues.append(f"Start step '{self.workflow.start_step}' not found")

        # Verificar que todos los pasos finales existen
        for end_step in self.workflow.end_steps:
            if end_step not in self.step_map:
                issues.append(f"End step '{end_step}' not found")

        # Verificar que todos los pasos son alcanzables desde el inicio
        try:
            reachable = nx.descendants(self.graph, self.workflow.start_step)
            reachable.add(self.workflow.start_step)

            unreachable_steps = set(self.step_map.keys()) - reachable
            if unreachable_steps:
                issues.append(f"Unreachable steps: {unreachable_steps}")

        except KeyError:
            issues.append("Cannot determine reachability from start step")

        # Verificar que todos los pasos finales son alcanzables
        for end_step in self.workflow.end_steps:
            if end_step in self.step_map:
                try:
                    if not nx.has_path(self.graph, self.workflow.start_step, end_step):
                        issues.append(f"End step '{end_step}' not reachable from start step")
                except nx.NetworkXNoPath:
                    issues.append(f"No path from start to end step '{end_step}'")

        return issues

    def get_parallel_execution_opportunities(self) -> List[Set[str]]:
        """
        Identifica oportunidades de ejecución paralela.
        Retorna grupos de pasos que pueden ejecutarse simultáneamente.
        """
        levels = self.get_execution_levels()
        parallel_groups = []

        for level in levels:
            if len(level.steps) > 1:
                parallel_groups.append(level.steps)

        return parallel_groups

    def visualize_graph(self) -> Dict[str, Any]:
        """
        Genera una representación del grafo para visualización.
        Retorna datos que pueden usarse en el frontend.
        """
        nodes = []
        edges = []

        # Crear nodos
        for step in self.workflow.steps:
            nodes.append({
                "id": step.id,
                "label": step.name,
                "type": step.type.value,
                "position": step.position
            })

        # Crear aristas
        for connection in self.workflow.connections:
            edges.append({
                "id": f"{connection.from_step}_{connection.to_step}",
                "source": connection.from_step,
                "target": connection.to_step,
                "label": connection.label
            })

        # Calcular niveles para layout automático
        levels = self.get_execution_levels()
        level_positions = {}
        for level in levels:
            y_position = level.level * 200  # Espaciado vertical
            x_positions = list(range(0, len(level.steps) * 300, 300))  # Espaciado horizontal

            for i, step_id in enumerate(level.steps):
                level_positions[step_id] = {
                    "x": x_positions[i] if i < len(x_positions) else i * 300,
                    "y": y_position
                }

        return {
            "nodes": nodes,
            "edges": edges,
            "levels": [{"level": l.level, "steps": list(l.steps)} for l in levels],
            "suggested_positions": level_positions,
            "critical_path": self.get_critical_path(),
            "estimated_duration": self.estimate_execution_time()
        }


class DependencyResolver:
    """
    Resolvedor de dependencias principal que coordina la resolución
    de dependencias para workflows.
    """

    def __init__(self):
        self.cache: Dict[str, ExecutionGraph] = {}

    def resolve_dependencies(self, workflow: WorkflowDefinition) -> ExecutionGraph:
        """
        Resuelve las dependencias de un workflow y retorna un grafo de ejecución.

        Args:
            workflow: Definición del workflow

        Returns:
            ExecutionGraph: Grafo optimizado para ejecución
        """
        # Usar caché si está disponible
        cache_key = f"{workflow.id}_{workflow.version}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Crear nuevo grafo de ejecución
        execution_graph = ExecutionGraph(workflow)

        # Validar el flujo
        issues = execution_graph.validate_execution_flow()
        if issues:
            raise ValueError(f"Invalid workflow dependencies: {'; '.join(issues)}")

        # Guardar en caché
        self.cache[cache_key] = execution_graph

        return execution_graph

    def optimize_execution_order(
        self,
        workflow: WorkflowDefinition,
        constraints: Optional[Dict[str, Any]] = None
    ) -> ExecutionGraph:
        """
        Optimiza el orden de ejecución considerando restricciones adicionales.

        Args:
            workflow: Definición del workflow
            constraints: Restricciones adicionales (ej: recursos limitados)

        Returns:
            ExecutionGraph: Grafo optimizado
        """
        # Por ahora, usar resolución básica
        # En el futuro, esto podría considerar:
        # - Restricciones de recursos
        # - Prioridades de pasos
        # - Costos de ejecución
        # - Disponibilidad de agentes

        return self.resolve_dependencies(workflow)

    def analyze_bottlenecks(self, workflow: WorkflowDefinition) -> Dict[str, Any]:
        """
        Analiza posibles cuellos de botella en el workflow.

        Returns:
            Análisis de rendimiento y sugerencias de optimización
        """
        execution_graph = self.resolve_dependencies(workflow)

        critical_path = execution_graph.get_critical_path()
        parallel_opportunities = execution_graph.get_parallel_execution_opportunities()

        # Identificar pasos con muchas dependencias
        high_dependency_steps = []
        for step in workflow.steps:
            dependencies = execution_graph.get_step_dependencies(step.id)
            if len(dependencies) > 3:  # Umbral arbitrario
                high_dependency_steps.append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "dependency_count": len(dependencies)
                })

        # Identificar pasos que bloquean muchos otros
        blocking_steps = []
        for step in workflow.steps:
            dependents = execution_graph.get_step_dependents(step.id)
            if len(dependents) > 3:  # Umbral arbitrario
                blocking_steps.append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "blocks_count": len(dependents)
                })

        return {
            "critical_path": critical_path,
            "critical_path_length": len(critical_path),
            "parallel_opportunities": len(parallel_opportunities),
            "total_parallel_steps": sum(len(group) for group in parallel_opportunities),
            "high_dependency_steps": high_dependency_steps,
            "blocking_steps": blocking_steps,
            "estimated_duration": execution_graph.estimate_execution_time(),
            "optimization_suggestions": self._generate_optimization_suggestions(
                execution_graph, critical_path, parallel_opportunities
            )
        }

    def _generate_optimization_suggestions(
        self,
        execution_graph: ExecutionGraph,
        critical_path: List[str],
        parallel_opportunities: List[Set[str]]
    ) -> List[str]:
        """Genera sugerencias de optimización"""
        suggestions = []

        if len(critical_path) > 10:
            suggestions.append("Consider breaking down the critical path into smaller, parallel steps")

        if len(parallel_opportunities) < len(execution_graph.workflow.steps) / 4:
            suggestions.append("Look for opportunities to parallelize more steps")

        # Sugerir optimizaciones específicas por tipo de paso
        for step in execution_graph.workflow.steps:
            if step.type.value == "agent_task" and step.id in critical_path:
                suggestions.append(f"Consider optimizing agent task '{step.name}' as it's on the critical path")

        if not suggestions:
            suggestions.append("Workflow appears well-optimized for parallel execution")

        return suggestions

    def clear_cache(self):
        """Limpia la caché de grafos de ejecución"""
        self.cache.clear()