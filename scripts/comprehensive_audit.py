#!/usr/bin/env python3
"""
Comprehensive Security and Performance Audit for AgentOS
Automated audit script that checks for security vulnerabilities, performance issues, and code quality problems
"""

import os
import sys
import json
import subprocess
import ast
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import importlib.util
import inspect
from dataclasses import dataclass, field
from enum import Enum

class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class Category(Enum):
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    ARCHITECTURE = "ARCHITECTURE"
    CODE_QUALITY = "CODE_QUALITY"
    TESTING = "TESTING"
    CONFIGURATION = "CONFIGURATION"

@dataclass
class AuditFinding:
    severity: Severity
    category: Category
    title: str
    description: str
    file_path: str
    line_number: int = 0
    code_snippet: str = ""
    recommendation: str = ""
    cwe_id: str = ""  # Common Weakness Enumeration ID
    risk_score: int = 0  # 1-10 scale

@dataclass
class AuditReport:
    timestamp: datetime
    total_files_scanned: int
    findings: List[AuditFinding] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)

class SecurityAuditor:
    """Automated security vulnerability scanner"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.findings = []

        # Security patterns to detect
        self.security_patterns = {
            'hardcoded_secrets': [
                r'password\s*=\s*["\'][^"\']*["\']',
                r'secret[_-]?key\s*=\s*["\'][^"\']*["\']',
                r'api[_-]?key\s*=\s*["\'][^"\']*["\']',
                r'token\s*=\s*["\'][^"\']*["\']',
                r'["\']sk_[a-zA-Z0-9]{24,}["\']',  # Stripe secret keys
                r'["\']AIza[0-9A-Za-z-_]{35}["\']',  # Google API keys
            ],
            'sql_injection': [
                r'execute\s*\(\s*[f]?["\'][^"\']*\+.*["\']',
                r'\.format\s*\(.*\)\s*\)',
                r'%s.*%.*execute',
                r'text\s*\([f]?["\'][^"\']*\{.*\}[^"\']*["\']',
            ],
            'xss_vulnerabilities': [
                r'\.innerHTML\s*=',
                r'document\.write\s*\(',
                r'eval\s*\(',
                r'exec\s*\(',
                r'render_template_string\s*\(',
            ],
            'path_traversal': [
                r'open\s*\([^)]*\.\.[^)]*\)',
                r'file\s*\([^)]*\.\.[^)]*\)',
                r'os\.path\.join\s*\([^)]*\.\.[^)]*\)',
            ],
            'weak_crypto': [
                r'md5\s*\(',
                r'sha1\s*\(',
                r'DES\s*\(',
                r'random\.random\s*\(',
                r'random\.randint\s*\(',
            ],
            'insecure_transport': [
                r'http://[^"\'\s]*',
                r'verify\s*=\s*False',
                r'ssl\._create_unverified_context',
            ]
        }

    def scan_file(self, file_path: Path) -> List[AuditFinding]:
        """Scan a single file for security vulnerabilities"""
        findings = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')

            # Check for security patterns
            for pattern_category, patterns in self.security_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1

                        # Get severity based on pattern type
                        severity = self._get_severity_for_pattern(pattern_category)

                        finding = AuditFinding(
                            severity=severity,
                            category=Category.SECURITY,
                            title=f"{pattern_category.replace('_', ' ').title()} Detected",
                            description=f"Potential {pattern_category} vulnerability found",
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_number=line_num,
                            code_snippet=lines[line_num-1].strip() if line_num <= len(lines) else "",
                            recommendation=self._get_recommendation_for_pattern(pattern_category),
                            cwe_id=self._get_cwe_for_pattern(pattern_category),
                            risk_score=self._get_risk_score_for_pattern(pattern_category, severity)
                        )
                        findings.append(finding)

            # Check for specific Python security issues
            if file_path.suffix == '.py':
                findings.extend(self._check_python_security(file_path, content, lines))

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

        return findings

    def _check_python_security(self, file_path: Path, content: str, lines: List[str]) -> List[AuditFinding]:
        """Check Python-specific security issues"""
        findings = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                # Check for eval/exec usage
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec']:
                        findings.append(AuditFinding(
                            severity=Severity.CRITICAL,
                            category=Category.SECURITY,
                            title="Code Injection Risk",
                            description="Use of eval() or exec() can lead to code injection",
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_number=node.lineno,
                            code_snippet=lines[node.lineno-1].strip(),
                            recommendation="Replace eval/exec with safer alternatives",
                            cwe_id="CWE-94",
                            risk_score=9
                        ))

                # Check for subprocess with shell=True
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['call', 'run', 'Popen']:
                        for keyword in node.keywords:
                            if keyword.arg == 'shell' and isinstance(keyword.value, ast.Constant):
                                if keyword.value.value is True:
                                    findings.append(AuditFinding(
                                        severity=Severity.HIGH,
                                        category=Category.SECURITY,
                                        title="Command Injection Risk",
                                        description="subprocess with shell=True can lead to command injection",
                                        file_path=str(file_path.relative_to(self.project_root)),
                                        line_number=node.lineno,
                                        code_snippet=lines[node.lineno-1].strip(),
                                        recommendation="Use shell=False or validate input thoroughly",
                                        cwe_id="CWE-78",
                                        risk_score=8
                                    ))

        except SyntaxError:
            # File has syntax errors, skip AST analysis
            pass

        return findings

    def _get_severity_for_pattern(self, pattern_category: str) -> Severity:
        """Get severity level for pattern category"""
        severity_map = {
            'hardcoded_secrets': Severity.CRITICAL,
            'sql_injection': Severity.CRITICAL,
            'xss_vulnerabilities': Severity.HIGH,
            'path_traversal': Severity.HIGH,
            'weak_crypto': Severity.MEDIUM,
            'insecure_transport': Severity.MEDIUM
        }
        return severity_map.get(pattern_category, Severity.LOW)

    def _get_recommendation_for_pattern(self, pattern_category: str) -> str:
        """Get recommendation for pattern category"""
        recommendations = {
            'hardcoded_secrets': "Store secrets in environment variables or secure vault",
            'sql_injection': "Use parameterized queries or ORM with proper sanitization",
            'xss_vulnerabilities': "Sanitize all user input and use template escaping",
            'path_traversal': "Validate and sanitize file paths, use absolute paths",
            'weak_crypto': "Use strong cryptographic algorithms (SHA-256, AES-256)",
            'insecure_transport': "Use HTTPS/TLS for all communications"
        }
        return recommendations.get(pattern_category, "Review and fix the identified issue")

    def _get_cwe_for_pattern(self, pattern_category: str) -> str:
        """Get CWE ID for pattern category"""
        cwe_map = {
            'hardcoded_secrets': "CWE-798",
            'sql_injection': "CWE-89",
            'xss_vulnerabilities': "CWE-79",
            'path_traversal': "CWE-22",
            'weak_crypto': "CWE-327",
            'insecure_transport': "CWE-319"
        }
        return cwe_map.get(pattern_category, "")

    def _get_risk_score_for_pattern(self, pattern_category: str, severity: Severity) -> int:
        """Get risk score (1-10) for pattern"""
        base_scores = {
            'hardcoded_secrets': 9,
            'sql_injection': 10,
            'xss_vulnerabilities': 7,
            'path_traversal': 8,
            'weak_crypto': 6,
            'insecure_transport': 5
        }
        return base_scores.get(pattern_category, 3)

class PerformanceAuditor:
    """Performance issue detector"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

        # Performance anti-patterns
        self.performance_patterns = {
            'n_plus_one_queries': [
                r'for.*in.*:\s*.*\.get\(',
                r'for.*in.*:\s*.*\.filter\(',
                r'for.*in.*:\s*.*\.query\(',
            ],
            'blocking_operations': [
                r'time\.sleep\(',
                r'requests\.get\(',
                r'requests\.post\(',
                r'urllib\.request\.',
            ],
            'memory_leaks': [
                r'global\s+[a-zA-Z_].*=.*\[\]',
                r'cache\s*=\s*\{\}',
                r'\.append\(.*\)\s*$',
            ],
            'inefficient_loops': [
                r'for.*in.*:\s*.*\.append\(',
                r'while.*True:',
                r'for.*range\(len\(',
            ]
        }

    def scan_file(self, file_path: Path) -> List[AuditFinding]:
        """Scan file for performance issues"""
        findings = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')

            for pattern_category, patterns in self.performance_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1

                        finding = AuditFinding(
                            severity=Severity.MEDIUM,
                            category=Category.PERFORMANCE,
                            title=f"{pattern_category.replace('_', ' ').title()} Detected",
                            description=f"Potential {pattern_category} performance issue",
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_number=line_num,
                            code_snippet=lines[line_num-1].strip(),
                            recommendation=self._get_performance_recommendation(pattern_category),
                            risk_score=self._get_performance_risk_score(pattern_category)
                        )
                        findings.append(finding)

        except Exception as e:
            print(f"Error scanning {file_path} for performance: {e}")

        return findings

    def _get_performance_recommendation(self, pattern_category: str) -> str:
        """Get performance recommendation"""
        recommendations = {
            'n_plus_one_queries': "Use eager loading or batch queries",
            'blocking_operations': "Use async/await for I/O operations",
            'memory_leaks': "Implement proper cleanup and use weak references",
            'inefficient_loops': "Use list comprehensions or optimize loop logic"
        }
        return recommendations.get(pattern_category, "Optimize this code section")

    def _get_performance_risk_score(self, pattern_category: str) -> int:
        """Get performance risk score"""
        scores = {
            'n_plus_one_queries': 8,
            'blocking_operations': 6,
            'memory_leaks': 7,
            'inefficient_loops': 4
        }
        return scores.get(pattern_category, 3)

class ArchitectureAuditor:
    """Architecture and design pattern analyzer"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    def analyze_coupling(self) -> List[AuditFinding]:
        """Analyze coupling between modules"""
        findings = []
        import_graph = {}

        # Build import graph
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                imports = re.findall(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', content, re.MULTILINE)
                module_name = str(py_file.relative_to(self.project_root)).replace('/', '.').replace('.py', '')
                import_graph[module_name] = imports

            except Exception:
                continue

        # Analyze circular dependencies
        for module, imports in import_graph.items():
            for imp in imports:
                if imp[0] and imp[0].startswith('app.'):  # Internal import
                    # Check for potential circular dependency
                    if module in str(imp):
                        findings.append(AuditFinding(
                            severity=Severity.MEDIUM,
                            category=Category.ARCHITECTURE,
                            title="Potential Circular Dependency",
                            description=f"Module {module} may have circular dependency with {imp[0]}",
                            file_path=module.replace('.', '/') + '.py',
                            recommendation="Refactor to remove circular dependencies",
                            risk_score=5
                        ))

        return findings

    def analyze_error_handling(self) -> List[AuditFinding]:
        """Analyze error handling patterns"""
        findings = []

        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')

                # Check for bare except clauses
                bare_except_pattern = r'except\s*:'
                matches = re.finditer(bare_except_pattern, content, re.MULTILINE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    findings.append(AuditFinding(
                        severity=Severity.MEDIUM,
                        category=Category.CODE_QUALITY,
                        title="Bare Except Clause",
                        description="Bare except clauses can hide bugs",
                        file_path=str(py_file.relative_to(self.project_root)),
                        line_number=line_num,
                        code_snippet=lines[line_num-1].strip(),
                        recommendation="Specify exception types or use 'except Exception'",
                        risk_score=4
                    ))

            except Exception:
                continue

        return findings

class ConfigurationAuditor:
    """Configuration and deployment auditor"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    def audit_configuration(self) -> List[AuditFinding]:
        """Audit configuration files"""
        findings = []

        # Check for sensitive files
        sensitive_files = ['.env', 'config.py', 'settings.py', 'secrets.json']

        for file_name in sensitive_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                # Check if file contains default/example values
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    if 'your-secret-key' in content.lower() or 'change-me' in content.lower():
                        findings.append(AuditFinding(
                            severity=Severity.CRITICAL,
                            category=Category.CONFIGURATION,
                            title="Default Configuration Values",
                            description="Configuration file contains default/example values",
                            file_path=str(file_path.relative_to(self.project_root)),
                            recommendation="Replace all default values with secure configurations",
                            cwe_id="CWE-798",
                            risk_score=9
                        ))

                except Exception:
                    continue

        return findings

class ComprehensiveAuditor:
    """Main auditor class that coordinates all audit types"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.security_auditor = SecurityAuditor(project_root)
        self.performance_auditor = PerformanceAuditor(project_root)
        self.architecture_auditor = ArchitectureAuditor(project_root)
        self.config_auditor = ConfigurationAuditor(project_root)

    def run_full_audit(self) -> AuditReport:
        """Run comprehensive audit"""
        print("🔍 Starting comprehensive security and performance audit...")

        report = AuditReport(
            timestamp=datetime.now(),
            total_files_scanned=0
        )

        # Scan all Python files
        python_files = list(self.project_root.rglob("*.py"))
        report.total_files_scanned = len(python_files)

        print(f"📁 Scanning {len(python_files)} Python files...")

        for i, py_file in enumerate(python_files):
            if i % 10 == 0:
                print(f"   Progress: {i}/{len(python_files)} files")

            # Security scan
            security_findings = self.security_auditor.scan_file(py_file)
            report.findings.extend(security_findings)

            # Performance scan
            performance_findings = self.performance_auditor.scan_file(py_file)
            report.findings.extend(performance_findings)

        # Architecture analysis
        print("🏗️  Analyzing architecture...")
        arch_findings = self.architecture_auditor.analyze_coupling()
        arch_findings.extend(self.architecture_auditor.analyze_error_handling())
        report.findings.extend(arch_findings)

        # Configuration audit
        print("⚙️  Auditing configuration...")
        config_findings = self.config_auditor.audit_configuration()
        report.findings.extend(config_findings)

        # Generate summary
        report.summary = self._generate_summary(report.findings)
        report.metrics = self._calculate_metrics(report.findings)

        print(f"✅ Audit complete! Found {len(report.findings)} issues.")

        return report

    def _generate_summary(self, findings: List[AuditFinding]) -> Dict[str, Any]:
        """Generate audit summary"""
        summary = {
            'total_findings': len(findings),
            'by_severity': {},
            'by_category': {},
            'critical_issues': [],
            'high_risk_files': []
        }

        # Count by severity
        for severity in Severity:
            count = len([f for f in findings if f.severity == severity])
            summary['by_severity'][severity.value] = count

        # Count by category
        for category in Category:
            count = len([f for f in findings if f.category == category])
            summary['by_category'][category.value] = count

        # Get critical issues
        critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
        summary['critical_issues'] = [
            {
                'title': f.title,
                'file': f.file_path,
                'line': f.line_number,
                'risk_score': f.risk_score
            }
            for f in critical_findings[:10]  # Top 10
        ]

        # Get high-risk files
        file_risk_scores = {}
        for finding in findings:
            if finding.file_path not in file_risk_scores:
                file_risk_scores[finding.file_path] = 0
            file_risk_scores[finding.file_path] += finding.risk_score

        high_risk_files = sorted(file_risk_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        summary['high_risk_files'] = [
            {'file': file_path, 'risk_score': score}
            for file_path, score in high_risk_files
        ]

        return summary

    def _calculate_metrics(self, findings: List[AuditFinding]) -> Dict[str, Any]:
        """Calculate audit metrics"""
        if not findings:
            return {}

        total_risk_score = sum(f.risk_score for f in findings)
        avg_risk_score = total_risk_score / len(findings)

        return {
            'total_risk_score': total_risk_score,
            'average_risk_score': round(avg_risk_score, 2),
            'security_score': self._calculate_security_score(findings),
            'code_quality_score': self._calculate_quality_score(findings)
        }

    def _calculate_security_score(self, findings: List[AuditFinding]) -> int:
        """Calculate security score (0-100, higher is better)"""
        security_findings = [f for f in findings if f.category == Category.SECURITY]

        if not security_findings:
            return 100

        # Penalty based on severity
        penalty = 0
        for finding in security_findings:
            if finding.severity == Severity.CRITICAL:
                penalty += 20
            elif finding.severity == Severity.HIGH:
                penalty += 10
            elif finding.severity == Severity.MEDIUM:
                penalty += 5
            else:
                penalty += 1

        return max(0, 100 - penalty)

    def _calculate_quality_score(self, findings: List[AuditFinding]) -> int:
        """Calculate code quality score (0-100, higher is better)"""
        quality_findings = [f for f in findings if f.category in [Category.CODE_QUALITY, Category.PERFORMANCE]]

        if not quality_findings:
            return 100

        penalty = len(quality_findings) * 2
        return max(0, 100 - penalty)

def generate_html_report(report: AuditReport, output_path: str):
    """Generate HTML audit report"""

    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>AgentOS Security Audit Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f4f4f4; padding: 20px; border-radius: 5px; }
        .summary { display: flex; gap: 20px; margin: 20px 0; }
        .metric-card { background: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px; flex: 1; }
        .critical { color: #dc3545; }
        .high { color: #fd7e14; }
        .medium { color: #ffc107; }
        .low { color: #6f42c1; }
        .finding { border-left: 4px solid #ddd; padding: 10px; margin: 10px 0; background: #f9f9f9; }
        .finding.critical { border-left-color: #dc3545; }
        .finding.high { border-left-color: #fd7e14; }
        .finding.medium { border-left-color: #ffc107; }
        .finding.low { border-left-color: #6f42c1; }
        .code { background: #f8f9fa; padding: 10px; border-radius: 3px; font-family: monospace; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 AgentOS Security Audit Report</h1>
        <p><strong>Generated:</strong> {timestamp}</p>
        <p><strong>Files Scanned:</strong> {total_files}</p>
        <p><strong>Total Findings:</strong> {total_findings}</p>
    </div>

    <div class="summary">
        <div class="metric-card">
            <h3>Security Score</h3>
            <h2 class="{security_class}">{security_score}/100</h2>
        </div>
        <div class="metric-card">
            <h3>Code Quality</h3>
            <h2>{quality_score}/100</h2>
        </div>
        <div class="metric-card">
            <h3>Total Risk Score</h3>
            <h2>{total_risk_score}</h2>
        </div>
    </div>

    <h2>📊 Findings by Severity</h2>
    <table>
        <tr><th>Severity</th><th>Count</th><th>Percentage</th></tr>
        {severity_table}
    </table>

    <h2>🚨 Critical Issues</h2>
    {critical_issues}

    <h2>📁 High-Risk Files</h2>
    <table>
        <tr><th>File</th><th>Risk Score</th></tr>
        {high_risk_files}
    </table>

    <h2>🔍 All Findings</h2>
    {all_findings}
</body>
</html>
"""

    # Generate severity table
    total_findings = report.summary['total_findings']
    severity_rows = []
    for severity, count in report.summary['by_severity'].items():
        percentage = (count / total_findings * 100) if total_findings > 0 else 0
        severity_rows.append(f'<tr><td class="{severity.lower()}">{severity}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>')

    # Generate critical issues
    critical_html = ""
    for issue in report.summary['critical_issues']:
        critical_html += f"""
        <div class="finding critical">
            <h4>{issue['title']}</h4>
            <p><strong>File:</strong> {issue['file']} <strong>Line:</strong> {issue['line']}</p>
            <p><strong>Risk Score:</strong> {issue['risk_score']}/10</p>
        </div>
        """

    # Generate high-risk files table
    risk_files_rows = []
    for file_info in report.summary['high_risk_files']:
        risk_files_rows.append(f'<tr><td>{file_info["file"]}</td><td>{file_info["risk_score"]}</td></tr>')

    # Generate all findings
    findings_html = ""
    for finding in sorted(report.findings, key=lambda x: x.risk_score, reverse=True)[:50]:  # Top 50
        findings_html += f"""
        <div class="finding {finding.severity.value.lower()}">
            <h4>{finding.title}</h4>
            <p><strong>Severity:</strong> {finding.severity.value} | <strong>Category:</strong> {finding.category.value}</p>
            <p><strong>File:</strong> {finding.file_path} <strong>Line:</strong> {finding.line_number}</p>
            <p>{finding.description}</p>
            {f'<div class="code">{finding.code_snippet}</div>' if finding.code_snippet else ''}
            <p><strong>Recommendation:</strong> {finding.recommendation}</p>
            {f'<p><strong>CWE:</strong> {finding.cwe_id}</p>' if finding.cwe_id else ''}
            <p><strong>Risk Score:</strong> {finding.risk_score}/10</p>
        </div>
        """

    # Security score class
    security_score = report.metrics.get('security_score', 0)
    security_class = 'critical' if security_score < 50 else 'medium' if security_score < 80 else 'high'

    # Fill template
    html_content = html_template.format(
        timestamp=report.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        total_files=report.total_files_scanned,
        total_findings=report.summary['total_findings'],
        security_score=security_score,
        security_class=security_class,
        quality_score=report.metrics.get('code_quality_score', 0),
        total_risk_score=report.metrics.get('total_risk_score', 0),
        severity_table='\n'.join(severity_rows),
        critical_issues=critical_html,
        high_risk_files='\n'.join(risk_files_rows),
        all_findings=findings_html
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"📄 HTML report generated: {output_path}")

def generate_json_report(report: AuditReport, output_path: str):
    """Generate JSON audit report"""

    report_data = {
        'metadata': {
            'timestamp': report.timestamp.isoformat(),
            'total_files_scanned': report.total_files_scanned,
            'audit_version': '1.0'
        },
        'summary': report.summary,
        'metrics': report.metrics,
        'findings': [
            {
                'severity': finding.severity.value,
                'category': finding.category.value,
                'title': finding.title,
                'description': finding.description,
                'file_path': finding.file_path,
                'line_number': finding.line_number,
                'code_snippet': finding.code_snippet,
                'recommendation': finding.recommendation,
                'cwe_id': finding.cwe_id,
                'risk_score': finding.risk_score
            }
            for finding in report.findings
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"📄 JSON report generated: {output_path}")

def main():
    """Main audit function"""
    project_root = Path(__file__).parent.parent

    print("🚀 AgentOS Comprehensive Security Audit")
    print("=" * 50)

    # Run audit
    auditor = ComprehensiveAuditor(str(project_root))
    report = auditor.run_full_audit()

    # Generate reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    html_output = project_root / f"audit_report_{timestamp}.html"
    json_output = project_root / f"audit_report_{timestamp}.json"

    generate_html_report(report, str(html_output))
    generate_json_report(report, str(json_output))

    # Print summary
    print("\n" + "=" * 50)
    print("📊 AUDIT SUMMARY")
    print("=" * 50)
    print(f"🔍 Files Scanned: {report.total_files_scanned}")
    print(f"🚨 Total Findings: {report.summary['total_findings']}")
    print(f"🔴 Critical: {report.summary['by_severity'].get('CRITICAL', 0)}")
    print(f"🟠 High: {report.summary['by_severity'].get('HIGH', 0)}")
    print(f"🟡 Medium: {report.summary['by_severity'].get('MEDIUM', 0)}")
    print(f"🔵 Low: {report.summary['by_severity'].get('LOW', 0)}")
    print(f"🛡️ Security Score: {report.metrics.get('security_score', 0)}/100")
    print(f"📝 Code Quality: {report.metrics.get('code_quality_score', 0)}/100")

    # Recommendations
    critical_count = report.summary['by_severity'].get('CRITICAL', 0)
    high_count = report.summary['by_severity'].get('HIGH', 0)

    print("\n🎯 RECOMMENDATIONS:")
    if critical_count > 0:
        print("❌ DO NOT DEPLOY TO PRODUCTION - Critical security issues found!")
        print("   Fix all critical issues before proceeding.")
    elif high_count > 5:
        print("⚠️  High risk deployment - Multiple high-severity issues found.")
        print("   Consider fixing high-priority issues before production.")
    elif report.metrics.get('security_score', 0) < 70:
        print("⚠️  Security improvements needed before production.")
    else:
        print("✅ Relatively safe for deployment with monitoring.")

    print(f"\n📄 Detailed reports saved:")
    print(f"   HTML: {html_output}")
    print(f"   JSON: {json_output}")

if __name__ == "__main__":
    main()