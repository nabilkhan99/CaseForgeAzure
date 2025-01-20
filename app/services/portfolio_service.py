# app/services/portfolio_service.py
from typing import Dict, List, Optional
import openai
from openai import OpenAI, AsyncOpenAI
import asyncio
from ..config import Settings, capability_content
from ..utils.text_processing import extract_sections, generate_title
from ..utils.capabilities import parse_capabilities, format_capabilities
from ..models import CaseReviewResponse, CaseReviewSection

class PortfolioService:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Use sync client for non-async operations
        self.openai_client = OpenAI(
            api_key=settings.openai_api_key,
            base_url="https://api.openai.com/v1"
        )
        self.capabilities = parse_capabilities(capability_content)

    async def generate_case_review(
        self,
        case_description: str,
        selected_capabilities: List[str]
    ) -> CaseReviewResponse:
        try:
            formatted_capabilities = format_capabilities(selected_capabilities)
            
            messages = [
                {
                    "role": "system",
                    "content": self.settings.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": self.settings.EXAMPLE_1
                },
                {
                    "role": "assistant",
                    "content": self.settings.EXAMPLE_1_RESPONSE
                },
                {
                    "role": "user",
                    "content": self.settings.EXAMPLE_2
                },
                {
                    "role": "assistant",
                    "content": self.settings.EXAMPLE_2_RESPONSE
                },
                {
                    "role": "user",
                    "content": f"""Generate a structured case review with the following:
                {self.settings.MAIN_PROMPT.format(
                    formatted_capabilities=formatted_capabilities,
                    case_description=case_description
                )}"""
                }
            ]

            

            # Use sync client in async context
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model=self.settings.openai_model,
                messages=messages,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature
            )

            review_content = response.choices[0].message.content
            review_content = review_content.replace('*', '').replace('#', '')

            sections = extract_sections(review_content, selected_capabilities)
            
            # Use sync client for title generation
            title_response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model=self.settings.openai_model,
                messages=[{
                    "role": "system",
                    "content": "Generate a brief (4-6 words) medical case title."
                }, {
                    "role": "user",
                    "content": f"Create a title for: {case_description}"
                }],
                max_tokens=50,
                temperature=0.7
            )
            case_title = title_response.choices[0].message.content.strip().replace('"', '')

            return CaseReviewResponse(
                case_title=case_title,
                review_content=review_content,
                sections=CaseReviewSection(**sections)
            )

        except Exception as e:
            raise Exception(f"Error generating case review: {str(e)}")

    # async def improve_case_review(
    #     self,
    #     original_case: str,
    #     improvement_prompt: str,
    #     selected_capabilities: List[str]
    # ) -> CaseReviewResponse:
    #     try:
    #         messages = [
    #             {
    #                 "role": "system",
    #                 "content": """You are an AI assistant helping to improve GP portfolio entries. 
    #                  IMPORTANT: Only modify the specific aspects mentioned in the improvement request. 
    #                  Keep all other content exactly the same."""
    #             },
    #             {
    #                 "role": "user", 
    #                 "content": f"""Current case review:
    #                 {original_case}
                    
    #                 Requested improvement:
    #                 {improvement_prompt}
                    
    #                 IMPORTANT: Only modify content specifically related to the requested improvement.
    #                 Keep all other content exactly the same."""
    #             }
    #         ]

    #         response = await asyncio.to_thread(
    #             self.openai_client.chat.completions.create,
    #             model="gpt-4",
    #             messages=messages,
    #             max_tokens=4000,
    #             temperature=0.7
    #         )

    #         improved_content = response.choices[0].message.content
    #         improved_content = improved_content.replace('*', '').replace('#', '')

    #         sections = extract_sections(improved_content, selected_capabilities)
    #         case_title = await generate_title(sections["brief_description"])

    #         return CaseReviewResponse(
    #             case_title=case_title,
    #             review_content=improved_content,
    #             sections=CaseReviewSection(**sections)
    #         )

    #     except Exception as e:
    #         raise Exception(f"Error improving case review: {str(e)}")

    async def improve_case_review(
        self,
        original_case: str,
        improvement_prompt: str,
        selected_capabilities: List[str]
    ) -> CaseReviewResponse:
        try:
            formatted_capabilities = format_capabilities(selected_capabilities)
            
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI assistant helping to improve GP portfolio entries.
                    Your task is to enhance specific aspects of case reviews while maintaining the overall structure and other content.
                    
                    Guidelines:
                    1. Only modify content specifically related to the requested improvement
                    2. Maintain the same level of professionalism and medical accuracy
                    3. Keep the same structure and sections
                    4. Ensure improvements are specific and evidence-based
                    5. Preserve any existing good content not related to the improvement request
                    6. For demographic corrections, ensure all pronouns and references are updated consistently throughout"""
                },
                {
                    "role": "user",
                    "content": self.settings.IMPROVEMENT_EXAMPLE_1
                },
                {
                    "role": "user",
                    "content": self.settings.IMPROVEMENT_REQUEST_1
                },
                {
                    "role": "assistant",
                    "content": self.settings.IMPROVEMENT_RESPONSE_1
                },
                {
                    "role": "user",
                    "content": self.settings.IMPROVEMENT_EXAMPLE_2
                },
                {
                    "role": "user",
                    "content": self.settings.IMPROVEMENT_REQUEST_2
                },
                {
                    "role": "assistant",
                    "content": self.settings.IMPROVEMENT_RESPONSE_2
                },
                {
                    "role": "user",
                    "content": self.settings.IMPROVEMENT_EXAMPLE_3
                },
                {
                    "role": "user",
                    "content": self.settings.IMPROVEMENT_REQUEST_3
                },
                {
                    "role": "assistant",
                    "content": self.settings.IMPROVEMENT_RESPONSE_3
                },
                {
                    "role": "user",
                    "content": f"""Current case review:
                    {original_case}
                    
                    Requested improvement:
                    {improvement_prompt}
                    
                    Selected capabilities to focus on:
                    {formatted_capabilities}
                    
                    IMPORTANT: 
                    1. Only modify sections specifically related to the requested improvement
                    2. Keep all other content exactly the same
                    3. Maintain the same structure and section headings
                    4. Ensure the improvements are specific and detailed"""
                }
            ]

            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model=self.settings.openai_model,  # Using the same model as generate_case_review
                messages=messages,
                max_tokens=self.settings.max_tokens,
                temperature=0.7
            )

            improved_content = response.choices[0].message.content
            improved_content = improved_content.replace('*', '').replace('#', '')

            sections = extract_sections(improved_content, selected_capabilities)
            
            # Only generate new title if the brief description was modified
            if "brief_description" in improvement_prompt.lower():
                case_title = await generate_title(sections["brief_description"])
            else:
                case_title = await generate_title(original_case.split("\n")[0])  # Use original title

            return CaseReviewResponse(
                case_title=case_title,
                review_content=improved_content,
                sections=CaseReviewSection(**sections)
            )

        except Exception as e:
            raise Exception(f"Error improving case review: {str(e)}")


    
    async def get_capabilities(self) -> Dict[str, List[str]]:
        """Return parsed capabilities dictionary."""
        try:
            capabilities = parse_capabilities(capability_content)
            # Add debug logging
            print(f"Parsed capabilities: {capabilities}")  # Temporary debug print
            if not capabilities:
                raise Exception("No capabilities were parsed")
            # Return directly without wrapping in another dict
            return capabilities
        except Exception as e:
            raise Exception(f"Error getting capabilities: {str(e)}")