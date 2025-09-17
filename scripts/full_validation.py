#!/usr/bin/env python3
"""
AgentOS MVP - Script de Validación Integral Completa
Valida todas las funcionalidades implementadas en las 6 fases
"""

import asyncio
import time
import sys
import os
from typing import Dict, List, Tuple
from datetime import datetime
import httpx
import json
from colorama import Fore, Style, init
import pandas as pd
from tabulate import tabulate

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

init(autoreset=True)

class MVPValidator:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": [],
            "metrics": {}
        }
        self.test_user = None
        self.test_org = None
        self.auth_token = None
        self.agent_id = None

    async def run_full_validation(self):
        """Ejecutar validación completa del MVP"""
        print(f"\n{Fore.CYAN}═══════════════════════════════════════════════════════")
        print(f"{Fore.CYAN}     AgentOS MVP - VALIDACIÓN INTEGRAL COMPLETA")
        print(f"{Fore.CYAN}═══════════════════════════════════════════════════════\n")

        start_time = time.time()

        # 1. Validaciones de infraestructura
        print(f"\n{Fore.YELLOW}▶ FASE 1: Validando Infraestructura...")
        await self.validate_infrastructure()

        # 2. Validación del Core
        print(f"\n{Fore.YELLOW}▶ FASE 2: Validando Core Features...")
        await self.validate_core_features()

        # 3. Validación de Subagentes
        print(f"\n{Fore.YELLOW}▶ FASE 3: Validando Subagentes...")
        await self.validate_subagents()

        # 4. Validación de Orquestación
        print(f"\n{Fore.YELLOW}▶ FASE 4: Validando Sistema de Orquestación...")
        await self.validate_orchestration()

        # 5. Validación del Builder
        print(f"\n{Fore.YELLOW}▶ FASE 5: Validando Workflow Builder...")
        await self.validate_workflow_builder()

        # 6. Validación del Marketplace
        print(f"\n{Fore.YELLOW}▶ FASE 6: Validando Marketplace...")
        await self.validate_marketplace()

        # 7. Métricas de Performance
        print(f"\n{Fore.YELLOW}▶ FASE 7: Midiendo Performance...")
        await self.measure_performance()

        # 8. Test de Carga
        print(f"\n{Fore.YELLOW}▶ FASE 8: Ejecutando Test de Carga...")
        await self.load_testing()

        total_time = time.time() - start_time

        # Generar reporte
        await self.generate_report(total_time)

        return self.results

    async def validate_infrastructure(self):
        """Validar que todos los servicios están funcionando"""

        services = {
            "API": f"{self.base_url}/health",
            "Database": f"{self.base_url}/api/v1/health/db",
            "Redis": f"{self.base_url}/api/v1/health/redis",
            "Authentication": f"{self.base_url}/api/v1/auth/status",
        }

        for service_name, endpoint in services.items():
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(endpoint, timeout=5.0)

                if response.status_code == 200:
                    self._log_success(f"✓ {service_name} está operativo")
                    self.results["passed"].append(f"{service_name} health check")
                else:
                    self._log_error(f"✗ {service_name} respondió con status {response.status_code}")
                    self.results["failed"].append(f"{service_name} health check")

            except Exception as e:
                self._log_error(f"✗ {service_name} no responde: {str(e)}")
                self.results["failed"].append(f"{service_name} connection")

    async def validate_core_features(self):
        """Validar funcionalidades core del MVP"""

        # 1. Registro de usuario
        user_data = {
            "email": f"test_{int(time.time())}@agentos.ai",
            "password": "Test123!@#",
            "organization_name": "Test PyME",
            "industry": "technology",
            "role": "admin"
        }

        async with httpx.AsyncClient() as client:
            # Registro
            response = await client.post(
                f"{self.base_url}/api/v1/auth/register",
                json=user_data
            )

            if response.status_code == 201:
                self._log_success("✓ Registro de usuario exitoso")
                self.results["passed"].append("User registration")
                data = response.json()
                self.auth_token = data.get("token") or data.get("access_token")
                self.test_user = data.get("user")

                # Medir tiempo de registro
                self.results["metrics"]["registration_time"] = response.elapsed.total_seconds()
            else:
                self._log_error(f"✗ Fallo en registro: {response.status_code}")
                self.results["failed"].append("User registration")
                return

            # 2. Login
            headers = {"Authorization": f"Bearer {self.auth_token}"}

            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }

            response = await client.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data
            )

            if response.status_code == 200:
                self._log_success("✓ Login exitoso")
                self.results["passed"].append("User login")
            else:
                self._log_error(f"✗ Fallo en login: {response.status_code}")
                self.results["failed"].append("User login")

            # 3. Onboarding - Business Context
            business_context = {
                "business_name": "Test Store",
                "industry": "ecommerce",
                "products": ["Electronics", "Gadgets"],
                "target_audience": "Tech enthusiasts 25-45",
                "brand_tone": "Professional, friendly",
                "brand_guidelines": "Use technical terms, be helpful"
            }

            response = await client.post(
                f"{self.base_url}/api/v1/onboarding/business-context",
                json=business_context,
                headers=headers
            )

            if response.status_code == 200:
                self._log_success("✓ Business context configurado")
                self.results["passed"].append("Business context setup")
                if response.json().get("organization"):
                    self.test_org = response.json()["organization"]
            else:
                self._log_error(f"✗ Fallo en business context: {response.status_code}")
                self.results["failed"].append("Business context setup")

            # 4. Subir documentos
            test_content = b"This is a test document for AgentOS validation. It contains business information about our company."
            files = {"file": ("test.txt", test_content, "text/plain")}

            response = await client.post(
                f"{self.base_url}/api/v1/onboarding/documents",
                files=files,
                headers=headers
            )

            if response.status_code == 200:
                self._log_success("✓ Upload de documentos funcional")
                self.results["passed"].append("Document upload")
            else:
                self._log_error(f"✗ Fallo en upload: {response.status_code}")
                self.results["failed"].append("Document upload")

            # 5. Entrenar Agente Principal
            start_training = time.time()
            response = await client.post(
                f"{self.base_url}/api/v1/agents/train-principal",
                json={"auto_train": True},
                headers=headers
            )

            if response.status_code == 200:
                agent_data = response.json()
                self.agent_id = agent_data.get("agent_id") or agent_data.get("id")

                # Esperar entrenamiento (simulado)
                training_time = time.time() - start_training
                self.results["metrics"]["agent_training_time"] = training_time

                self._log_success(f"✓ Agente Principal entrenado en {training_time:.2f}s")
                self.results["passed"].append("Principal agent training")
            else:
                self._log_error(f"✗ Fallo en entrenamiento: {response.status_code}")
                self.results["failed"].append("Principal agent training")

            # 6. Test de chat con contexto
            if self.agent_id:
                chat_start = time.time()
                response = await client.post(
                    f"{self.base_url}/api/v1/agents/{self.agent_id}/chat",
                    json={"message": "What products do we sell?", "include_context": True},
                    headers=headers
                )

                if response.status_code == 200:
                    chat_response = response.json().get("response", "")
                    response_time = time.time() - chat_start
                    self.results["metrics"]["chat_response_time"] = response_time

                    # Verificar que menciona los productos
                    if "electronics" in chat_response.lower() or "gadgets" in chat_response.lower():
                        self._log_success(f"✓ Chat con contexto funcional ({response_time:.2f}s)")
                        self.results["passed"].append("Contextual chat")
                    else:
                        self._log_warning("⚠ Respuesta sin contexto del negocio")
                        self.results["warnings"].append("Chat context accuracy")
                else:
                    self._log_error(f"✗ Fallo en chat: {response.status_code}")
                    self.results["failed"].append("Contextual chat")

    async def validate_subagents(self):
        """Validar cada uno de los 5 subagentes"""

        if not self.auth_token:
            self._log_warning("⚠ Saltando validación de subagentes (sin auth)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        subagent_tests = [
            {
                "name": "Productivity Agent",
                "endpoint": "/api/v1/agents/specialized/productivity/execute",
                "payload": {
                    "task": "schedule_meeting",
                    "context": {
                        "meeting_type": "team_standup",
                        "duration": 30
                    }
                }
            },
            {
                "name": "Data Analysis Agent",
                "endpoint": "/api/v1/agents/specialized/data_analysis/execute",
                "payload": {
                    "task": "generate_insights",
                    "context": {
                        "data": [
                            {"date": "2024-01-01", "sales": 100},
                            {"date": "2024-01-02", "sales": 150}
                        ]
                    }
                }
            },
            {
                "name": "Customer Service Agent",
                "endpoint": "/api/v1/agents/specialized/customer_service/execute",
                "payload": {
                    "task": "classify_inquiry",
                    "context": {
                        "message": "I need help with my order"
                    }
                }
            },
            {
                "name": "Marketing Agent",
                "endpoint": "/api/v1/agents/specialized/marketing/execute",
                "payload": {
                    "task": "generate_content",
                    "context": {
                        "platform": "social",
                        "topic": "new product launch"
                    }
                }
            },
            {
                "name": "Project Management Agent",
                "endpoint": "/api/v1/agents/specialized/project_management/execute",
                "payload": {
                    "task": "create_timeline",
                    "context": {
                        "project": "Website redesign",
                        "duration_weeks": 8
                    }
                }
            }
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            for test in subagent_tests:
                try:
                    start = time.time()
                    response = await client.post(
                        f"{self.base_url}{test['endpoint']}",
                        json=test['payload'],
                        headers=headers
                    )

                    execution_time = time.time() - start

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success") or result.get("status") == "completed":
                            self._log_success(f"✓ {test['name']} funcional ({execution_time:.2f}s)")
                            self.results["passed"].append(f"{test['name']}")
                            self.results["metrics"][f"{test['name'].lower().replace(' ', '_')}_time"] = execution_time
                        else:
                            self._log_error(f"✗ {test['name']} falló: {result.get('error', 'Unknown error')}")
                            self.results["failed"].append(f"{test['name']}")
                    else:
                        self._log_error(f"✗ {test['name']} error: {response.status_code}")
                        self.results["failed"].append(f"{test['name']}")

                except Exception as e:
                    self._log_error(f"✗ {test['name']} exception: {str(e)}")
                    self.results["failed"].append(f"{test['name']}")

    async def validate_orchestration(self):
        """Validar sistema de orquestación Principal-Subagentes"""

        if not self.auth_token:
            self._log_warning("⚠ Saltando validación de orquestación (sin auth)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Test de orquestación compleja
        complex_request = {
            "request": "Create a social media post about our new product launch, analyze the best posting time, and schedule it",
            "context": {
                "require_research": True,
                "schedule_post": True,
                "analyze_best_time": True
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            start = time.time()
            response = await client.post(
                f"{self.base_url}/api/v1/orchestrator/process",
                json=complex_request,
                headers=headers
            )

            orchestration_time = time.time() - start

            if response.status_code == 200:
                result = response.json()
                agents_used = result.get("agents_used", [])

                if len(agents_used) >= 2:
                    self._log_success(f"✓ Orquestación multi-agente exitosa ({len(agents_used)} agentes, {orchestration_time:.2f}s)")
                    self.results["passed"].append("Multi-agent orchestration")
                    self.results["metrics"]["orchestration_time"] = orchestration_time
                    self.results["metrics"]["agents_coordinated"] = len(agents_used)
                else:
                    self._log_warning(f"⚠ Orquestación simple (solo {len(agents_used)} agente)")
                    self.results["warnings"].append("Limited orchestration")
            else:
                self._log_error(f"✗ Fallo en orquestación: {response.status_code}")
                self.results["failed"].append("Multi-agent orchestration")

    async def validate_workflow_builder(self):
        """Validar creación y ejecución de workflows"""

        if not self.auth_token:
            self._log_warning("⚠ Saltando validación de workflows (sin auth)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Crear workflow de prueba
        test_workflow = {
            "name": "Test Workflow",
            "description": "Validation test workflow",
            "workflow_definition": {
                "start_step": "1",
                "end_steps": ["3"],
                "steps": [
                    {
                        "id": "1",
                        "name": "Start",
                        "type": "trigger",
                        "config": {"trigger_type": "manual"}
                    },
                    {
                        "id": "2",
                        "name": "Process",
                        "type": "agent_task",
                        "config": {
                            "agent_type": "marketing",
                            "task": "generate_content",
                            "params": {"platform": "twitter", "topic": "test"}
                        }
                    },
                    {
                        "id": "3",
                        "name": "End",
                        "type": "end",
                        "config": {"output_type": "response"}
                    }
                ],
                "connections": [
                    {"from_step": "1", "to_step": "2"},
                    {"from_step": "2", "to_step": "3"}
                ],
                "input_variables": [],
                "output_variables": []
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Crear workflow
            response = await client.post(
                f"{self.base_url}/api/v1/workflows",
                json=test_workflow,
                headers=headers
            )

            if response.status_code == 201:
                workflow_data = response.json()
                workflow_id = workflow_data.get("id")
                self._log_success("✓ Workflow creado exitosamente")
                self.results["passed"].append("Workflow creation")

                # Ejecutar workflow
                if workflow_id:
                    start = time.time()
                    response = await client.post(
                        f"{self.base_url}/api/v1/workflows/{workflow_id}/execute",
                        json={"input": {"test": "data"}},
                        headers=headers
                    )

                    execution_time = time.time() - start

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status") == "completed":
                            self._log_success(f"✓ Workflow ejecutado ({execution_time:.2f}s)")
                            self.results["passed"].append("Workflow execution")
                            self.results["metrics"]["workflow_execution_time"] = execution_time
                        else:
                            self._log_error(f"✗ Workflow falló: {result.get('error')}")
                            self.results["failed"].append("Workflow execution")
                    else:
                        self._log_error(f"✗ Error ejecutando workflow: {response.status_code}")
                        self.results["failed"].append("Workflow execution")
            else:
                self._log_error(f"✗ Error creando workflow: {response.status_code}")
                self.results["failed"].append("Workflow creation")

    async def validate_marketplace(self):
        """Validar funcionalidad del marketplace"""

        if not self.auth_token:
            self._log_warning("⚠ Saltando validación de marketplace (sin auth)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        async with httpx.AsyncClient() as client:
            # Listar templates
            response = await client.get(
                f"{self.base_url}/api/v1/marketplace/templates",
                headers=headers
            )

            if response.status_code == 200:
                templates_data = response.json()
                templates = templates_data.get("templates", templates_data) if isinstance(templates_data, dict) else templates_data

                if isinstance(templates, list) and len(templates) >= 5:
                    self._log_success(f"✓ Marketplace con {len(templates)} templates")
                    self.results["passed"].append("Marketplace templates")
                    self.results["metrics"]["total_templates"] = len(templates)

                    # Intentar instalar un template
                    if templates:
                        template = templates[0]
                        template_id = template.get("id")
                        if template_id:
                            response = await client.post(
                                f"{self.base_url}/api/v1/marketplace/templates/{template_id}/install",
                                json={"installation_type": "standard"},
                                headers=headers
                            )

                            if response.status_code == 200:
                                self._log_success("✓ Instalación de template exitosa")
                                self.results["passed"].append("Template installation")
                            else:
                                self._log_error(f"✗ Error instalando template: {response.status_code}")
                                self.results["failed"].append("Template installation")
                else:
                    template_count = len(templates) if isinstance(templates, list) else 0
                    self._log_warning(f"⚠ Solo {template_count} templates en marketplace")
                    self.results["warnings"].append("Limited templates")
            else:
                self._log_error(f"✗ Error accediendo marketplace: {response.status_code}")
                self.results["failed"].append("Marketplace access")

    async def measure_performance(self):
        """Medir métricas de performance clave"""

        if not self.auth_token:
            self._log_warning("⚠ Saltando medición de performance (sin auth)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        performance_tests = [
            {
                "name": "Simple chat response",
                "endpoint": f"/api/v1/agents/{self.agent_id or 'test'}/chat",
                "payload": {"message": "Hello"},
                "target_ms": 2000
            },
            {
                "name": "Agent execution",
                "endpoint": "/api/v1/agents/specialized/productivity/execute",
                "payload": {"task": "simple_task", "context": {}},
                "target_ms": 3000
            }
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            for test in performance_tests:
                try:
                    times = []
                    for _ in range(3):  # 3 iteraciones para promedio
                        start = time.time()
                        response = await client.post(
                            f"{self.base_url}{test['endpoint']}",
                            json=test['payload'],
                            headers=headers
                        )
                        elapsed = (time.time() - start) * 1000  # ms
                        times.append(elapsed)

                        if response.status_code != 200:
                            break

                    if times:
                        avg_time = sum(times) / len(times)

                        if avg_time <= test['target_ms']:
                            self._log_success(f"✓ {test['name']}: {avg_time:.0f}ms (target: {test['target_ms']}ms)")
                            self.results["passed"].append(f"Performance: {test['name']}")
                        else:
                            self._log_warning(f"⚠ {test['name']}: {avg_time:.0f}ms (target: {test['target_ms']}ms)")
                            self.results["warnings"].append(f"Performance: {test['name']}")

                        self.results["metrics"][f"perf_{test['name'].replace(' ', '_')}"] = avg_time

                except Exception as e:
                    self._log_error(f"✗ Error en test de performance {test['name']}: {str(e)}")
                    self.results["failed"].append(f"Performance: {test['name']}")

    async def load_testing(self):
        """Test de carga básico"""

        if not self.auth_token:
            self._log_warning("⚠ Saltando test de carga (sin auth)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}
        concurrent_users = 5  # Reducido para testing
        requests_per_user = 3

        async def user_simulation(user_id: int):
            """Simular un usuario haciendo requests"""
            results = []
            async with httpx.AsyncClient(timeout=30.0) as client:
                for i in range(requests_per_user):
                    start = time.time()
                    try:
                        response = await client.get(
                            f"{self.base_url}/health",
                            headers=headers
                        )
                        elapsed = time.time() - start
                        results.append({
                            "success": response.status_code == 200,
                            "time": elapsed,
                            "status": response.status_code
                        })
                    except Exception as e:
                        results.append({
                            "success": False,
                            "time": time.time() - start,
                            "error": str(e)
                        })

                    await asyncio.sleep(0.1)  # Pequeña pausa entre requests

            return results

        # Ejecutar usuarios concurrentes
        self._log_info(f"Ejecutando test de carga: {concurrent_users} usuarios, {requests_per_user} requests c/u")
        start = time.time()

        tasks = [user_simulation(i) for i in range(concurrent_users)]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start

        # Analizar resultados
        flat_results = []
        for user_results in all_results:
            if isinstance(user_results, list):
                flat_results.extend(user_results)

        if flat_results:
            successful = sum(1 for r in flat_results if r.get("success"))
            total = len(flat_results)
            success_rate = (successful / total) * 100 if total > 0 else 0

            avg_response_time = sum(r["time"] for r in flat_results) / len(flat_results)

            self.results["metrics"]["load_test_users"] = concurrent_users
            self.results["metrics"]["load_test_total_requests"] = total
            self.results["metrics"]["load_test_success_rate"] = success_rate
            self.results["metrics"]["load_test_avg_response"] = avg_response_time
            self.results["metrics"]["load_test_rps"] = total / total_time if total_time > 0 else 0

            if success_rate >= 95:
                self._log_success(f"✓ Test de carga exitoso: {success_rate:.1f}% success rate, {avg_response_time:.2f}s avg")
                self.results["passed"].append("Load testing")
            elif success_rate >= 80:
                self._log_warning(f"⚠ Test de carga parcial: {success_rate:.1f}% success rate")
                self.results["warnings"].append("Load testing")
            else:
                self._log_error(f"✗ Test de carga falló: {success_rate:.1f}% success rate")
                self.results["failed"].append("Load testing")
        else:
            self._log_error("✗ Test de carga falló: no se obtuvieron resultados")
            self.results["failed"].append("Load testing")

    async def generate_report(self, total_time: float):
        """Generar reporte final de validación"""

        print(f"\n{Fore.CYAN}═══════════════════════════════════════════════════════")
        print(f"{Fore.CYAN}                    REPORTE FINAL")
        print(f"{Fore.CYAN}═══════════════════════════════════════════════════════\n")

        # Resumen
        total_tests = len(self.results["passed"]) + len(self.results["failed"])
        pass_rate = (len(self.results["passed"]) / total_tests * 100) if total_tests > 0 else 0

        print(f"{Fore.WHITE}Tiempo total de validación: {total_time:.2f} segundos\n")

        # Estado general
        if pass_rate >= 90:
            status = f"{Fore.GREEN}✓ MVP LISTO PARA PRODUCCIÓN"
            self.results["overall_status"] = "READY"
        elif pass_rate >= 70:
            status = f"{Fore.YELLOW}⚠ MVP REQUIERE AJUSTES"
            self.results["overall_status"] = "NEEDS_WORK"
        else:
            status = f"{Fore.RED}✗ MVP NO ESTÁ LISTO"
            self.results["overall_status"] = "NOT_READY"

        print(f"{status}{Style.RESET_ALL}")
        print(f"\nTasa de éxito: {pass_rate:.1f}%")
        print(f"Tests pasados: {len(self.results['passed'])}/{total_tests}")
        print(f"Warnings: {len(self.results['warnings'])}")

        # Tabla de resultados
        if self.results["failed"]:
            print(f"\n{Fore.RED}Tests Fallidos:")
            for test in self.results["failed"]:
                print(f"  ✗ {test}")

        if self.results["warnings"]:
            print(f"\n{Fore.YELLOW}Warnings:")
            for warning in self.results["warnings"]:
                print(f"  ⚠ {warning}")

        # Métricas de performance
        if self.results["metrics"]:
            print(f"\n{Fore.CYAN}Métricas de Performance:")

            metrics_table = []
            for key, value in self.results["metrics"].items():
                if isinstance(value, float):
                    if "time" in key:
                        metrics_table.append([key.replace("_", " ").title(), f"{value:.2f}s"])
                    elif "rate" in key or "percent" in key:
                        metrics_table.append([key.replace("_", " ").title(), f"{value:.1f}%"])
                    else:
                        metrics_table.append([key.replace("_", " ").title(), f"{value:.2f}"])
                else:
                    metrics_table.append([key.replace("_", " ").title(), str(value)])

            if metrics_table:
                try:
                    print(tabulate(metrics_table, headers=["Métrica", "Valor"], tablefmt="grid"))
                except:
                    # Fallback sin tabulate
                    for metric, value in metrics_table:
                        print(f"  {metric}: {value}")

        # Guardar reporte en archivo
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_time": total_time,
            "overall_status": self.results.get("overall_status"),
            "pass_rate": pass_rate,
            "results": self.results
        }

        try:
            with open("validation_report.json", "w") as f:
                json.dump(report_data, f, indent=2)
            print(f"\n{Fore.GREEN}Reporte guardado en validation_report.json")
        except:
            print(f"\n{Fore.YELLOW}No se pudo guardar el reporte en archivo")

        # Recomendaciones
        print(f"\n{Fore.CYAN}Recomendaciones:")
        if pass_rate < 100:
            if "Load testing" in self.results["failed"] or "Load testing" in self.results["warnings"]:
                print("  • Optimizar performance para manejar más carga")
            if any("agent" in f.lower() for f in self.results["failed"]):
                print("  • Revisar configuración de subagentes")
            if "Multi-agent orchestration" in self.results["failed"]:
                print("  • Mejorar coordinación entre agentes")
            if any(m > 3000 for k, m in self.results["metrics"].items() if "time" in k and isinstance(m, (int, float))):
                print("  • Implementar caching para reducir tiempos de respuesta")
        else:
            print("  • ¡Excelente! El MVP está listo para producción")

    def _log_success(self, message: str):
        print(f"{Fore.GREEN}{message}")

    def _log_error(self, message: str):
        print(f"{Fore.RED}{message}")

    def _log_warning(self, message: str):
        print(f"{Fore.YELLOW}{message}")

    def _log_info(self, message: str):
        print(f"{Fore.CYAN}{message}")


# Ejecutar validación
async def main():
    validator = MVPValidator()

    try:
        results = await validator.run_full_validation()

        # Retornar código de salida basado en resultado
        if results.get("overall_status") == "READY":
            sys.exit(0)
        elif results.get("overall_status") == "NEEDS_WORK":
            sys.exit(1)
        else:
            sys.exit(2)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Validación interrumpida por el usuario")
        sys.exit(3)
    except Exception as e:
        print(f"\n{Fore.RED}Error inesperado durante la validación: {str(e)}")
        sys.exit(4)

if __name__ == "__main__":
    asyncio.run(main())