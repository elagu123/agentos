"""
Researcher Agent for AgentOS

Specialized agent for conducting research, gathering information,
and providing comprehensive analysis on various topics.
"""

from typing import Dict, List, Any, Optional, Tuple
import re
import json
import asyncio
from datetime import datetime, timedelta
import httpx

from .base_agent import BaseAgent, AgentCapability, AgentContext, AgentConfig
from app.core.multi_llm_router import TaskType


class ResearcherAgent(BaseAgent):
    """
    Specialized agent for research and information gathering tasks.

    Capabilities:
    - Web research and information gathering
    - Competitive analysis
    - Market research
    - Industry trend analysis
    - Source verification and fact-checking
    - Research synthesis and reporting
    """

    def __init__(self):
        config = AgentConfig(
            name="Researcher Agent",
            description="Expert researcher for gathering, analyzing, and synthesizing information",
            capabilities=[
                AgentCapability.RESEARCH,
                AgentCapability.WEB_SEARCH,
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.TEXT_GENERATION
            ],
            model_preferences={
                TaskType.DATA_ANALYSIS.value: "gpt-4o",
                TaskType.BULK_PROCESSING.value: "claude-3-5-sonnet-20241022",
                TaskType.REALTIME_CHAT.value: "gpt-4o-mini"
            },
            max_tokens=4000,
            temperature=0.3,  # Lower temperature for factual accuracy
            timeout=60,  # Longer timeout for research tasks
            custom_instructions="""
            You are an expert researcher with expertise in:
            - Information gathering and verification
            - Source evaluation and credibility assessment
            - Data synthesis and analysis
            - Research methodology
            - Fact-checking and verification

            Always:
            - Provide accurate and up-to-date information
            - Cite sources when possible
            - Distinguish between facts and opinions
            - Acknowledge limitations and uncertainties
            - Structure information clearly and logically
            - Cross-reference multiple sources
            """,
            tools=["web_search", "source_verifier", "trend_analyzer", "competitor_analyzer"]
        )
        super().__init__(config)
        self._search_engines = {
            "duckduckgo": "https://api.duckduckgo.com/",
            "serp": "https://serpapi.com/search"
        }
        self._research_cache = {}

    async def _execute_core_task(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> str:
        """Execute research task based on the request"""

        # Analyze research type and scope
        research_type = self._analyze_research_type(task)
        search_queries = self._generate_search_queries(task, research_type)

        # Gather information from multiple sources
        research_data = await self._gather_research_data(
            search_queries, research_type, kwargs
        )

        # Analyze and synthesize findings
        analysis = await self._analyze_research_data(research_data, task, context)

        # Generate comprehensive research report
        report = await self._generate_research_report(
            task, research_type, analysis, research_data, context
        )

        return report

    def _analyze_research_type(self, task: str) -> str:
        """Analyze task to determine research type"""
        task_lower = task.lower()

        research_type_patterns = {
            "market_research": [
                "market", "industry", "sector", "market size", "market trends",
                "customer analysis", "demand", "supply"
            ],
            "competitive_analysis": [
                "competitor", "competition", "competitive", "rival", "vs",
                "compare", "comparison", "alternative"
            ],
            "trend_analysis": [
                "trend", "trending", "future", "forecast", "prediction",
                "emerging", "growth", "decline"
            ],
            "fact_checking": [
                "verify", "fact", "true", "false", "accurate", "check",
                "confirm", "validate"
            ],
            "academic_research": [
                "study", "research", "paper", "academic", "scientific",
                "journal", "publication"
            ],
            "news_research": [
                "news", "current", "recent", "latest", "today",
                "yesterday", "this week"
            ],
            "product_research": [
                "product", "service", "tool", "software", "app",
                "platform", "solution"
            ],
            "general": []
        }

        for research_type, patterns in research_type_patterns.items():
            if any(pattern in task_lower for pattern in patterns):
                return research_type

        return "general"

    def _generate_search_queries(self, task: str, research_type: str) -> List[str]:
        """Generate targeted search queries based on task and type"""

        # Extract key terms from task
        key_terms = self._extract_key_terms(task)

        base_queries = [task]

        # Add research-type specific queries
        if research_type == "market_research":
            base_queries.extend([
                f"{' '.join(key_terms)} market size",
                f"{' '.join(key_terms)} industry trends",
                f"{' '.join(key_terms)} market analysis 2024"
            ])
        elif research_type == "competitive_analysis":
            base_queries.extend([
                f"{' '.join(key_terms)} competitors",
                f"{' '.join(key_terms)} alternatives",
                f"best {' '.join(key_terms)} comparison"
            ])
        elif research_type == "trend_analysis":
            base_queries.extend([
                f"{' '.join(key_terms)} trends 2024",
                f"future of {' '.join(key_terms)}",
                f"{' '.join(key_terms)} predictions"
            ])
        elif research_type == "news_research":
            base_queries.extend([
                f"{' '.join(key_terms)} news",
                f"{' '.join(key_terms)} latest updates",
                f"recent {' '.join(key_terms)} developments"
            ])

        # Limit to top 5 queries to avoid overwhelming
        return base_queries[:5]

    def _extract_key_terms(self, task: str) -> List[str]:
        """Extract key terms from research task"""

        # Remove common words
        stop_words = {
            "research", "find", "information", "about", "what", "how", "why",
            "when", "where", "the", "a", "an", "and", "or", "but", "in",
            "on", "at", "to", "for", "of", "with", "by"
        }

        words = re.findall(r'\b[a-zA-Z]+\b', task.lower())
        key_terms = [word for word in words if word not in stop_words and len(word) > 2]

        return key_terms[:10]  # Limit to most relevant terms

    async def _gather_research_data(
        self,
        queries: List[str],
        research_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Gather research data from multiple sources"""

        research_data = {
            "queries": queries,
            "search_results": [],
            "web_content": [],
            "sources": [],
            "timestamp": datetime.now().isoformat()
        }

        # Check cache first
        cache_key = f"{research_type}:{':'.join(queries)}"
        if cache_key in self._research_cache:
            cached_data = self._research_cache[cache_key]
            # Use cached data if less than 1 hour old
            if datetime.fromisoformat(cached_data["timestamp"]) > datetime.now() - timedelta(hours=1):
                return cached_data

        # Gather data from multiple sources concurrently
        tasks = []

        for query in queries:
            # Simulate web search (in production, integrate with real search APIs)
            tasks.append(self._simulate_web_search(query, research_type))

        # Execute searches concurrently
        search_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process search results
        for i, result in enumerate(search_results):
            if isinstance(result, Exception):
                continue

            research_data["search_results"].append({
                "query": queries[i],
                "results": result
            })

        # Cache results
        self._research_cache[cache_key] = research_data

        return research_data

    async def _simulate_web_search(
        self,
        query: str,
        research_type: str
    ) -> List[Dict[str, Any]]:
        """Simulate web search results (replace with real API in production)"""

        # This is a simulation - in production, integrate with:
        # - Google Search API
        # - Bing Search API
        # - DuckDuckGo API
        # - Academic databases (when applicable)

        # Simulate realistic search results
        results = [
            {
                "title": f"Research Results for: {query}",
                "url": f"https://example.com/research/{query.replace(' ', '-')}",
                "snippet": f"Comprehensive analysis and insights about {query}. This source provides detailed information on market trends, competitive landscape, and industry developments.",
                "source": "Example Research Institute",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "relevance_score": 0.85
            },
            {
                "title": f"{query.title()} - Industry Report 2024",
                "url": f"https://industry-reports.com/{query.replace(' ', '-')}",
                "snippet": f"Latest industry report covering {query} with market analysis, key players, and future outlook. Includes statistical data and expert insights.",
                "source": "Industry Analytics",
                "date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "relevance_score": 0.78
            },
            {
                "title": f"Expert Analysis: {query}",
                "url": f"https://expert-insights.com/analysis/{query.replace(' ', '-')}",
                "snippet": f"Expert perspective on {query} including current trends, challenges, and opportunities in the field.",
                "source": "Expert Insights",
                "date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                "relevance_score": 0.72
            }
        ]

        # Add research-type specific results
        if research_type == "competitive_analysis":
            results.append({
                "title": f"Top Competitors in {query}",
                "url": f"https://competitor-analysis.com/{query.replace(' ', '-')}",
                "snippet": f"Comprehensive competitive analysis for {query} including market share, strengths, weaknesses, and positioning strategies.",
                "source": "Competitive Intelligence",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "relevance_score": 0.88
            })

        elif research_type == "market_research":
            results.append({
                "title": f"{query} Market Size and Forecast",
                "url": f"https://market-research.com/{query.replace(' ', '-')}",
                "snippet": f"Market size, growth projections, and segment analysis for {query} with detailed statistics and forecasts through 2030.",
                "source": "Market Research Group",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "relevance_score": 0.92
            })

        return results

    async def _analyze_research_data(
        self,
        research_data: Dict[str, Any],
        task: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Analyze and synthesize research data"""

        # Prepare analysis prompt
        analysis_prompt = self._build_analysis_prompt(research_data, task, context)

        # Generate analysis using LLM
        analysis_response = await self.generate_llm_response(
            analysis_prompt, TaskType.DATA_ANALYSIS
        )

        # Extract structured insights
        insights = await self._extract_structured_insights(analysis_response, research_data)

        return {
            "raw_analysis": analysis_response,
            "structured_insights": insights,
            "source_count": len(research_data.get("search_results", [])),
            "confidence_score": self._calculate_research_confidence(research_data)
        }

    def _build_analysis_prompt(
        self,
        research_data: Dict[str, Any],
        task: str,
        context: AgentContext
    ) -> str:
        """Build prompt for research analysis"""

        search_results_text = ""
        for result_group in research_data.get("search_results", []):
            query = result_group["query"]
            search_results_text += f"\n=== Results for: {query} ===\n"

            for result in result_group["results"]:
                search_results_text += f"""
Title: {result['title']}
Source: {result['source']}
Date: {result['date']}
Content: {result['snippet']}
Relevance: {result['relevance_score']}
---
"""

        prompt = f"""
Research Task: {task}

Research Data:
{search_results_text}

Please analyze this research data and provide:

1. KEY FINDINGS
   - Most important discoveries
   - Confirmed facts and verified information
   - Significant trends or patterns

2. SYNTHESIS
   - How different sources relate to each other
   - Conflicting information (if any)
   - Gaps in available information

3. INSIGHTS
   - Implications and meaning of findings
   - Context and significance
   - Actionable intelligence

4. SOURCE EVALUATION
   - Credibility assessment of sources
   - Potential biases or limitations
   - Data quality indicators

5. CONCLUSIONS
   - Direct answers to the research question
   - Confidence level in findings
   - Recommendations for further research

Format your response with clear sections and bullet points for easy reading.
"""

        return prompt

    async def _extract_structured_insights(
        self,
        analysis_response: str,
        research_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract structured insights from analysis"""

        # Use LLM to extract structured data
        extraction_prompt = f"""
        Extract key insights from this research analysis in JSON format:

        {analysis_response}

        Provide JSON with this structure:
        {{
            "key_findings": ["finding1", "finding2", "finding3"],
            "trends": ["trend1", "trend2"],
            "opportunities": ["opportunity1", "opportunity2"],
            "challenges": ["challenge1", "challenge2"],
            "recommendations": ["rec1", "rec2"],
            "confidence_indicators": {{
                "source_diversity": "high/medium/low",
                "information_recency": "current/somewhat_current/outdated",
                "data_quality": "high/medium/low"
            }}
        }}
        """

        try:
            extraction_response = await self.generate_llm_response(
                extraction_prompt, TaskType.DATA_ANALYSIS
            )

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', extraction_response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except (json.JSONDecodeError, Exception):
            pass

        # Fallback extraction
        return {
            "key_findings": ["Analysis completed successfully"],
            "trends": [],
            "opportunities": [],
            "challenges": [],
            "recommendations": ["Review detailed analysis for insights"],
            "confidence_indicators": {
                "source_diversity": "medium",
                "information_recency": "current",
                "data_quality": "medium"
            }
        }

    def _calculate_research_confidence(self, research_data: Dict[str, Any]) -> float:
        """Calculate confidence score for research findings"""

        base_confidence = 0.5
        search_results = research_data.get("search_results", [])

        # Increase confidence based on source count
        source_count = len(search_results)
        if source_count >= 5:
            base_confidence += 0.2
        elif source_count >= 3:
            base_confidence += 0.1

        # Calculate average relevance score
        total_relevance = 0
        result_count = 0

        for result_group in search_results:
            for result in result_group["results"]:
                total_relevance += result.get("relevance_score", 0.5)
                result_count += 1

        if result_count > 0:
            avg_relevance = total_relevance / result_count
            base_confidence += (avg_relevance - 0.5) * 0.3

        return min(max(base_confidence, 0.0), 1.0)

    async def _generate_research_report(
        self,
        task: str,
        research_type: str,
        analysis: Dict[str, Any],
        research_data: Dict[str, Any],
        context: AgentContext
    ) -> str:
        """Generate comprehensive research report"""

        report_prompt = f"""
        Create a comprehensive research report based on this analysis:

        Research Task: {task}
        Research Type: {research_type}

        Analysis Summary:
        {analysis['raw_analysis']}

        Key Insights:
        {json.dumps(analysis['structured_insights'], indent=2)}

        Please format this as a professional research report with:

        1. EXECUTIVE SUMMARY
        2. RESEARCH METHODOLOGY
        3. KEY FINDINGS
        4. DETAILED ANALYSIS
        5. CONCLUSIONS AND RECOMMENDATIONS
        6. SOURCES AND REFERENCES

        The report should be:
        - Professional and well-structured
        - Fact-based and objective
        - Easy to understand
        - Actionable where appropriate
        """

        report = await self.generate_llm_response(
            report_prompt, TaskType.BULK_PROCESSING
        )

        # Add metadata footer
        metadata = f"""

        ---
        Research Report Metadata:
        - Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        - Sources Analyzed: {analysis['source_count']}
        - Confidence Score: {analysis['confidence_score']:.2f}
        - Research Type: {research_type}
        - Agent: {self.config.name}
        """

        return report + metadata

    async def conduct_competitive_analysis(
        self,
        company_name: str,
        industry: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Conduct detailed competitive analysis"""

        task = f"Competitive analysis for {company_name} in {industry} industry"

        # Generate competitor-specific queries
        queries = [
            f"{company_name} competitors {industry}",
            f"top companies in {industry}",
            f"{company_name} vs competitors",
            f"{industry} market leaders",
            f"{company_name} competitive advantages"
        ]

        research_data = await self._gather_research_data(queries, "competitive_analysis", {})
        analysis = await self._analyze_research_data(research_data, task, context)

        return {
            "target_company": company_name,
            "industry": industry,
            "analysis": analysis,
            "research_data": research_data
        }

    async def track_industry_trends(
        self,
        industry: str,
        timeframe: str = "2024",
        context: AgentContext = None
    ) -> Dict[str, Any]:
        """Track and analyze industry trends"""

        task = f"Industry trends analysis for {industry} in {timeframe}"

        queries = [
            f"{industry} trends {timeframe}",
            f"future of {industry}",
            f"{industry} market forecast",
            f"emerging technologies {industry}",
            f"{industry} disruption {timeframe}"
        ]

        research_data = await self._gather_research_data(queries, "trend_analysis", {})
        analysis = await self._analyze_research_data(research_data, task, context)

        return {
            "industry": industry,
            "timeframe": timeframe,
            "trends": analysis["structured_insights"],
            "confidence": analysis["confidence_score"]
        }

    def _get_tool_function(self, tool_name: str):
        """Get researcher-specific tool functions"""
        tools = {
            "web_search": self._simulate_web_search,
            "source_verifier": self._verify_source,
            "trend_analyzer": self.track_industry_trends,
            "competitor_analyzer": self.conduct_competitive_analysis
        }
        return tools.get(tool_name)

    async def _verify_source(self, source_url: str) -> Dict[str, Any]:
        """Verify credibility of a source"""

        # In production, this would check:
        # - Domain authority
        # - Publication reputation
        # - Author credentials
        # - Publication date
        # - Fact-checking status

        return {
            "url": source_url,
            "credibility": "medium",
            "authority_score": 0.7,
            "bias_assessment": "minimal",
            "last_updated": "recent"
        }