import json
import logging
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

logger = logging.getLogger(__name__)

# Define the output structure
class InsightsOutput(BaseModel):
    executive_summary: str = Field(description="3-sentence executive summary for policymakers")
    key_findings: List[str] = Field(description="3 key findings with supporting data")
    risk_alerts: List[str] = Field(description="Top 2 risks requiring immediate attention")
    recommendations: List[str] = Field(description="3 actionable recommendations")

def generate_insights(metrics_data: dict, model_name: str = "llama3") -> dict:
    """
    Generates natural language insights from analytics data using Ollama.
    """
    try:
        # Initialize LLM (Ollama)
        llm = Ollama(model=model_name, temperature=0.2) # Low temp for factual consistency
        
        # Define Parser
        parser = JsonOutputParser(pydantic_object=InsightsOutput)
        
        # Define Prompt
        template = """
        You are an expert analyst for India's Aadhaar enrollment system.
        
        Analyze the following metrics data and provide a professional, data-driven report.
        
        DATA:
        {metrics_data}
        
        TASK:
        1. Write a 3-sentence executive summary for policymakers.
        2. List 3 key findings with supporting data.
        3. Identify top 2 risks requiring immediate attention.
        4. Suggest 3 actionable recommendations.
        
        FORMAT INSTRUCTIONS:
        {format_instructions}
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["metrics_data"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        # Chain
        chain = prompt | llm | parser
        
        # Execute
        logger.info(f"Generating insights with model {model_name}...")
        result = chain.invoke({"metrics_data": json.dumps(metrics_data, indent=2)})
        
        logger.info("Insights generation successful")
        return result
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        # Fallback response in case of LLM failure
        return {
            "executive_summary": "Automated insight generation failed. Please review the raw data.",
            "key_findings": ["Error processing data for insights."],
            "risk_alerts": ["System error in AI module."],
            "recommendations": ["Check Ollama service status.", "Verify data format."]
        }
