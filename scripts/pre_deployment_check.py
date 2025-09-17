#!/usr/bin/env python3
"""
Pre-Deployment Validation Script for AgentOS Production
Comprehensive validation of all systems before deployment
"""

import sys
import os
import asyncio
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    import redis
    import boto3
    import requests
    from colorama import Fore, Style, init
    from sqlalchemy import create_engine, text
    from cryptography.fernet import Fernet
    import jwt
    import openai
    from anthropic import Anthropic
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install psycopg2-binary redis boto3 requests colorama sqlalchemy cryptography pyjwt openai anthropic")
    sys.exit(1)

# Initialize colorama for colored output
init(autoreset=True)

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    duration: float = 0.0
    details: Dict = field(default_factory=dict)

class PreDeploymentChecker:
    def __init__(self, env_file: str = ".env.production"):
        self.env_file = env_file
        self.checks_passed = []
        self.checks_failed = []
        self.warnings = []
        self.total_duration = 0.0

        # Load environment variables
        self.load_env_file()

    def load_env_file(self):
        """Load environment variables from file"""
        if not os.path.exists(self.env_file):
            print(f"{Fore.RED}❌ Environment file {self.env_file} not found{Style.RESET_ALL}")
            sys.exit(1)

        with open(self.env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"\'')

    def print_header(self):
        """Print header banner"""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}   AGENTOS - PRE-DEPLOYMENT VALIDATION")
        print(f"{Fore.CYAN}   Environment: {os.getenv('ENVIRONMENT', 'production')}")
        print(f"{Fore.CYAN}   Timestamp: {datetime.now().isoformat()}")
        print(f"{Fore.CYAN}{'='*70}\n")

    def print_step(self, step_name: str):
        """Print step header"""
        print(f"{Fore.YELLOW}▶ {step_name}...{Style.RESET_ALL}")

    def record_result(self, result: CheckResult):
        """Record check result"""
        if result.passed:
            self.checks_passed.append(result)
            print(f"  {Fore.GREEN}✓ {result.name}: {result.message}{Style.RESET_ALL}")
        else:
            self.checks_failed.append(result)
            print(f"  {Fore.RED}✗ {result.name}: {result.message}{Style.RESET_ALL}")

        if result.duration > 0:
            print(f"    {Fore.CYAN}Duration: {result.duration:.2f}s{Style.RESET_ALL}")

    async def check_environment_variables(self) -> List[CheckResult]:
        """Validate all required environment variables"""
        results = []
        start_time = time.time()

        required_vars = {
            # Core
            'DATABASE_URL': 'Database connection string',
            'REDIS_URL': 'Redis connection string',
            'JWT_SECRET': 'JWT signing secret',
            'ENCRYPTION_KEY': 'Data encryption key',

            # Authentication
            'CLERK_SECRET_KEY': 'Clerk authentication secret',
            'CLERK_PUBLISHABLE_KEY': 'Clerk publishable key',

            # LLM Providers
            'OPENAI_API_KEY': 'OpenAI API key',
            'ANTHROPIC_API_KEY': 'Anthropic API key',

            # Payment
            'STRIPE_SECRET_KEY': 'Stripe secret key',
            'STRIPE_WEBHOOK_SECRET': 'Stripe webhook secret',

            # Monitoring
            'SENTRY_DSN': 'Sentry error tracking DSN',
            'DATADOG_API_KEY': 'Datadog monitoring API key',

            # Storage
            'AWS_ACCESS_KEY_ID': 'AWS access key',
            'AWS_SECRET_ACCESS_KEY': 'AWS secret key',
            'S3_BUCKET': 'S3 storage bucket',

            # Email
            'RESEND_API_KEY': 'Email service API key',
            'FROM_EMAIL': 'From email address',

            # Domains
            'API_URL': 'API domain URL',
            'FRONTEND_URL': 'Frontend domain URL'
        }

        missing = []
        invalid = []

        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value:
                missing.append(f"{var} ({description})")
            elif var.endswith('_KEY') and len(value) < 20:
                invalid.append(f"{var} (too short)")
            elif var.endswith('_URL') and not value.startswith(('http://', 'https://', 'postgresql://', 'redis://')):
                invalid.append(f"{var} (invalid format)")

        # Check for placeholder values
        placeholder_patterns = [
            'xxxxx', 'CHANGE-ME', 'REPLACE-ME', 'your-', 'production-',
            'SECURE_PASS_HERE', 'GENERATE_WITH'
        ]

        placeholders = []
        for var, description in required_vars.items():
            value = os.getenv(var, '')
            if any(pattern in value for pattern in placeholder_patterns):
                placeholders.append(f"{var} (contains placeholder)")

        duration = time.time() - start_time

        # Record results
        if missing:
            results.append(CheckResult(
                "Missing Environment Variables",
                False,
                f"Missing {len(missing)} variables: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}",
                duration,
                {"missing": missing}
            ))

        if invalid:
            results.append(CheckResult(
                "Invalid Environment Variables",
                False,
                f"Invalid {len(invalid)} variables: {', '.join(invalid[:3])}{'...' if len(invalid) > 3 else ''}",
                duration,
                {"invalid": invalid}
            ))

        if placeholders:
            results.append(CheckResult(
                "Placeholder Environment Variables",
                False,
                f"Found {len(placeholders)} placeholder values",
                duration,
                {"placeholders": placeholders}
            ))

        if not missing and not invalid and not placeholders:
            results.append(CheckResult(
                "Environment Variables",
                True,
                f"All {len(required_vars)} required variables configured",
                duration
            ))

        return results

    async def check_database(self) -> List[CheckResult]:
        """Test database connectivity and configuration"""
        results = []
        start_time = time.time()

        try:
            # Test connection
            engine = create_engine(os.getenv('DATABASE_URL'))
            with engine.connect() as conn:
                # Test basic query
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]

                # Check pgvector extension
                try:
                    conn.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
                    vector_enabled = True
                except:
                    vector_enabled = False

                # Check database size
                result = conn.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
                db_size = result.fetchone()[0]

                # Check connection count
                result = conn.execute(text("SELECT count(*) FROM pg_stat_activity"))
                connection_count = result.fetchone()[0]

            duration = time.time() - start_time

            results.append(CheckResult(
                "Database Connection",
                True,
                f"Connected to PostgreSQL {version.split()[1]}",
                duration,
                {
                    "version": version,
                    "size": db_size,
                    "connections": connection_count,
                    "pgvector": vector_enabled
                }
            ))

            if not vector_enabled:
                results.append(CheckResult(
                    "pgvector Extension",
                    False,
                    "pgvector extension not found - required for embeddings",
                    0
                ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(CheckResult(
                "Database Connection",
                False,
                f"Failed to connect: {str(e)}",
                duration
            ))

        return results

    async def check_redis(self) -> List[CheckResult]:
        """Test Redis connectivity and configuration"""
        results = []
        start_time = time.time()

        try:
            r = redis.from_url(os.getenv('REDIS_URL'))

            # Test connection
            r.ping()

            # Get Redis info
            info = r.info()
            version = info.get('redis_version', 'unknown')
            memory_used = info.get('used_memory_human', 'unknown')
            connected_clients = info.get('connected_clients', 0)

            # Test operations
            test_key = f"health_check_{int(time.time())}"
            r.set(test_key, "test", ex=60)
            r.delete(test_key)

            duration = time.time() - start_time

            results.append(CheckResult(
                "Redis Connection",
                True,
                f"Connected to Redis {version}",
                duration,
                {
                    "version": version,
                    "memory_used": memory_used,
                    "connected_clients": connected_clients
                }
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(CheckResult(
                "Redis Connection",
                False,
                f"Failed to connect: {str(e)}",
                duration
            ))

        return results

    async def check_external_services(self) -> List[CheckResult]:
        """Test external service connectivity"""
        results = []

        services = [
            {
                "name": "OpenAI API",
                "test": self._test_openai,
                "key": "OPENAI_API_KEY"
            },
            {
                "name": "Anthropic API",
                "test": self._test_anthropic,
                "key": "ANTHROPIC_API_KEY"
            },
            {
                "name": "Stripe API",
                "test": self._test_stripe,
                "key": "STRIPE_SECRET_KEY"
            },
            {
                "name": "AWS S3",
                "test": self._test_aws_s3,
                "key": "AWS_ACCESS_KEY_ID"
            },
            {
                "name": "Sentry",
                "test": self._test_sentry,
                "key": "SENTRY_DSN"
            }
        ]

        for service in services:
            if os.getenv(service["key"]):
                result = await service["test"]()
                results.append(result)
            else:
                results.append(CheckResult(
                    service["name"],
                    False,
                    f"API key not configured ({service['key']})",
                    0
                ))

        return results

    async def _test_openai(self) -> CheckResult:
        """Test OpenAI API connection"""
        start_time = time.time()
        try:
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            models = client.models.list()
            duration = time.time() - start_time

            return CheckResult(
                "OpenAI API",
                True,
                f"Connected successfully ({len(models.data)} models available)",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return CheckResult(
                "OpenAI API",
                False,
                f"Connection failed: {str(e)}",
                duration
            )

    async def _test_anthropic(self) -> CheckResult:
        """Test Anthropic API connection"""
        start_time = time.time()
        try:
            client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            # Test with a simple message
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            duration = time.time() - start_time

            return CheckResult(
                "Anthropic API",
                True,
                "Connected successfully",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return CheckResult(
                "Anthropic API",
                False,
                f"Connection failed: {str(e)}",
                duration
            )

    async def _test_stripe(self) -> CheckResult:
        """Test Stripe API connection"""
        start_time = time.time()
        try:
            response = requests.get(
                "https://api.stripe.com/v1/customers",
                headers={"Authorization": f"Bearer {os.getenv('STRIPE_SECRET_KEY')}"},
                params={"limit": 1}
            )
            duration = time.time() - start_time

            if response.status_code == 200:
                return CheckResult(
                    "Stripe API",
                    True,
                    "Connected successfully",
                    duration
                )
            else:
                return CheckResult(
                    "Stripe API",
                    False,
                    f"API returned status {response.status_code}",
                    duration
                )
        except Exception as e:
            duration = time.time() - start_time
            return CheckResult(
                "Stripe API",
                False,
                f"Connection failed: {str(e)}",
                duration
            )

    async def _test_aws_s3(self) -> CheckResult:
        """Test AWS S3 access"""
        start_time = time.time()
        try:
            s3 = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )

            bucket = os.getenv('S3_BUCKET')
            s3.head_bucket(Bucket=bucket)

            duration = time.time() - start_time

            return CheckResult(
                "AWS S3",
                True,
                f"Access to bucket '{bucket}' confirmed",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return CheckResult(
                "AWS S3",
                False,
                f"Access failed: {str(e)}",
                duration
            )

    async def _test_sentry(self) -> CheckResult:
        """Test Sentry DSN"""
        start_time = time.time()
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=os.getenv('SENTRY_DSN'))

            # Test capture
            sentry_sdk.capture_message("Pre-deployment test", level="info")

            duration = time.time() - start_time

            return CheckResult(
                "Sentry",
                True,
                "DSN validated successfully",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            return CheckResult(
                "Sentry",
                False,
                f"DSN validation failed: {str(e)}",
                duration
            )

    async def check_security_configuration(self) -> List[CheckResult]:
        """Validate security configuration"""
        results = []

        # Check JWT secret strength
        jwt_secret = os.getenv('JWT_SECRET', '')
        if len(jwt_secret) < 32:
            results.append(CheckResult(
                "JWT Secret",
                False,
                f"JWT secret too short ({len(jwt_secret)} chars, minimum 32)",
                0
            ))
        else:
            results.append(CheckResult(
                "JWT Secret",
                True,
                f"JWT secret properly configured ({len(jwt_secret)} chars)",
                0
            ))

        # Check encryption key
        try:
            Fernet(os.getenv('ENCRYPTION_KEY', '').encode())
            results.append(CheckResult(
                "Encryption Key",
                True,
                "Encryption key is valid",
                0
            ))
        except:
            results.append(CheckResult(
                "Encryption Key",
                False,
                "Invalid encryption key format",
                0
            ))

        # Check HTTPS enforcement
        if os.getenv('FORCE_HTTPS', '').lower() == 'true':
            results.append(CheckResult(
                "HTTPS Enforcement",
                True,
                "HTTPS enforcement enabled",
                0
            ))
        else:
            results.append(CheckResult(
                "HTTPS Enforcement",
                False,
                "HTTPS enforcement not enabled",
                0
            ))

        return results

    async def run_tests(self) -> List[CheckResult]:
        """Run test suite"""
        results = []
        start_time = time.time()

        try:
            # Check if tests exist
            test_dir = Path("tests")
            if not test_dir.exists():
                return [CheckResult(
                    "Test Suite",
                    False,
                    "Tests directory not found",
                    0
                )]

            # Run pytest
            result = subprocess.run(
                ['python', '-m', 'pytest', 'tests/', '--tb=short', '-q', '--maxfail=5'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                # Extract test count from output
                output_lines = result.stdout.split('\n')
                test_line = [line for line in output_lines if 'passed' in line and 'failed' not in line]

                results.append(CheckResult(
                    "Test Suite",
                    True,
                    f"All tests passed ({test_line[0] if test_line else 'tests completed'})",
                    duration
                ))
            else:
                results.append(CheckResult(
                    "Test Suite",
                    False,
                    f"Tests failed with return code {result.returncode}",
                    duration,
                    {"stderr": result.stderr[:500]}  # First 500 chars of error
                ))

        except subprocess.TimeoutExpired:
            results.append(CheckResult(
                "Test Suite",
                False,
                "Tests timed out after 5 minutes",
                300
            ))
        except Exception as e:
            duration = time.time() - start_time
            results.append(CheckResult(
                "Test Suite",
                False,
                f"Could not run tests: {str(e)}",
                duration
            ))

        return results

    async def check_docker_images(self) -> List[CheckResult]:
        """Check Docker image requirements"""
        results = []

        # Check if Dockerfile exists
        dockerfiles = ['Dockerfile', 'Dockerfile.production']
        dockerfile_found = False

        for dockerfile in dockerfiles:
            if Path(dockerfile).exists():
                dockerfile_found = True
                results.append(CheckResult(
                    f"Docker Configuration",
                    True,
                    f"{dockerfile} found",
                    0
                ))
                break

        if not dockerfile_found:
            results.append(CheckResult(
                "Docker Configuration",
                False,
                "No Dockerfile found",
                0
            ))

        # Check requirements.txt
        if Path("requirements.txt").exists():
            results.append(CheckResult(
                "Python Dependencies",
                True,
                "requirements.txt found",
                0
            ))
        else:
            results.append(CheckResult(
                "Python Dependencies",
                False,
                "requirements.txt not found",
                0
            ))

        return results

    def print_summary(self):
        """Print final summary"""
        total_checks = len(self.checks_passed) + len(self.checks_failed)
        success_rate = (len(self.checks_passed) / total_checks * 100) if total_checks > 0 else 0

        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}   VALIDATION SUMMARY")
        print(f"{Fore.CYAN}{'='*70}\n")

        print(f"Total Checks: {total_checks}")
        print(f"{Fore.GREEN}Passed: {len(self.checks_passed)}{Style.RESET_ALL}")
        print(f"{Fore.RED}Failed: {len(self.checks_failed)}{Style.RESET_ALL}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Total Duration: {self.total_duration:.2f}s")

        if self.checks_failed:
            print(f"\n{Fore.RED}❌ FAILED CHECKS:{Style.RESET_ALL}")
            for check in self.checks_failed:
                print(f"  • {check.name}: {check.message}")
                if check.details:
                    for key, value in check.details.items():
                        if isinstance(value, list) and len(value) <= 3:
                            print(f"    {key}: {', '.join(map(str, value))}")

        if self.warnings:
            print(f"\n{Fore.YELLOW}⚠️  WARNINGS:{Style.RESET_ALL}")
            for warning in self.warnings:
                print(f"  • {warning}")

        print(f"\n{Fore.CYAN}{'='*70}")
        if len(self.checks_failed) == 0:
            print(f"{Fore.GREEN}   ✅ READY FOR DEPLOYMENT!{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}   ❌ NOT READY - Fix {len(self.checks_failed)} critical issues{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}\n")

    async def run_all_checks(self) -> bool:
        """Execute all pre-deployment checks"""
        start_time = time.time()

        self.print_header()

        # Define check sequence
        check_sequence = [
            ("Environment Variables", self.check_environment_variables),
            ("Database Connection", self.check_database),
            ("Redis Connection", self.check_redis),
            ("External Services", self.check_external_services),
            ("Security Configuration", self.check_security_configuration),
            ("Docker Configuration", self.check_docker_images),
            ("Test Suite", self.run_tests),
        ]

        # Execute checks
        for step_name, check_func in check_sequence:
            self.print_step(step_name)
            try:
                results = await check_func()
                for result in results:
                    self.record_result(result)
            except Exception as e:
                self.record_result(CheckResult(
                    step_name,
                    False,
                    f"Check failed with exception: {str(e)}",
                    0
                ))
            print()  # Empty line between sections

        self.total_duration = time.time() - start_time
        self.print_summary()

        return len(self.checks_failed) == 0

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pre-deployment validation for AgentOS")
    parser.add_argument("--env", default=".env.production", help="Environment file to use")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    checker = PreDeploymentChecker(args.env)

    try:
        success = asyncio.run(checker.run_all_checks())

        if args.json:
            results = {
                "success": success,
                "total_checks": len(checker.checks_passed) + len(checker.checks_failed),
                "passed": len(checker.checks_passed),
                "failed": len(checker.checks_failed),
                "duration": checker.total_duration,
                "timestamp": datetime.now().isoformat(),
                "failed_checks": [
                    {"name": check.name, "message": check.message, "details": check.details}
                    for check in checker.checks_failed
                ]
            }
            print(json.dumps(results, indent=2))

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Validation interrupted by user{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Validation failed with error: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)