"""
Secure Sandbox Manager for AgentOS
Provides isolated code execution with Docker and gVisor security
"""

import os
import json
import asyncio
import tempfile
import hashlib
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import docker
from docker.types import Mount, RestartPolicy, LogConfig
import resource
import signal
from contextlib import asynccontextmanager
import aiofiles
import logging
import time
import threading
from queue import Queue, Empty
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class SandboxResult:
    success: bool
    output: str
    error: Optional[str] = None
    execution_id: str = ""
    duration_ms: float = 0
    exit_code: int = 0
    resource_usage: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SandboxConfig:
    language: str
    timeout: int = 30
    memory_limit: str = "256m"
    cpu_quota: int = 50000  # 50% CPU
    network_enabled: bool = False
    allowed_imports: List[str] = field(default_factory=list)
    max_file_size: int = 10485760  # 10MB
    max_output_size: int = 1048576  # 1MB

class SecureSandbox:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.docker_client = docker.from_env()

        # Security configuration
        self.runtime = "runsc"  # gVisor runtime
        self.max_containers = 10
        self.container_timeout = 30
        self.memory_limit = "256m"
        self.cpu_quota = 50000

        # Container tracking
        self.active_containers = {}
        self.execution_history = Queue(maxsize=1000)
        self.container_lock = threading.RLock()

        # Pre-built images for different languages
        self.sandbox_images = {
            "python": "agentos/sandbox-python:latest",
            "javascript": "agentos/sandbox-node:latest",
            "sql": "agentos/sandbox-sql:latest",
            "bash": "agentos/sandbox-bash:latest",
            "r": "agentos/sandbox-r:latest",
            "java": "agentos/sandbox-java:latest"
        }

        # Language-specific configurations
        self.language_configs = {
            "python": SandboxConfig(
                language="python",
                allowed_imports=["json", "math", "datetime", "re", "urllib", "base64"],
                timeout=30
            ),
            "javascript": SandboxConfig(
                language="javascript",
                timeout=30
            ),
            "sql": SandboxConfig(
                language="sql",
                timeout=10,
                memory_limit="128m"
            ),
            "bash": SandboxConfig(
                language="bash",
                timeout=15,
                memory_limit="128m"
            )
        }

    async def initialize(self):
        """Initialize sandbox and build images if necessary"""

        # Check if gVisor is available
        if not await self._check_gvisor():
            logger.warning("gVisor not found, falling back to standard Docker isolation")
            self.runtime = "runc"

        # Build sandbox images if they don't exist
        for language, image in self.sandbox_images.items():
            if not await self._image_exists(image):
                await self._build_sandbox_image(language, image)

        # Clean up old containers
        await self._cleanup_old_containers()

        logger.info("Sandbox manager initialized successfully")

    async def _check_gvisor(self) -> bool:
        """Check if gVisor runtime is available"""
        try:
            result = await asyncio.create_subprocess_shell(
                "docker info --format '{{.Runtimes}}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            return "runsc" in stdout.decode()
        except Exception as e:
            logger.error(f"Error checking gVisor: {e}")
            return False

    async def _image_exists(self, image_name: str) -> bool:
        """Check if Docker image exists"""
        try:
            self.docker_client.images.get(image_name)
            return True
        except docker.errors.ImageNotFound:
            return False

    async def _build_sandbox_image(self, language: str, image_name: str):
        """Build sandbox Docker image for specific language"""

        dockerfiles = {
            "python": """
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 sandbox && \
    mkdir -p /sandbox/code && \
    chown -R sandbox:sandbox /sandbox

# Install allowed libraries only
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    pandas==2.0.3 \
    requests==2.31.0 \
    beautifulsoup4==4.12.2 \
    lxml==4.9.3 \
    pillow==10.0.0

# Security hardening
RUN rm -rf /var/lib/apt/lists/* && \
    rm -rf /root/.cache && \
    find /usr/local -name "*.pyc" -delete

# Copy security wrapper
COPY sandbox_wrapper.py /usr/local/bin/sandbox_wrapper.py

USER sandbox
WORKDIR /sandbox

# Environment restrictions
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/sandbox
ENV HOME=/sandbox

# Resource limits
RUN ulimit -n 100 && \
    ulimit -u 10 && \
    ulimit -f 10240

ENTRYPOINT ["python", "/usr/local/bin/sandbox_wrapper.py"]
            """,

            "javascript": """
FROM node:18-slim

RUN useradd -m -u 1000 sandbox && \
    mkdir -p /sandbox/code && \
    chown -R sandbox:sandbox /sandbox

# Install allowed packages
RUN npm install -g --production \
    axios@1.4.0 \
    lodash@4.17.21 \
    moment@2.29.4 \
    cheerio@1.0.0-rc.12

# Security hardening
RUN rm -rf /var/lib/apt/lists/* && \
    rm -rf /root/.npm && \
    npm cache clean --force

USER sandbox
WORKDIR /sandbox

# Disable dangerous modules
ENV NODE_OPTIONS="--no-expose-wasm --disable-proto=delete"
ENV NODE_ENV=production

# Copy security wrapper
COPY node_wrapper.js /usr/local/bin/node_wrapper.js

ENTRYPOINT ["node", "/usr/local/bin/node_wrapper.js"]
            """,

            "sql": """
FROM postgres:15-alpine

RUN adduser -D -u 1000 sandbox

# Create restricted database
RUN initdb -D /tmp/db --auth-local=trust && \
    echo "CREATE DATABASE sandbox;" | postgres --single -D /tmp/db && \
    echo "CREATE USER sandbox_user WITH PASSWORD 'sandbox';" | postgres --single -D /tmp/db && \
    echo "GRANT CONNECT ON DATABASE sandbox TO sandbox_user;" | postgres --single -D /tmp/db

USER sandbox
WORKDIR /sandbox

ENV PGUSER=sandbox_user
ENV PGPASSWORD=sandbox
ENV PGDATABASE=sandbox

COPY sql_wrapper.sh /usr/local/bin/sql_wrapper.sh

ENTRYPOINT ["/usr/local/bin/sql_wrapper.sh"]
            """,

            "bash": """
FROM alpine:latest

RUN adduser -D -u 1000 sandbox && \
    mkdir -p /sandbox && \
    chown -R sandbox:sandbox /sandbox

# Install safe tools only
RUN apk add --no-cache \
    coreutils \
    grep \
    sed \
    awk \
    curl \
    jq \
    bc

# Remove dangerous commands
RUN rm -f /bin/kill /bin/ps /bin/top /usr/bin/killall \
    /sbin/shutdown /sbin/reboot /sbin/halt \
    /bin/mount /bin/umount /usr/bin/wget \
    /usr/bin/ssh /usr/bin/scp /usr/bin/nc

USER sandbox
WORKDIR /sandbox

# Resource limits
RUN ulimit -n 50 && \
    ulimit -u 5 && \
    ulimit -f 5120

COPY bash_wrapper.sh /usr/local/bin/bash_wrapper.sh

ENTRYPOINT ["/usr/local/bin/bash_wrapper.sh"]
            """,

            "r": """
FROM r-base:4.3.1

RUN useradd -m -u 1000 sandbox && \
    mkdir -p /sandbox/code && \
    chown -R sandbox:sandbox /sandbox

# Install allowed packages
RUN R -e "install.packages(c('dplyr', 'ggplot2', 'jsonlite', 'httr'), repos='https://cran.rstudio.com/')"

USER sandbox
WORKDIR /sandbox

ENV R_LIBS_USER=/sandbox/packages

COPY r_wrapper.R /usr/local/bin/r_wrapper.R

ENTRYPOINT ["Rscript", "/usr/local/bin/r_wrapper.R"]
            """,

            "java": """
FROM openjdk:11-jre-slim

RUN useradd -m -u 1000 sandbox && \
    mkdir -p /sandbox/code && \
    chown -R sandbox:sandbox /sandbox

USER sandbox
WORKDIR /sandbox

# Security policy
COPY java.policy /sandbox/java.policy

ENV JAVA_OPTS="-Djava.security.manager -Djava.security.policy=/sandbox/java.policy -Xmx128m"

COPY java_wrapper.sh /usr/local/bin/java_wrapper.sh

ENTRYPOINT ["/usr/local/bin/java_wrapper.sh"]
            """
        }

        dockerfile_content = dockerfiles.get(language)
        if not dockerfile_content:
            raise ValueError(f"Unsupported language: {language}")

        # Create wrapper files
        await self._create_wrapper_files(language)

        # Create temporary directory for build context
        with tempfile.TemporaryDirectory() as build_dir:
            dockerfile_path = os.path.join(build_dir, "Dockerfile")

            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)

            # Copy wrapper files to build context
            await self._copy_wrapper_files(language, build_dir)

            try:
                logger.info(f"Building sandbox image for {language}...")

                # Build image
                image, logs = self.docker_client.images.build(
                    path=build_dir,
                    tag=image_name,
                    forcerm=True,
                    rm=True,
                    pull=True
                )

                logger.info(f"Successfully built {image_name}")

            except docker.errors.BuildError as e:
                logger.error(f"Failed to build {image_name}: {e}")
                raise

    async def _create_wrapper_files(self, language: str):
        """Create security wrapper files for each language"""

        wrappers = {
            "python": """
import sys
import os
import signal
import resource
import subprocess
import json
from datetime import datetime

def set_limits():
    # CPU time limit (30 seconds)
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    # Memory limit (256MB)
    resource.setrlimit(resource.RLIMIT_AS, (256*1024*1024, 256*1024*1024))
    # File size limit (10MB)
    resource.setrlimit(resource.RLIMIT_FSIZE, (10*1024*1024, 10*1024*1024))
    # Process limit
    resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))

def timeout_handler(signum, frame):
    print("TIMEOUT: Execution exceeded time limit", file=sys.stderr)
    sys.exit(124)

def main():
    if len(sys.argv) < 2:
        print("Usage: sandbox_wrapper.py <script_file>", file=sys.stderr)
        sys.exit(1)

    script_file = sys.argv[1]

    # Set resource limits
    set_limits()

    # Set timeout alarm
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)

    try:
        # Validate script exists
        if not os.path.exists(script_file):
            print(f"ERROR: Script file {script_file} not found", file=sys.stderr)
            sys.exit(1)

        # Execute the script
        with open(script_file, 'r') as f:
            code = f.read()

        # Basic security checks
        dangerous_imports = ['os', 'subprocess', 'socket', 'ctypes', 'sys']
        for imp in dangerous_imports:
            if f'import {imp}' in code or f'from {imp}' in code:
                print(f"ERROR: Dangerous import '{imp}' detected", file=sys.stderr)
                sys.exit(1)

        # Execute in restricted environment
        restricted_globals = {
            '__builtins__': {
                'print': print,
                'len': len,
                'range': range,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'bool': bool,
                'abs': abs,
                'max': max,
                'min': min,
                'sum': sum,
                'sorted': sorted,
                'enumerate': enumerate,
                'zip': zip,
                'isinstance': isinstance,
                'type': type,
                'hasattr': hasattr,
                'getattr': getattr
            }
        }

        exec(code, restricted_globals)

    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        signal.alarm(0)

if __name__ == "__main__":
    main()
            """,

            "javascript": """
const fs = require('fs');
const vm = require('vm');

function setLimits() {
    // Set memory limit
    if (process.memoryUsage().heapUsed > 128 * 1024 * 1024) {
        throw new Error('Memory limit exceeded');
    }
}

function main() {
    if (process.argv.length < 3) {
        console.error('Usage: node_wrapper.js <script_file>');
        process.exit(1);
    }

    const scriptFile = process.argv[2];

    // Set timeout
    const timeout = setTimeout(() => {
        console.error('TIMEOUT: Execution exceeded time limit');
        process.exit(124);
    }, 30000);

    try {
        // Check if file exists
        if (!fs.existsSync(scriptFile)) {
            console.error(`ERROR: Script file ${scriptFile} not found`);
            process.exit(1);
        }

        // Read script
        const code = fs.readFileSync(scriptFile, 'utf8');

        // Basic security checks
        const dangerousPatterns = [
            'require\\\\s*\\\\(\\\\s*["\']fs["\']',
            'require\\\\s*\\\\(\\\\s*["\']child_process["\']',
            'require\\\\s*\\\\(\\\\s*["\']net["\']',
            'require\\\\s*\\\\(\\\\s*["\']http["\']',
            'eval\\\\s*\\\\(',
            'Function\\\\s*\\\\(',
            'process\\\\.exit',
            'process\\\\.kill'
        ];

        for (const pattern of dangerousPatterns) {
            const regex = new RegExp(pattern, 'i');
            if (regex.test(code)) {
                console.error(`ERROR: Dangerous pattern detected: ${pattern}`);
                process.exit(1);
            }
        }

        // Create restricted context
        const context = {
            console: console,
            JSON: JSON,
            Math: Math,
            Date: Date,
            Array: Array,
            Object: Object,
            String: String,
            Number: Number,
            Boolean: Boolean,
            parseInt: parseInt,
            parseFloat: parseFloat,
            isNaN: isNaN,
            isFinite: isFinite,
            setTimeout: (fn, delay) => {
                if (delay > 5000) throw new Error('Timeout too long');
                return setTimeout(fn, delay);
            }
        };

        // Execute in sandbox
        vm.createContext(context);
        vm.runInContext(code, context, {
            timeout: 30000,
            displayErrors: true
        });

    } catch (error) {
        console.error(`ERROR: ${error.message}`);
        process.exit(1);
    } finally {
        clearTimeout(timeout);
    }
}

main();
            """,

            "bash": """
#!/bin/sh

# Security wrapper for bash execution
set -e
set -u

if [ $# -lt 1 ]; then
    echo "Usage: bash_wrapper.sh <script_file>" >&2
    exit 1
fi

SCRIPT_FILE="$1"

# Set resource limits
ulimit -t 30    # CPU time
ulimit -f 5120  # File size (5MB)
ulimit -d 131072 # Data segment (128MB)
ulimit -n 50    # Open files
ulimit -u 5     # Processes

# Set timeout
timeout 30s sh "$SCRIPT_FILE"
            """
        }

        # Store wrappers temporarily (would be better to use a proper build system)
        self.wrapper_files = wrappers

    async def _copy_wrapper_files(self, language: str, build_dir: str):
        """Copy wrapper files to build directory"""

        wrapper_files = {
            "python": "sandbox_wrapper.py",
            "javascript": "node_wrapper.js",
            "bash": "bash_wrapper.sh"
        }

        if language in wrapper_files:
            wrapper_path = os.path.join(build_dir, wrapper_files[language])
            with open(wrapper_path, 'w') as f:
                f.write(self.wrapper_files[language])

            # Make executable if shell script
            if language == "bash":
                os.chmod(wrapper_path, 0o755)

    async def execute_code(
        self,
        code: str,
        language: str,
        user_id: str,
        timeout: Optional[int] = None,
        inputs: Optional[Dict] = None,
        allowed_network: bool = False
    ) -> SandboxResult:
        """Execute user code in secure sandbox"""

        execution_id = str(uuid.uuid4())
        start_time = time.time()

        # Get language configuration
        config = self.language_configs.get(language, SandboxConfig(language=language))
        if timeout:
            config.timeout = timeout

        # Security validation
        if not await self._validate_code(code, language):
            return SandboxResult(
                success=False,
                error="Code validation failed - potentially malicious code detected",
                execution_id=execution_id
            )

        # Check concurrent container limit
        with self.container_lock:
            if len(self.active_containers) >= self.max_containers:
                return SandboxResult(
                    success=False,
                    error="Too many concurrent executions, please try again later",
                    execution_id=execution_id
                )

        # Prepare execution environment
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:8]
        container_name = f"sandbox_{user_id}_{code_hash}_{execution_id[:8]}"

        try:
            # Create temporary files
            code_file = await self._prepare_code_file(code, language)
            input_file = None

            if inputs:
                input_file = await self._prepare_input_file(inputs)

            # Container configuration
            volumes = {
                code_file: {"bind": f"/sandbox/code.{self._get_extension(language)}", "mode": "ro"}
            }

            if input_file:
                volumes[input_file] = {"bind": "/sandbox/inputs.json", "mode": "ro"}

            container_config = {
                "image": self.sandbox_images[language],
                "name": container_name,
                "runtime": self.runtime,
                "detach": True,
                "mem_limit": config.memory_limit,
                "memswap_limit": config.memory_limit,
                "cpu_quota": config.cpu_quota,
                "cpu_period": 100000,
                "network_mode": "bridge" if allowed_network else "none",
                "read_only": True,
                "security_opt": [
                    "no-new-privileges:true",
                    "seccomp:default"
                ],
                "cap_drop": ["ALL"],
                "cap_add": [],  # No additional capabilities
                "pids_limit": 50,
                "volumes": volumes,
                "working_dir": "/sandbox",
                "user": "1000:1000",
                "environment": {
                    "EXECUTION_ID": execution_id,
                    "TIMEOUT": str(config.timeout),
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8"
                },
                "labels": {
                    "user_id": user_id,
                    "execution_id": execution_id,
                    "language": language,
                    "created_at": datetime.utcnow().isoformat()
                },
                "tmpfs": {
                    "/tmp": "size=10m,noexec,nosuid,nodev",
                    "/var/tmp": "size=10m,noexec,nosuid,nodev"
                }
            }

            # Create and start container
            container = self.docker_client.containers.run(
                command=f"/sandbox/code.{self._get_extension(language)}",
                **container_config
            )

            # Track active container
            with self.container_lock:
                self.active_containers[container_name] = {
                    "container": container,
                    "start_time": start_time,
                    "user_id": user_id
                }

            # Wait for completion with timeout
            result = await self._wait_for_container(container, config.timeout)

            # Calculate execution time
            duration_ms = (time.time() - start_time) * 1000

            # Get resource usage
            try:
                stats = container.stats(stream=False)
                resource_usage = self._extract_resource_usage(stats)
            except Exception:
                resource_usage = {}

            # Clean up
            await self._cleanup_container(container, code_file, input_file)

            # Log execution
            execution_record = {
                "execution_id": execution_id,
                "user_id": user_id,
                "language": language,
                "code_hash": code_hash,
                "duration_ms": duration_ms,
                "success": result.success,
                "timestamp": datetime.utcnow().isoformat()
            }

            try:
                self.execution_history.put_nowait(execution_record)
            except:
                pass  # Queue full, ignore

            result.execution_id = execution_id
            result.duration_ms = duration_ms
            result.resource_usage = resource_usage

            return result

        except asyncio.TimeoutError:
            await self._cleanup_container_by_name(container_name, code_file, input_file)

            return SandboxResult(
                success=False,
                error=f"Execution timeout ({config.timeout} seconds)",
                execution_id=execution_id,
                duration_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            await self._cleanup_container_by_name(container_name, code_file, input_file)

            return SandboxResult(
                success=False,
                error=f"Execution failed: {str(e)}",
                execution_id=execution_id,
                duration_ms=(time.time() - start_time) * 1000
            )

    async def _validate_code(self, code: str, language: str) -> bool:
        """Validate code for malicious patterns"""

        # Size limits
        if len(code) > 100000:  # 100KB max
            logger.warning("Code too large")
            return False

        # Language-specific dangerous patterns
        dangerous_patterns = {
            "python": [
                r"import\s+os\b",
                r"import\s+subprocess\b",
                r"import\s+socket\b",
                r"import\s+ctypes\b",
                r"from\s+os\s+import",
                r"from\s+subprocess\s+import",
                r"__import__\s*\(",
                r"eval\s*\(",
                r"exec\s*\(",
                r"compile\s*\(",
                r"open\s*\(",
                r"file\s*\(",
                r"input\s*\(",
                r"raw_input\s*\(",
                r"__builtins__",
                r"globals\s*\(",
                r"locals\s*\(",
                r"vars\s*\(",
                r"dir\s*\(",
                r"getattr\s*\(",
                r"setattr\s*\(",
                r"delattr\s*\(",
                r"hasattr\s*\(",
                r"while\s+True\s*:",  # Potential infinite loop
                r"for.*while.*:"  # Nested loops
            ],
            "javascript": [
                r"require\s*\(\s*['\"]fs['\"]",
                r"require\s*\(\s*['\"]child_process['\"]",
                r"require\s*\(\s*['\"]net['\"]",
                r"require\s*\(\s*['\"]http['\"]",
                r"eval\s*\(",
                r"Function\s*\(",
                r"setTimeout\s*\(",
                r"setInterval\s*\(",
                r"process\.exit",
                r"process\.kill",
                r"process\.env",
                r"__dirname",
                r"__filename",
                r"while\s*\(\s*true\s*\)",  # Infinite loop
                r"for\s*\(\s*;\s*;\s*\)"  # Infinite loop
            ],
            "bash": [
                r"rm\s+-rf",
                r"dd\s+if=",
                r"mkfs",
                r":\(\)\{\s*:\|\:&\s*\};:",  # Fork bomb
                r">\s*/dev/sd[a-z]",
                r"chmod\s+777",
                r"sudo\b",
                r"su\s+-",
                r"nc\s+-",
                r"telnet\b",
                r"wget\b",
                r"curl\b",
                r"ssh\b",
                r"while\s+true",  # Infinite loop
                r"until\s+false"  # Infinite loop
            ],
            "sql": [
                r"DROP\s+DATABASE",
                r"DROP\s+TABLE",
                r"DELETE\s+FROM",
                r"TRUNCATE\b",
                r"ALTER\s+TABLE",
                r"CREATE\s+USER",
                r"GRANT\b",
                r"REVOKE\b",
                r"SHUTDOWN\b",
                r"EXEC\b",
                r"xp_cmdshell",
                r"WHILE\s+1\s*=\s*1"  # Infinite loop
            ]
        }

        patterns = dangerous_patterns.get(language, [])

        import re
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected: {pattern}")
                return False

        return True

    async def _prepare_code_file(self, code: str, language: str) -> str:
        """Prepare code file for execution"""

        extension = self._get_extension(language)

        # Add security wrappers for certain languages
        if language == "python":
            wrapped_code = f"""
# Auto-generated security wrapper
import signal
import sys
import time

def timeout_handler(signum, frame):
    print("TIMEOUT: Execution time limit exceeded", file=sys.stderr)
    sys.exit(124)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)

start_time = time.time()

try:
    # User code starts here
{self._indent_code(code, 4)}

except Exception as e:
    print(f"ERROR: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
finally:
    elapsed = time.time() - start_time
    print(f"\\n# Execution completed in {{elapsed:.3f}} seconds", file=sys.stderr)
    signal.alarm(0)
"""
        else:
            wrapped_code = code

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=f'.{extension}',
            delete=False
        ) as f:
            f.write(wrapped_code)
            return f.name

    def _indent_code(self, code: str, indent: int) -> str:
        """Indent code by specified number of spaces"""
        lines = code.split('\n')
        return '\n'.join(' ' * indent + line if line.strip() else line for line in lines)

    async def _prepare_input_file(self, inputs: Dict) -> str:
        """Prepare input file"""

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(inputs, f, indent=2)
            return f.name

    async def _wait_for_container(self, container, timeout: int) -> SandboxResult:
        """Wait for container to complete execution"""

        try:
            # Wait for container to finish
            exit_code = container.wait(timeout=timeout)['StatusCode']

            # Get output
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')

            # Limit output size
            max_output = 50000  # 50KB
            if len(logs) > max_output:
                logs = logs[:max_output] + "\n... (output truncated)"

            return SandboxResult(
                success=exit_code == 0,
                output=logs,
                exit_code=exit_code
            )

        except docker.errors.ContainerError as e:
            return SandboxResult(
                success=False,
                error=f"Container error: {str(e)}",
                output=e.stderr.decode('utf-8', errors='replace') if e.stderr else "",
                exit_code=e.exit_status
            )

        except Exception as e:
            return SandboxResult(
                success=False,
                error=f"Execution error: {str(e)}",
                exit_code=1
            )

    def _extract_resource_usage(self, stats: Dict) -> Dict[str, Any]:
        """Extract resource usage from container stats"""

        try:
            cpu_stats = stats.get('cpu_stats', {})
            memory_stats = stats.get('memory_stats', {})

            return {
                "cpu_usage_percent": self._calculate_cpu_percent(stats),
                "memory_usage_bytes": memory_stats.get('usage', 0),
                "memory_max_bytes": memory_stats.get('max_usage', 0),
                "memory_limit_bytes": memory_stats.get('limit', 0),
                "network_rx_bytes": sum(
                    net.get('rx_bytes', 0)
                    for net in stats.get('networks', {}).values()
                ),
                "network_tx_bytes": sum(
                    net.get('tx_bytes', 0)
                    for net in stats.get('networks', {}).values()
                )
            }
        except Exception as e:
            logger.error(f"Error extracting resource usage: {e}")
            return {}

    def _calculate_cpu_percent(self, stats: Dict) -> float:
        """Calculate CPU usage percentage"""

        try:
            cpu_stats = stats.get('cpu_stats', {})
            prev_cpu_stats = stats.get('precpu_stats', {})

            cpu_usage = cpu_stats.get('cpu_usage', {})
            prev_cpu_usage = prev_cpu_stats.get('cpu_usage', {})

            cpu_delta = cpu_usage.get('total_usage', 0) - prev_cpu_usage.get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - prev_cpu_stats.get('system_cpu_usage', 0)

            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * len(cpu_usage.get('percpu_usage', [])) * 100.0
                return round(cpu_percent, 2)

        except Exception:
            pass

        return 0.0

    async def _cleanup_container(self, container, code_file: str, input_file: Optional[str] = None):
        """Clean up container and temporary files"""

        try:
            # Remove container
            container.remove(force=True)

            # Remove from active containers
            with self.container_lock:
                for name, info in list(self.active_containers.items()):
                    if info["container"].id == container.id:
                        del self.active_containers[name]
                        break

            # Clean up temporary files
            if os.path.exists(code_file):
                os.unlink(code_file)

            if input_file and os.path.exists(input_file):
                os.unlink(input_file)

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    async def _cleanup_container_by_name(self, container_name: str, code_file: str, input_file: Optional[str] = None):
        """Clean up container by name"""

        try:
            with self.container_lock:
                if container_name in self.active_containers:
                    container_info = self.active_containers[container_name]
                    container = container_info["container"]

                    try:
                        container.kill()
                    except:
                        pass

                    await self._cleanup_container(container, code_file, input_file)

        except Exception as e:
            logger.error(f"Cleanup by name error: {e}")

    async def _cleanup_old_containers(self):
        """Clean up old sandbox containers"""

        try:
            containers = self.docker_client.containers.list(
                all=True,
                filters={"name": "sandbox_"}
            )

            for container in containers:
                try:
                    # Check if container is older than 1 hour
                    created = datetime.fromisoformat(
                        container.attrs['Created'].replace('Z', '+00:00')
                    )

                    if datetime.now(created.tzinfo) - created > timedelta(hours=1):
                        container.remove(force=True)
                        logger.info(f"Cleaned up old container: {container.name}")

                except Exception as e:
                    logger.error(f"Error cleaning container {container.name}: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _get_extension(self, language: str) -> str:
        """Get file extension for language"""

        extensions = {
            "python": "py",
            "javascript": "js",
            "bash": "sh",
            "sql": "sql",
            "r": "r",
            "java": "java"
        }
        return extensions.get(language, "txt")

    async def get_execution_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get execution statistics"""

        # Convert queue to list for analysis
        history = []
        temp_queue = Queue()

        try:
            while True:
                record = self.execution_history.get_nowait()
                history.append(record)
                temp_queue.put(record)
        except Empty:
            pass

        # Restore queue
        while not temp_queue.empty():
            self.execution_history.put(temp_queue.get())

        # Filter by user if specified
        if user_id:
            history = [h for h in history if h.get("user_id") == user_id]

        if not history:
            return {"message": "No execution history found"}

        total = len(history)
        successful = sum(1 for h in history if h.get("success", False))

        # Language statistics
        languages = {}
        for h in history:
            lang = h.get("language", "unknown")
            if lang not in languages:
                languages[lang] = {"count": 0, "success": 0}
            languages[lang]["count"] += 1
            if h.get("success", False):
                languages[lang]["success"] += 1

        # Calculate averages
        durations = [h.get("duration_ms", 0) for h in history if h.get("duration_ms")]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": total - successful,
            "success_rate": f"{(successful/total)*100:.1f}%",
            "average_duration_ms": round(avg_duration, 2),
            "active_containers": len(self.active_containers),
            "languages": languages,
            "recent_activity": history[-10:] if history else []
        }

    async def kill_execution(self, execution_id: str) -> bool:
        """Kill running execution by ID"""

        with self.container_lock:
            for name, info in self.active_containers.items():
                if execution_id in name:
                    try:
                        container = info["container"]
                        container.kill()
                        logger.info(f"Killed execution {execution_id}")
                        return True
                    except Exception as e:
                        logger.error(f"Error killing execution {execution_id}: {e}")
                        return False

        return False

    async def get_active_executions(self) -> List[Dict[str, Any]]:
        """Get list of active executions"""

        with self.container_lock:
            active = []
            for name, info in self.active_containers.items():
                active.append({
                    "container_name": name,
                    "user_id": info["user_id"],
                    "start_time": info["start_time"],
                    "duration_seconds": time.time() - info["start_time"],
                    "status": info["container"].status
                })
            return active

# Global singleton instance
sandbox_manager = SecureSandbox()