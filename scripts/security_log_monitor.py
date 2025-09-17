#!/usr/bin/env python3
"""
Security Log Monitor for AgentOS
Real-time monitoring of security middleware logs to detect false positives and legitimate requests being blocked
"""

import asyncio
import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging
import sys
from pathlib import Path
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

@dataclass
class SecurityEvent:
    timestamp: datetime
    ip_address: str
    endpoint: str
    method: str
    threat_type: str
    blocked: bool
    user_agent: str = ""
    payload_sample: str = ""
    reason: str = ""

@dataclass
class SecurityStats:
    total_requests: int = 0
    blocked_requests: int = 0
    unique_ips: Set[str] = field(default_factory=set)
    threat_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    top_blocked_ips: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    hourly_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

class SecurityLogMonitor:
    def __init__(self, log_file_path: str = None):
        self.log_file_path = log_file_path or "app.log"
        self.events: List[SecurityEvent] = []
        self.stats = SecurityStats()
        self.running = False

        # Patterns for detecting security events in logs
        self.security_patterns = {
            'blocked_request': r'Security middleware.*blocked.*IP:\s*(\S+).*endpoint:\s*(\S+)',
            'xss_detected': r'XSS attempt detected from (\S+)',
            'sql_injection_detected': r'SQL injection attempt detected from (\S+)',
            'path_traversal_detected': r'Path traversal attempt detected from (\S+)',
            'rate_limit_exceeded': r'Rate limit exceeded.*IP:\s*(\S+)',
            'ip_blocked': r'IP (\S+) blocked temporarily',
        }

        # Known legitimate user agents (to detect false positives)
        self.legitimate_user_agents = [
            r'Mozilla/\d+\.\d+.*Chrome',
            r'Mozilla/\d+\.\d+.*Firefox',
            r'Mozilla/\d+\.\d+.*Safari',
            r'curl/\d+\.\d+',
            r'python-requests',
            r'PostmanRuntime',
            r'insomnia',
        ]

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def print_colored(self, message: str, color: str = "WHITE"):
        """Print colored message"""
        colors = {
            "RED": Fore.RED,
            "GREEN": Fore.GREEN,
            "YELLOW": Fore.YELLOW,
            "BLUE": Fore.BLUE,
            "CYAN": Fore.CYAN,
            "MAGENTA": Fore.MAGENTA,
            "WHITE": Fore.WHITE
        }
        print(f"{colors.get(color, Fore.WHITE)}{message}{Style.RESET_ALL}")

    def is_legitimate_user_agent(self, user_agent: str) -> bool:
        """Check if user agent appears to be from a legitimate client"""
        for pattern in self.legitimate_user_agents:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return True
        return False

    def parse_log_line(self, line: str) -> Optional[SecurityEvent]:
        """Parse a log line for security events"""
        try:
            # Try to parse as JSON log entry
            if line.strip().startswith('{'):
                log_entry = json.loads(line.strip())
                message = log_entry.get('message', '')
                timestamp = datetime.fromisoformat(log_entry.get('timestamp', datetime.now().isoformat()))
            else:
                # Parse plain text log
                message = line
                timestamp = datetime.now()

            # Check for security patterns
            for threat_type, pattern in self.security_patterns.items():
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    ip_address = match.group(1) if match.groups() else "unknown"
                    endpoint = match.group(2) if len(match.groups()) > 1 else "unknown"

                    return SecurityEvent(
                        timestamp=timestamp,
                        ip_address=ip_address,
                        endpoint=endpoint,
                        method="unknown",
                        threat_type=threat_type,
                        blocked=True,
                        reason=message
                    )

        except Exception as e:
            self.logger.debug(f"Error parsing log line: {e}")

        return None

    def analyze_event(self, event: SecurityEvent) -> Dict[str, Any]:
        """Analyze a security event for potential false positives"""
        analysis = {
            "is_suspicious": True,
            "confidence": 0.8,
            "reasons": [],
            "recommendations": []
        }

        # Check if user agent looks legitimate
        if self.is_legitimate_user_agent(event.user_agent):
            analysis["confidence"] -= 0.3
            analysis["reasons"].append("Legitimate user agent detected")

        # Check for common development/testing IPs
        if event.ip_address in ['127.0.0.1', 'localhost', '::1']:
            analysis["confidence"] -= 0.4
            analysis["reasons"].append("Local development IP")

        # Check for repeated requests from same IP
        same_ip_events = [e for e in self.events if e.ip_address == event.ip_address]
        if len(same_ip_events) > 10:
            analysis["confidence"] += 0.2
            analysis["reasons"].append(f"Multiple attempts from same IP ({len(same_ip_events)})")

        # Provide recommendations
        if analysis["confidence"] < 0.5:
            analysis["is_suspicious"] = False
            analysis["recommendations"].append("Consider whitelisting this IP or user agent")

        if analysis["confidence"] > 0.9:
            analysis["recommendations"].append("Consider blocking this IP for longer duration")

        return analysis

    def update_stats(self, event: SecurityEvent):
        """Update monitoring statistics"""
        self.stats.total_requests += 1
        if event.blocked:
            self.stats.blocked_requests += 1

        self.stats.unique_ips.add(event.ip_address)
        self.stats.threat_types[event.threat_type] += 1
        self.stats.top_blocked_ips[event.ip_address] += 1

        # Hourly stats
        hour_key = event.timestamp.strftime("%Y-%m-%d %H:00")
        if hour_key not in self.stats.hourly_stats:
            self.stats.hourly_stats[hour_key] = {"total": 0, "blocked": 0}

        self.stats.hourly_stats[hour_key]["total"] += 1
        if event.blocked:
            self.stats.hourly_stats[hour_key]["blocked"] += 1

    def print_real_time_alert(self, event: SecurityEvent, analysis: Dict[str, Any]):
        """Print real-time security alert"""
        if analysis["is_suspicious"]:
            color = "RED" if analysis["confidence"] > 0.8 else "YELLOW"
            self.print_colored(f"🚨 SECURITY ALERT", color)
        else:
            self.print_colored(f"ℹ️  SECURITY INFO", "CYAN")

        print(f"   Time: {event.timestamp.strftime('%H:%M:%S')}")
        print(f"   IP: {event.ip_address}")
        print(f"   Endpoint: {event.endpoint}")
        print(f"   Threat: {event.threat_type}")
        print(f"   Confidence: {analysis['confidence']:.1%}")

        if analysis["reasons"]:
            print(f"   Reasons: {', '.join(analysis['reasons'])}")

        if analysis["recommendations"]:
            print(f"   Recommendations: {', '.join(analysis['recommendations'])}")

        print("-" * 50)

    def print_summary_stats(self):
        """Print summary statistics"""
        print("\n" + "="*60)
        self.print_colored("SECURITY MONITORING SUMMARY", "MAGENTA")
        print("="*60)

        print(f"Total Requests Monitored: {self.stats.total_requests}")
        print(f"Blocked Requests: {self.stats.blocked_requests}")
        print(f"Block Rate: {(self.stats.blocked_requests/self.stats.total_requests*100) if self.stats.total_requests > 0 else 0:.1f}%")
        print(f"Unique IPs: {len(self.stats.unique_ips)}")

        # Top threat types
        if self.stats.threat_types:
            print(f"\n{Fore.YELLOW}Top Threat Types:{Style.RESET_ALL}")
            sorted_threats = sorted(self.stats.threat_types.items(), key=lambda x: x[1], reverse=True)
            for threat, count in sorted_threats[:5]:
                print(f"  {threat}: {count}")

        # Top blocked IPs
        if self.stats.top_blocked_ips:
            print(f"\n{Fore.RED}Top Blocked IPs:{Style.RESET_ALL}")
            sorted_ips = sorted(self.stats.top_blocked_ips.items(), key=lambda x: x[1], reverse=True)
            for ip, count in sorted_ips[:5]:
                print(f"  {ip}: {count} attempts")

        # Recent hourly stats
        if self.stats.hourly_stats:
            print(f"\n{Fore.CYAN}Hourly Activity (Last 6 hours):{Style.RESET_ALL}")
            recent_hours = sorted(self.stats.hourly_stats.keys())[-6:]
            for hour in recent_hours:
                stats = self.stats.hourly_stats[hour]
                block_rate = (stats["blocked"]/stats["total"]*100) if stats["total"] > 0 else 0
                print(f"  {hour}: {stats['total']} requests, {stats['blocked']} blocked ({block_rate:.1f}%)")

    async def monitor_file(self, follow: bool = True):
        """Monitor log file for security events"""
        self.print_colored("🔍 Starting Security Log Monitor...", "GREEN")
        self.print_colored(f"📁 Monitoring: {self.log_file_path}", "CYAN")

        try:
            if not Path(self.log_file_path).exists():
                self.print_colored(f"⚠️  Log file not found: {self.log_file_path}", "YELLOW")
                self.print_colored("💡 Creating sample security events for demonstration...", "CYAN")
                await self.simulate_security_events()
                return

            self.running = True

            with open(self.log_file_path, 'r') as file:
                # Start from end of file if following
                if follow:
                    file.seek(0, 2)

                while self.running:
                    line = file.readline()

                    if line:
                        event = self.parse_log_line(line)
                        if event:
                            self.events.append(event)
                            self.update_stats(event)

                            analysis = self.analyze_event(event)
                            self.print_real_time_alert(event, analysis)

                    elif follow:
                        await asyncio.sleep(0.1)  # Brief pause before checking for new lines
                    else:
                        break  # End of file reached and not following

        except KeyboardInterrupt:
            self.running = False
            self.print_colored("\n⏹️  Monitoring stopped by user", "YELLOW")
        except Exception as e:
            self.print_colored(f"❌ Error monitoring file: {e}", "RED")

        finally:
            self.print_summary_stats()

    async def simulate_security_events(self):
        """Simulate security events for demonstration"""
        sample_events = [
            SecurityEvent(
                timestamp=datetime.now(),
                ip_address="192.168.1.100",
                endpoint="/api/v1/feedback/submit",
                method="POST",
                threat_type="xss_detected",
                blocked=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                reason="XSS attempt detected"
            ),
            SecurityEvent(
                timestamp=datetime.now(),
                ip_address="10.0.0.5",
                endpoint="/api/v1/auth/login",
                method="POST",
                threat_type="sql_injection_detected",
                blocked=True,
                user_agent="curl/7.68.0",
                reason="SQL injection attempt detected"
            ),
            SecurityEvent(
                timestamp=datetime.now(),
                ip_address="127.0.0.1",
                endpoint="/api/v1/health",
                method="GET",
                threat_type="rate_limit_exceeded",
                blocked=True,
                user_agent="PostmanRuntime/7.28.0",
                reason="Rate limit exceeded"
            )
        ]

        for event in sample_events:
            self.events.append(event)
            self.update_stats(event)

            analysis = self.analyze_event(event)
            self.print_real_time_alert(event, analysis)

            await asyncio.sleep(1)  # Pause between events

async def main():
    """Main monitoring function"""
    log_file = sys.argv[1] if len(sys.argv) > 1 else "app.log"
    follow = "--follow" in sys.argv

    monitor = SecurityLogMonitor(log_file)

    try:
        await monitor.monitor_file(follow=follow)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    print("Usage: python security_log_monitor.py [log_file] [--follow]")
    print("Example: python security_log_monitor.py app.log --follow")
    print()

    asyncio.run(main())