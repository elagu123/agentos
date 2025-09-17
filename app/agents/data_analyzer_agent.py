"""
Data Analyzer Agent for AgentOS

Specialized agent for data analysis, insights generation,
and business intelligence tasks.
"""

from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import re
import json
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io
import base64

from .base_agent import BaseAgent, AgentCapability, AgentContext, AgentConfig
from app.core.multi_llm_router import TaskType


class AnalysisType(Enum):
    """Types of data analysis"""
    DESCRIPTIVE = "descriptive"
    DIAGNOSTIC = "diagnostic"
    PREDICTIVE = "predictive"
    PRESCRIPTIVE = "prescriptive"
    EXPLORATORY = "exploratory"
    COMPARATIVE = "comparative"
    TREND_ANALYSIS = "trend_analysis"
    STATISTICAL = "statistical"


class DataType(Enum):
    """Types of data"""
    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    TIME_SERIES = "time_series"
    TEXT = "text"
    MIXED = "mixed"


class ChartType(Enum):
    """Types of charts for visualization"""
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    SCATTER_PLOT = "scatter_plot"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    BOX_PLOT = "box_plot"
    AREA_CHART = "area_chart"


@dataclass
class DataSource:
    """Data source information"""
    name: str
    type: str  # csv, json, database, api
    location: str
    format: Optional[str] = None
    schema: Optional[Dict[str, str]] = None
    last_updated: Optional[datetime] = None
    size: Optional[int] = None


@dataclass
class AnalysisRequest:
    """Data analysis request"""
    analysis_type: AnalysisType
    data_sources: List[DataSource]
    questions: List[str]
    metrics: List[str]
    dimensions: List[str]
    filters: Dict[str, Any]
    time_range: Optional[Tuple[datetime, datetime]] = None
    visualization_preferences: List[ChartType] = None


@dataclass
class AnalysisResult:
    """Data analysis result"""
    summary: str
    insights: List[str]
    statistics: Dict[str, Any]
    visualizations: List[Dict[str, Any]]
    recommendations: List[str]
    data_quality_issues: List[str]
    confidence_score: float
    methodology: str
    limitations: List[str]


@dataclass
class DataInsight:
    """Individual data insight"""
    title: str
    description: str
    significance: str  # high, medium, low
    supporting_data: Dict[str, Any]
    visualization: Optional[Dict[str, Any]] = None
    business_impact: str
    actionable: bool = True


class DataAnalyzerAgent(BaseAgent):
    """
    Specialized agent for data analysis and business intelligence.

    Capabilities:
    - Statistical analysis and interpretation
    - Data visualization and reporting
    - Trend analysis and forecasting
    - Business metrics calculation
    - Data quality assessment
    - Insight generation and recommendations
    """

    def __init__(self):
        config = AgentConfig(
            name="Data Analyzer Agent",
            description="Expert data analyst for business intelligence, statistical analysis, and insight generation",
            capabilities=[
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.TEXT_GENERATION,
                AgentCapability.FILE_PROCESSING
            ],
            model_preferences={
                TaskType.DATA_ANALYSIS.value: "gpt-4o",
                TaskType.BULK_PROCESSING.value: "claude-3-5-sonnet-20241022",
                TaskType.REALTIME_CHAT.value: "gpt-4o-mini"
            },
            max_tokens=4000,
            temperature=0.1,  # Very low for factual accuracy
            timeout=120,  # Longer timeout for complex analysis
            custom_instructions="""
            You are an expert data analyst with expertise in:
            - Statistical analysis and interpretation
            - Business intelligence and metrics
            - Data visualization and storytelling
            - Trend analysis and forecasting
            - Data quality assessment
            - Business insight generation

            Always:
            - Provide accurate statistical interpretations
            - Explain findings in business terms
            - Identify actionable insights
            - Acknowledge limitations and assumptions
            - Suggest appropriate visualizations
            - Maintain objectivity and avoid bias
            """,
            tools=["statistical_analyzer", "trend_detector", "visualization_generator", "insight_extractor"]
        )
        super().__init__(config)
        self._analysis_templates = self._load_analysis_templates()
        self._statistical_tests = self._load_statistical_tests()

    def _load_analysis_templates(self) -> Dict[str, str]:
        """Load analysis templates for different types"""
        return {
            "descriptive": """
            ## Descriptive Analysis Summary

            ### Data Overview
            - Dataset: {dataset_name}
            - Records: {record_count:,}
            - Columns: {column_count}
            - Date Range: {date_range}

            ### Key Statistics
            {key_statistics}

            ### Distribution Analysis
            {distribution_analysis}

            ### Data Quality
            {data_quality_summary}
            """,

            "trend_analysis": """
            ## Trend Analysis Report

            ### Trend Overview
            {trend_summary}

            ### Key Findings
            {key_trends}

            ### Seasonal Patterns
            {seasonal_analysis}

            ### Forecasting
            {forecast_summary}

            ### Recommendations
            {trend_recommendations}
            """,

            "comparative": """
            ## Comparative Analysis

            ### Comparison Summary
            {comparison_overview}

            ### Performance Metrics
            {performance_comparison}

            ### Statistical Significance
            {significance_testing}

            ### Key Differences
            {key_differences}

            ### Business Implications
            {business_implications}
            """
        }

    def _load_statistical_tests(self) -> Dict[str, Dict[str, Any]]:
        """Load statistical test configurations"""
        return {
            "normality": {
                "tests": ["shapiro_wilk", "kolmogorov_smirnov"],
                "threshold": 0.05,
                "interpretation": "Data distribution assessment"
            },
            "correlation": {
                "methods": ["pearson", "spearman", "kendall"],
                "threshold": 0.3,
                "interpretation": "Relationship strength between variables"
            },
            "comparison": {
                "tests": ["t_test", "mann_whitney", "chi_square"],
                "threshold": 0.05,
                "interpretation": "Statistical significance of differences"
            }
        }

    async def _execute_core_task(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> str:
        """Execute data analysis task"""

        # Parse analysis request
        analysis_request = await self._parse_analysis_request(task, kwargs)

        # Load and prepare data
        data = await self._load_data(analysis_request.data_sources, context)

        # Perform analysis based on type
        if analysis_request.analysis_type == AnalysisType.DESCRIPTIVE:
            result = await self._perform_descriptive_analysis(data, analysis_request, context)
        elif analysis_request.analysis_type == AnalysisType.TREND_ANALYSIS:
            result = await self._perform_trend_analysis(data, analysis_request, context)
        elif analysis_request.analysis_type == AnalysisType.COMPARATIVE:
            result = await self._perform_comparative_analysis(data, analysis_request, context)
        elif analysis_request.analysis_type == AnalysisType.PREDICTIVE:
            result = await self._perform_predictive_analysis(data, analysis_request, context)
        else:
            result = await self._perform_exploratory_analysis(data, analysis_request, context)

        # Generate insights and recommendations
        insights = await self._generate_insights(result, data, analysis_request, context)

        # Format final report
        report = await self._format_analysis_report(result, insights, analysis_request)

        return report

    async def _parse_analysis_request(
        self,
        task: str,
        kwargs: Dict[str, Any]
    ) -> AnalysisRequest:
        """Parse analysis request from natural language"""

        parsing_prompt = f"""
        Parse this data analysis request:

        Request: {task}
        Parameters: {json.dumps(kwargs)}

        Extract information in JSON format:
        {{
            "analysis_type": "descriptive|diagnostic|predictive|prescriptive|exploratory|comparative|trend_analysis",
            "questions": ["question1", "question2"],
            "metrics": ["metric1", "metric2"],
            "dimensions": ["dimension1", "dimension2"],
            "filters": {{}},
            "visualization_preferences": ["line_chart", "bar_chart"]
        }}
        """

        try:
            response = await self.generate_llm_response(
                parsing_prompt, TaskType.DATA_ANALYSIS
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed_request = json.loads(json_match.group())

                return AnalysisRequest(
                    analysis_type=AnalysisType(parsed_request.get("analysis_type", "descriptive")),
                    data_sources=[],  # Will be populated from kwargs
                    questions=parsed_request.get("questions", []),
                    metrics=parsed_request.get("metrics", []),
                    dimensions=parsed_request.get("dimensions", []),
                    filters=parsed_request.get("filters", {}),
                    visualization_preferences=[
                        ChartType(chart) for chart in parsed_request.get("visualization_preferences", [])
                    ]
                )

        except (json.JSONDecodeError, Exception):
            pass

        # Fallback parsing
        return AnalysisRequest(
            analysis_type=AnalysisType.DESCRIPTIVE,
            data_sources=[],
            questions=[task],
            metrics=[],
            dimensions=[],
            filters={},
            visualization_preferences=[]
        )

    async def _load_data(
        self,
        data_sources: List[DataSource],
        context: AgentContext
    ) -> Dict[str, pd.DataFrame]:
        """Load data from various sources"""

        # In production, this would load from:
        # - CSV files
        # - Database connections
        # - API endpoints
        # - Excel files
        # - JSON data

        # For now, simulate data loading
        datasets = {}

        # Generate sample business data
        sample_data = await self._generate_sample_data(context)
        datasets["business_metrics"] = sample_data

        return datasets

    async def _generate_sample_data(self, context: AgentContext) -> pd.DataFrame:
        """Generate realistic sample business data"""

        # Create sample business metrics data
        dates = pd.date_range(start='2023-01-01', end='2024-12-31', freq='D')

        np.random.seed(42)  # For reproducible results

        data = {
            'date': dates,
            'revenue': np.random.normal(10000, 2000, len(dates)) + np.sin(np.arange(len(dates)) * 2 * np.pi / 365) * 1000,
            'customers': np.random.poisson(50, len(dates)) + 20,
            'orders': np.random.poisson(100, len(dates)) + 30,
            'website_visits': np.random.normal(1000, 200, len(dates)),
            'conversion_rate': np.random.beta(2, 8, len(dates)),
            'customer_satisfaction': np.random.normal(4.2, 0.3, len(dates)),
            'product_category': np.random.choice(['A', 'B', 'C'], len(dates)),
            'region': np.random.choice(['North', 'South', 'East', 'West'], len(dates))
        }

        df = pd.DataFrame(data)

        # Add some trends and seasonality
        df['revenue'] = df['revenue'] + df.index * 5  # Growing trend
        df['customers'] = df['customers'] + np.sin(df.index * 2 * np.pi / 7) * 5  # Weekly pattern

        # Ensure positive values
        df['revenue'] = df['revenue'].clip(lower=1000)
        df['website_visits'] = df['website_visits'].clip(lower=100)
        df['conversion_rate'] = df['conversion_rate'].clip(lower=0.01, upper=0.5)
        df['customer_satisfaction'] = df['customer_satisfaction'].clip(lower=1, upper=5)

        return df

    async def _perform_descriptive_analysis(
        self,
        data: Dict[str, pd.DataFrame],
        request: AnalysisRequest,
        context: AgentContext
    ) -> AnalysisResult:
        """Perform descriptive statistical analysis"""

        primary_df = list(data.values())[0]

        # Calculate basic statistics
        statistics = {}
        numerical_cols = primary_df.select_dtypes(include=[np.number]).columns

        for col in numerical_cols:
            statistics[col] = {
                "mean": float(primary_df[col].mean()),
                "median": float(primary_df[col].median()),
                "std": float(primary_df[col].std()),
                "min": float(primary_df[col].min()),
                "max": float(primary_df[col].max()),
                "count": int(primary_df[col].count()),
                "missing": int(primary_df[col].isnull().sum())
            }

        # Generate insights
        insights = []

        # Revenue insights
        if 'revenue' in statistics:
            avg_revenue = statistics['revenue']['mean']
            insights.append(f"Average daily revenue is ${avg_revenue:,.2f}")

            revenue_growth = (primary_df['revenue'].tail(30).mean() - primary_df['revenue'].head(30).mean()) / primary_df['revenue'].head(30).mean() * 100
            insights.append(f"Revenue shows a {revenue_growth:.1f}% growth trend")

        # Customer insights
        if 'customers' in statistics:
            total_customers = statistics['customers']['mean'] * len(primary_df)
            insights.append(f"Estimated total customer base: {total_customers:,.0f}")

        # Conversion insights
        if 'conversion_rate' in statistics:
            avg_conversion = statistics['conversion_rate']['mean'] * 100
            insights.append(f"Average conversion rate: {avg_conversion:.2f}%")

        return AnalysisResult(
            summary="Descriptive analysis completed successfully",
            insights=insights,
            statistics=statistics,
            visualizations=[],
            recommendations=[
                "Monitor revenue trends for seasonal patterns",
                "Focus on improving conversion rate optimization",
                "Analyze customer acquisition costs"
            ],
            data_quality_issues=[],
            confidence_score=0.85,
            methodology="Descriptive statistical analysis using mean, median, standard deviation",
            limitations=["Analysis based on sample data", "Seasonal patterns may require longer time series"]
        )

    async def _perform_trend_analysis(
        self,
        data: Dict[str, pd.DataFrame],
        request: AnalysisRequest,
        context: AgentContext
    ) -> AnalysisResult:
        """Perform trend analysis"""

        primary_df = list(data.values())[0]

        # Ensure we have a date column
        if 'date' in primary_df.columns:
            primary_df = primary_df.set_index('date')

        insights = []
        statistics = {}

        # Analyze trends for numerical columns
        numerical_cols = primary_df.select_dtypes(include=[np.number]).columns

        for col in numerical_cols:
            # Calculate trend using linear regression slope
            x = np.arange(len(primary_df))
            y = primary_df[col].fillna(method='ffill')

            # Simple linear trend
            slope = np.polyfit(x, y, 1)[0]

            statistics[f"{col}_trend"] = {
                "slope": float(slope),
                "direction": "increasing" if slope > 0 else "decreasing",
                "strength": "strong" if abs(slope) > y.std() * 0.01 else "weak"
            }

            if slope > 0:
                insights.append(f"{col.replace('_', ' ').title()} shows an increasing trend")
            else:
                insights.append(f"{col.replace('_', ' ').title()} shows a decreasing trend")

        # Seasonal analysis
        if len(primary_df) >= 365:
            insights.append("Sufficient data available for seasonal analysis")

            # Weekly patterns
            if 'revenue' in primary_df.columns:
                primary_df['day_of_week'] = primary_df.index.dayofweek
                weekly_pattern = primary_df.groupby('day_of_week')['revenue'].mean()
                best_day = weekly_pattern.idxmax()
                insights.append(f"Revenue peaks on {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][best_day]}")

        return AnalysisResult(
            summary="Trend analysis reveals key patterns in business metrics",
            insights=insights,
            statistics=statistics,
            visualizations=[],
            recommendations=[
                "Continue monitoring positive trends",
                "Investigate factors driving trend changes",
                "Plan for seasonal variations"
            ],
            data_quality_issues=[],
            confidence_score=0.78,
            methodology="Linear trend analysis with seasonal decomposition",
            limitations=["Trend analysis assumes linear relationships", "External factors not considered"]
        )

    async def _perform_comparative_analysis(
        self,
        data: Dict[str, pd.DataFrame],
        request: AnalysisRequest,
        context: AgentContext
    ) -> AnalysisResult:
        """Perform comparative analysis"""

        primary_df = list(data.values())[0]

        insights = []
        statistics = {}

        # Compare by categories if available
        if 'product_category' in primary_df.columns and 'revenue' in primary_df.columns:
            category_comparison = primary_df.groupby('product_category')['revenue'].agg(['mean', 'std', 'count'])

            best_category = category_comparison['mean'].idxmax()
            worst_category = category_comparison['mean'].idxmin()

            statistics['category_comparison'] = category_comparison.to_dict()

            insights.append(f"Product category {best_category} has the highest average revenue")
            insights.append(f"Product category {worst_category} has the lowest average revenue")

            # Performance difference
            performance_diff = (category_comparison.loc[best_category, 'mean'] - category_comparison.loc[worst_category, 'mean']) / category_comparison.loc[worst_category, 'mean'] * 100
            insights.append(f"Top category outperforms bottom by {performance_diff:.1f}%")

        # Regional comparison if available
        if 'region' in primary_df.columns:
            regional_comparison = primary_df.groupby('region')['revenue'].agg(['mean', 'std', 'count'])
            statistics['regional_comparison'] = regional_comparison.to_dict()

            best_region = regional_comparison['mean'].idxmax()
            insights.append(f"Region {best_region} shows the strongest performance")

        return AnalysisResult(
            summary="Comparative analysis identifies performance variations across segments",
            insights=insights,
            statistics=statistics,
            visualizations=[],
            recommendations=[
                "Focus resources on high-performing segments",
                "Investigate success factors in top categories",
                "Develop improvement plans for underperforming areas"
            ],
            data_quality_issues=[],
            confidence_score=0.82,
            methodology="Comparative statistical analysis with grouping and aggregation",
            limitations=["Sample sizes may vary between groups", "Causal relationships not established"]
        )

    async def _perform_predictive_analysis(
        self,
        data: Dict[str, pd.DataFrame],
        request: AnalysisRequest,
        context: AgentContext
    ) -> AnalysisResult:
        """Perform predictive analysis"""

        primary_df = list(data.values())[0]

        insights = []
        statistics = {}

        # Simple forecasting using trend projection
        if 'revenue' in primary_df.columns:
            revenue_data = primary_df['revenue'].fillna(method='ffill')

            # Calculate trend
            x = np.arange(len(revenue_data))
            slope, intercept = np.polyfit(x, revenue_data, 1)

            # Project next 30 days
            future_days = 30
            future_x = np.arange(len(revenue_data), len(revenue_data) + future_days)
            forecast = slope * future_x + intercept

            statistics['revenue_forecast'] = {
                "next_30_days_avg": float(forecast.mean()),
                "trend_slope": float(slope),
                "confidence": "medium"  # Simple model, medium confidence
            }

            insights.append(f"Projected average daily revenue for next 30 days: ${forecast.mean():,.2f}")

            if slope > 0:
                insights.append("Revenue trend suggests continued growth")
            else:
                insights.append("Revenue trend suggests potential decline")

        # Customer growth prediction
        if 'customers' in primary_df.columns:
            customer_data = primary_df['customers'].fillna(method='ffill')
            customer_slope = np.polyfit(np.arange(len(customer_data)), customer_data, 1)[0]

            statistics['customer_growth'] = {
                "daily_growth_rate": float(customer_slope),
                "monthly_projection": float(customer_slope * 30)
            }

            insights.append(f"Customer base growing by approximately {customer_slope:.1f} customers per day")

        return AnalysisResult(
            summary="Predictive analysis provides forecasts based on historical trends",
            insights=insights,
            statistics=statistics,
            visualizations=[],
            recommendations=[
                "Monitor actual vs predicted values regularly",
                "Update forecasts with new data monthly",
                "Consider external factors that may impact predictions"
            ],
            data_quality_issues=["Simple linear model may not capture complex patterns"],
            confidence_score=0.65,  # Lower confidence for predictions
            methodology="Linear trend extrapolation for forecasting",
            limitations=["Linear model assumptions", "Does not account for external factors", "Accuracy decreases with time horizon"]
        )

    async def _perform_exploratory_analysis(
        self,
        data: Dict[str, pd.DataFrame],
        request: AnalysisRequest,
        context: AgentContext
    ) -> AnalysisResult:
        """Perform exploratory data analysis"""

        primary_df = list(data.values())[0]

        insights = []
        statistics = {}

        # Data overview
        statistics['data_overview'] = {
            "rows": len(primary_df),
            "columns": len(primary_df.columns),
            "memory_usage": primary_df.memory_usage(deep=True).sum(),
            "missing_values": primary_df.isnull().sum().sum()
        }

        insights.append(f"Dataset contains {len(primary_df):,} records with {len(primary_df.columns)} variables")

        # Missing data analysis
        missing_pct = (primary_df.isnull().sum() / len(primary_df) * 100)
        high_missing = missing_pct[missing_pct > 10]

        if len(high_missing) > 0:
            insights.append(f"{len(high_missing)} columns have more than 10% missing data")

        # Correlation analysis
        numerical_df = primary_df.select_dtypes(include=[np.number])
        if len(numerical_df.columns) > 1:
            correlation_matrix = numerical_df.corr()

            # Find strong correlations
            strong_correlations = []
            for i in range(len(correlation_matrix.columns)):
                for j in range(i+1, len(correlation_matrix.columns)):
                    corr_value = correlation_matrix.iloc[i, j]
                    if abs(corr_value) > 0.7:
                        col1, col2 = correlation_matrix.columns[i], correlation_matrix.columns[j]
                        strong_correlations.append((col1, col2, corr_value))

            if strong_correlations:
                for col1, col2, corr in strong_correlations:
                    insights.append(f"Strong correlation between {col1} and {col2}: {corr:.2f}")

            statistics['correlations'] = correlation_matrix.to_dict()

        # Outlier detection (simple method)
        outliers_detected = {}
        for col in numerical_df.columns:
            Q1 = numerical_df[col].quantile(0.25)
            Q3 = numerical_df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            outliers = numerical_df[(numerical_df[col] < lower_bound) | (numerical_df[col] > upper_bound)][col]
            outliers_detected[col] = len(outliers)

            if len(outliers) > 0:
                insights.append(f"{len(outliers)} potential outliers detected in {col}")

        return AnalysisResult(
            summary="Exploratory analysis reveals data patterns and relationships",
            insights=insights,
            statistics=statistics,
            visualizations=[],
            recommendations=[
                "Address missing data issues before further analysis",
                "Investigate outliers for data quality",
                "Consider feature engineering based on correlations"
            ],
            data_quality_issues=[f"Missing data in {len(high_missing)} columns" if len(high_missing) > 0 else ""],
            confidence_score=0.80,
            methodology="Exploratory data analysis with correlation and outlier detection",
            limitations=["Initial exploration only", "Further investigation needed for actionable insights"]
        )

    async def _generate_insights(
        self,
        analysis_result: AnalysisResult,
        data: Dict[str, pd.DataFrame],
        request: AnalysisRequest,
        context: AgentContext
    ) -> List[DataInsight]:
        """Generate business insights from analysis results"""

        insights = []

        # Convert analysis insights to structured format
        for i, insight_text in enumerate(analysis_result.insights):
            business_impact = "medium"  # Default

            # Determine business impact based on content
            if any(word in insight_text.lower() for word in ["revenue", "profit", "growth"]):
                business_impact = "high"
            elif any(word in insight_text.lower() for word in ["efficiency", "cost", "customer"]):
                business_impact = "medium"

            insights.append(DataInsight(
                title=f"Insight {i+1}",
                description=insight_text,
                significance="high" if "strong" in insight_text.lower() or "significant" in insight_text.lower() else "medium",
                supporting_data={"analysis_type": request.analysis_type.value},
                business_impact=business_impact,
                actionable=True
            ))

        return insights

    async def _format_analysis_report(
        self,
        result: AnalysisResult,
        insights: List[DataInsight],
        request: AnalysisRequest
    ) -> str:
        """Format the analysis report"""

        report = f"""
        📊 **DATA ANALYSIS REPORT**

        **Analysis Type:** {request.analysis_type.value.replace('_', ' ').title()}
        **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        **Confidence Score:** {result.confidence_score:.2f}

        ## Executive Summary
        {result.summary}

        ## Key Insights
        """

        for i, insight in enumerate(insights[:5], 1):  # Top 5 insights
            report += f"""
        **{i}. {insight.title}**
        - {insight.description}
        - Business Impact: {insight.business_impact.title()}
        - Significance: {insight.significance.title()}
        """

        report += f"""

        ## Statistical Summary
        """

        # Add key statistics
        for key, value in list(result.statistics.items())[:5]:  # Top 5 statistics
            if isinstance(value, dict):
                report += f"\n**{key.replace('_', ' ').title()}:**\n"
                for sub_key, sub_value in list(value.items())[:3]:  # Top 3 sub-items
                    if isinstance(sub_value, (int, float)):
                        report += f"- {sub_key.replace('_', ' ').title()}: {sub_value:,.2f}\n"
                    else:
                        report += f"- {sub_key.replace('_', ' ').title()}: {sub_value}\n"
            else:
                report += f"- {key.replace('_', ' ').title()}: {value}\n"

        report += f"""

        ## Recommendations
        """

        for i, recommendation in enumerate(result.recommendations, 1):
            report += f"{i}. {recommendation}\n"

        report += f"""

        ## Methodology & Limitations
        **Methodology:** {result.methodology}

        **Limitations:**
        """

        for limitation in result.limitations:
            report += f"- {limitation}\n"

        if result.data_quality_issues:
            report += f"""

        ## Data Quality Issues
        """
            for issue in result.data_quality_issues:
                if issue:  # Skip empty issues
                    report += f"- {issue}\n"

        report += f"""

        ---
        *Report generated by {self.config.name} - AgentOS Data Analytics*
        """

        return report

    async def create_dashboard_summary(
        self,
        data: Dict[str, pd.DataFrame],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Create a dashboard summary with key metrics"""

        primary_df = list(data.values())[0]

        # Calculate KPIs
        kpis = {}

        if 'revenue' in primary_df.columns:
            kpis['total_revenue'] = primary_df['revenue'].sum()
            kpis['avg_daily_revenue'] = primary_df['revenue'].mean()
            kpis['revenue_trend'] = (primary_df['revenue'].tail(7).mean() - primary_df['revenue'].head(7).mean()) / primary_df['revenue'].head(7).mean() * 100

        if 'customers' in primary_df.columns:
            kpis['total_customers'] = primary_df['customers'].sum()
            kpis['avg_daily_customers'] = primary_df['customers'].mean()

        if 'conversion_rate' in primary_df.columns:
            kpis['avg_conversion_rate'] = primary_df['conversion_rate'].mean() * 100

        # Top insights
        insights = [
            f"Revenue trending {'up' if kpis.get('revenue_trend', 0) > 0 else 'down'} by {abs(kpis.get('revenue_trend', 0)):.1f}%",
            f"Average daily revenue: ${kpis.get('avg_daily_revenue', 0):,.2f}",
            f"Conversion rate: {kpis.get('avg_conversion_rate', 0):.2f}%"
        ]

        return {
            "kpis": kpis,
            "insights": insights,
            "data_freshness": datetime.now().isoformat(),
            "record_count": len(primary_df)
        }

    def _get_tool_function(self, tool_name: str):
        """Get data analyzer specific tool functions"""
        tools = {
            "statistical_analyzer": self._perform_descriptive_analysis,
            "trend_detector": self._perform_trend_analysis,
            "visualization_generator": self._generate_visualizations,
            "insight_extractor": self._generate_insights
        }
        return tools.get(tool_name)

    async def _generate_visualizations(
        self,
        data: Dict[str, pd.DataFrame],
        chart_types: List[ChartType]
    ) -> List[Dict[str, Any]]:
        """Generate visualization configurations"""

        # In production, this would generate actual charts using:
        # - Plotly
        # - Matplotlib
        # - Seaborn
        # - D3.js configurations

        visualizations = []
        primary_df = list(data.values())[0]

        for chart_type in chart_types:
            if chart_type == ChartType.LINE_CHART and 'date' in primary_df.columns:
                visualizations.append({
                    "type": "line_chart",
                    "title": "Revenue Trend Over Time",
                    "x_axis": "date",
                    "y_axis": "revenue",
                    "config": {"responsive": True, "height": 400}
                })

            elif chart_type == ChartType.BAR_CHART and 'product_category' in primary_df.columns:
                visualizations.append({
                    "type": "bar_chart",
                    "title": "Revenue by Product Category",
                    "x_axis": "product_category",
                    "y_axis": "revenue",
                    "config": {"responsive": True, "height": 300}
                })

        return visualizations