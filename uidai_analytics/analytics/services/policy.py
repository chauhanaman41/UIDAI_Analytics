import json
import logging
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

logger = logging.getLogger(__name__)

class Recommendation(BaseModel):
    district: str = Field(description="Name of the district")
    recommendation: str = Field(description="Primary intervention strategy")
    rationale: str = Field(description="Reasoning based on context")
    impact_estimate: str = Field(description="Quantified expected impact")
    cost_category: str = Field(description="Low, Medium, or High")
    priority: str = Field(description="High, Medium, or Low")

class PolicyOutput(BaseModel):
    recommendations: List[Recommendation]

def generate_policy_recommendations(problem_districts: list, model_name: str = "llama3") -> list:
    """
    Generates policy recommendations for a list of problem districts.
    """
    if not problem_districts:
        return []

    try:
        llm = Ollama(model=model_name, temperature=0.3)
        parser = JsonOutputParser(pydantic_object=PolicyOutput)

        template = """
        You are a policy expert for digital inclusion in India.
        
        Analyze the following problem districts and suggest interventions.
        
        PROBLEM DISTRICTS:
        {problem_districts}
        
        TASK:
        For each district, provide a targeted recommendation considering:
        1. Infrastructure constraints
        2. Literacy levels
        3. Geographic accessibility
        4. Budget efficiency
        
        FORMAT INSTRUCTIONS:
        {format_instructions}
        """

        prompt = PromptTemplate(
            template=template,
            input_variables=["problem_districts"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        chain = prompt | llm | parser

        logger.info(f"Generating policy recommendations for {len(problem_districts)} districts...")
        result = chain.invoke({"problem_districts": json.dumps(problem_districts, indent=2)})
        
        return result.get("recommendations", [])

    except Exception as e:
        logger.error(f"Error generating policy recommendations: {e}")
        return []
