"""
Copywriter Agent for AgentOS

Specialized agent for creating high-quality marketing copy, content creation,
and brand-aligned communications.
"""

from typing import Dict, List, Any, Optional
import re
import json

from .base_agent import BaseAgent, AgentCapability, AgentContext, AgentConfig
from app.core.multi_llm_router import TaskType


class CopywriterAgent(BaseAgent):
    """
    Specialized agent for copywriting and content creation tasks.

    Capabilities:
    - Marketing copy creation
    - Blog post writing
    - Social media content
    - Email campaigns
    - Product descriptions
    - Brand voice adaptation
    """

    def __init__(self):
        config = AgentConfig(
            name="Copywriter Agent",
            description="Expert copywriter for marketing content, brand communications, and creative writing",
            capabilities=[
                AgentCapability.TEXT_GENERATION,
                AgentCapability.CONTENT_OPTIMIZATION,
                AgentCapability.COPYWRITING
            ],
            model_preferences={
                TaskType.CREATIVE_WRITING.value: "gpt-4o",
                TaskType.REALTIME_CHAT.value: "claude-3-5-sonnet-20241022"
            },
            max_tokens=3000,
            temperature=0.8,  # Higher creativity for copywriting
            custom_instructions="""
            You are an expert copywriter with deep expertise in:
            - Brand voice and tone adaptation
            - Persuasive writing techniques
            - Marketing psychology
            - Content optimization for different platforms
            - A/B testing copy variations

            Always:
            - Adapt to the company's brand voice
            - Use persuasive but authentic language
            - Include clear calls-to-action when appropriate
            - Consider the target audience
            - Optimize for the specific platform/medium
            """,
            tools=["tone_analyzer", "readability_checker", "cta_optimizer"]
        )
        super().__init__(config)
        self._content_templates = self._load_content_templates()

    def _load_content_templates(self) -> Dict[str, str]:
        """Load content templates for different copywriting tasks"""
        return {
            "marketing_email": """
            Subject: {subject}

            Hi {name},

            {opening_hook}

            {main_content}

            {call_to_action}

            Best regards,
            {signature}
            """,

            "social_media_post": """
            {hook}

            {main_message}

            {hashtags}
            {call_to_action}
            """,

            "product_description": """
            {product_name}

            {headline}

            {benefits}

            Key Features:
            {features}

            {call_to_action}
            """,

            "blog_post": """
            # {title}

            {introduction}

            ## {section1_title}
            {section1_content}

            ## {section2_title}
            {section2_content}

            ## {conclusion_title}
            {conclusion}

            {call_to_action}
            """,

            "ad_copy": """
            Headline: {headline}

            {body_text}

            CTA: {call_to_action}
            """
        }

    async def _execute_core_task(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> str:
        """Execute copywriting task based on the request"""

        # Analyze the task to determine content type
        content_type = self._analyze_content_type(task)

        # Extract parameters from task and kwargs
        parameters = self._extract_parameters(task, kwargs)

        # Build context-aware prompt
        prompt = await self._build_copywriting_prompt(
            task, content_type, parameters, context
        )

        # Generate content using appropriate model
        task_type = self._get_task_type(content_type)
        response = await self.generate_llm_response(prompt, task_type)

        # Apply copywriting-specific post-processing
        processed_response = await self._apply_copywriting_processing(
            response, content_type, parameters, context
        )

        return processed_response

    def _analyze_content_type(self, task: str) -> str:
        """Analyze task to determine content type"""
        task_lower = task.lower()

        content_type_patterns = {
            "email": ["email", "newsletter", "campaign"],
            "social_media": ["social", "twitter", "facebook", "instagram", "linkedin", "post"],
            "blog_post": ["blog", "article", "post", "content"],
            "product_description": ["product", "description", "listing"],
            "ad_copy": ["ad", "advertisement", "banner", "ppc"],
            "press_release": ["press", "release", "announcement"],
            "landing_page": ["landing", "page", "conversion"],
            "general": []
        }

        for content_type, patterns in content_type_patterns.items():
            if any(pattern in task_lower for pattern in patterns):
                return content_type

        return "general"

    def _extract_parameters(self, task: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters from task description and kwargs"""
        parameters = kwargs.copy()

        # Extract common parameters from task text
        param_patterns = {
            "target_audience": r"(?:for|targeting|audience:?)\s+([^.]+)",
            "tone": r"(?:tone:?|style:?)\s+([^.]+)",
            "platform": r"(?:platform:?|channel:?)\s+([^.]+)",
            "length": r"(?:length:?|words:?)\s+(\d+)",
            "product": r"(?:product:?|service:?)\s+([^.]+)"
        }

        for param, pattern in param_patterns.items():
            if param not in parameters:
                match = re.search(pattern, task, re.IGNORECASE)
                if match:
                    parameters[param] = match.group(1).strip()

        return parameters

    async def _build_copywriting_prompt(
        self,
        task: str,
        content_type: str,
        parameters: Dict[str, Any],
        context: AgentContext
    ) -> str:
        """Build context-aware prompt for copywriting"""

        # Get business context for brand voice
        brand_context = await self._get_brand_context(context)

        prompt_parts = [
            f"Task: {task}",
            f"Content Type: {content_type}",
            "",
            "Context:",
            brand_context,
            "",
            "Parameters:"
        ]

        # Add parameters
        for key, value in parameters.items():
            prompt_parts.append(f"- {key.replace('_', ' ').title()}: {value}")

        prompt_parts.extend([
            "",
            self.config.custom_instructions,
            "",
            f"Please create {content_type} content that:",
            "1. Aligns with the brand voice and values",
            "2. Speaks directly to the target audience",
            "3. Includes compelling and authentic messaging",
            "4. Has clear structure and flow",
            "5. Includes appropriate calls-to-action",
            "",
            "Content:"
        ])

        return "\n".join(prompt_parts)

    async def _get_brand_context(self, context: AgentContext) -> str:
        """Extract brand context from business information"""
        brand_info = []

        if context.business_context and context.business_context.get("retrieved_contexts"):
            for ctx in context.business_context["retrieved_contexts"]:
                content = ctx.get("content", "")
                # Look for brand-related information
                if any(keyword in content.lower() for keyword in [
                    "mission", "vision", "values", "brand", "voice", "tone"
                ]):
                    brand_info.append(content[:300])

        if brand_info:
            return "Brand Context:\n" + "\n".join(brand_info)
        else:
            return "Brand Context: Use professional, helpful, and authentic tone."

    def _get_task_type(self, content_type: str) -> TaskType:
        """Get appropriate task type for LLM routing"""
        creative_types = ["blog_post", "social_media", "ad_copy"]

        if content_type in creative_types:
            return TaskType.CREATIVE_WRITING
        else:
            return TaskType.REALTIME_CHAT

    async def _apply_copywriting_processing(
        self,
        response: str,
        content_type: str,
        parameters: Dict[str, Any],
        context: AgentContext
    ) -> str:
        """Apply copywriting-specific post-processing"""

        processed = response

        # Apply content-type specific formatting
        if content_type == "email":
            processed = await self._format_email_content(processed, parameters)
        elif content_type == "social_media":
            processed = await self._format_social_media_content(processed, parameters)
        elif content_type == "product_description":
            processed = await self._format_product_description(processed, parameters)

        # Apply general copywriting optimizations
        processed = await self._optimize_readability(processed)
        processed = await self._enhance_cta(processed, content_type)

        return processed

    async def _format_email_content(self, content: str, parameters: Dict[str, Any]) -> str:
        """Format email content with proper structure"""

        # Extract subject line if not in content
        lines = content.split('\n')
        if not any(line.startswith('Subject:') for line in lines[:3]):
            subject = parameters.get('subject', 'Important Update')
            content = f"Subject: {subject}\n\n{content}"

        return content

    async def _format_social_media_content(self, content: str, parameters: Dict[str, Any]) -> str:
        """Format social media content with hashtags and optimal length"""

        platform = parameters.get('platform', '').lower()

        # Platform-specific optimizations
        if platform == 'twitter':
            # Ensure content fits Twitter character limit
            if len(content) > 280:
                content = content[:270] + "..."

        # Add hashtags if not present
        if '#' not in content and parameters.get('hashtags'):
            hashtags = parameters['hashtags']
            if isinstance(hashtags, str):
                content += f"\n\n{hashtags}"
            elif isinstance(hashtags, list):
                content += f"\n\n{' '.join(hashtags)}"

        return content

    async def _format_product_description(self, content: str, parameters: Dict[str, Any]) -> str:
        """Format product description with proper structure"""

        # Ensure product name is prominent
        product_name = parameters.get('product', '')
        if product_name and not content.startswith(product_name):
            content = f"**{product_name}**\n\n{content}"

        return content

    async def _optimize_readability(self, content: str) -> str:
        """Optimize content for readability"""

        # Add line breaks for better readability
        sentences = content.split('. ')
        if len(sentences) > 3:
            # Add paragraph breaks every 2-3 sentences
            optimized_sentences = []
            for i, sentence in enumerate(sentences):
                optimized_sentences.append(sentence)
                if (i + 1) % 3 == 0 and i < len(sentences) - 1:
                    optimized_sentences.append('\n')
            content = '. '.join(optimized_sentences)

        return content

    async def _enhance_cta(self, content: str, content_type: str) -> str:
        """Enhance call-to-action elements"""

        # Common weak CTAs to strengthen
        weak_ctas = {
            "click here": "Get Started Now",
            "learn more": "Discover How",
            "sign up": "Join Today",
            "buy now": "Get Yours Today"
        }

        for weak, strong in weak_ctas.items():
            if weak.lower() in content.lower():
                content = re.sub(
                    weak, strong, content, flags=re.IGNORECASE
                )

        return content

    async def create_content_variations(
        self,
        base_content: str,
        variation_count: int = 3,
        context: AgentContext = None
    ) -> List[str]:
        """Create multiple variations of content for A/B testing"""

        variations = [base_content]  # Include original

        for i in range(variation_count - 1):
            variation_prompt = f"""
            Create a variation of this content that maintains the same message
            but uses different wording, structure, or approach:

            Original: {base_content}

            Variation {i + 1}:
            """

            variation = await self.generate_llm_response(
                variation_prompt, TaskType.CREATIVE_WRITING
            )
            variations.append(variation)

        return variations

    async def analyze_content_tone(self, content: str) -> Dict[str, Any]:
        """Analyze the tone and style of content"""

        analysis_prompt = f"""
        Analyze the tone and style of this content:

        {content}

        Provide analysis in JSON format:
        {{
            "tone": "professional/casual/friendly/formal/etc",
            "sentiment": "positive/neutral/negative",
            "readability": "easy/medium/difficult",
            "persuasiveness": "high/medium/low",
            "brand_alignment": "strong/medium/weak",
            "suggestions": ["improvement1", "improvement2"]
        }}
        """

        response = await self.generate_llm_response(
            analysis_prompt, TaskType.DATA_ANALYSIS
        )

        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Fallback analysis
        return {
            "tone": "neutral",
            "sentiment": "positive",
            "readability": "medium",
            "persuasiveness": "medium",
            "brand_alignment": "medium",
            "suggestions": ["Consider adding more specific details", "Strengthen call-to-action"]
        }

    def _get_tool_function(self, tool_name: str):
        """Get copywriter-specific tool functions"""
        tools = {
            "tone_analyzer": self.analyze_content_tone,
            "readability_checker": self._check_readability,
            "cta_optimizer": self._optimize_cta
        }
        return tools.get(tool_name)

    async def _check_readability(self, content: str) -> Dict[str, Any]:
        """Check content readability"""

        # Simple readability metrics
        sentences = len([s for s in content.split('.') if s.strip()])
        words = len(content.split())
        avg_sentence_length = words / sentences if sentences > 0 else 0

        # Estimate reading level
        if avg_sentence_length < 15:
            reading_level = "easy"
        elif avg_sentence_length < 25:
            reading_level = "medium"
        else:
            reading_level = "difficult"

        return {
            "word_count": words,
            "sentence_count": sentences,
            "avg_sentence_length": round(avg_sentence_length, 1),
            "reading_level": reading_level,
            "estimated_reading_time": f"{words // 200} min"
        }

    async def _optimize_cta(self, content: str) -> str:
        """Optimize call-to-action in content"""

        # This would be called by the tool system
        return await self._enhance_cta(content, "general")