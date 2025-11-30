# app/services/portfolio_service.py
from typing import Dict, List, Optional
import openai
from openai import AsyncOpenAI, AsyncAzureOpenAI
import asyncio
from ..config import Settings, capability_content
from ..utils.text_processing import extract_sections, generate_title
from ..utils.capabilities import parse_capabilities, format_capabilities
from ..models import CaseReviewResponse, CaseReviewSection

class PortfolioService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai_client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version
        )
        self.capabilities = parse_capabilities(capability_content)

    async def generate_case_review(
        self,
        case_description: str,
        selected_capabilities: List[str]
    ) -> CaseReviewResponse:
        import time
        start_time = time.time()
        try:
            print("🔵 Step 1: Formatting capabilities...")
            step_start = time.time()
            formatted_capabilities = format_capabilities(selected_capabilities)
            print(f"   ⏱️  Step 1 took {time.time() - step_start:.2f}s")
            
            print("🔵 Step 2: Building messages...")
            step_start = time.time()
            messages = [
                {
                    "role": "system",
                    "content": self.settings.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"""Input Data:
{case_description}

Task:
Please convert the notes above into a formal RCGP Clinical Case Review.

Selected Capabilities:
{formatted_capabilities}"""
                }
            ]
            print(f"   ⏱️  Step 2 took {time.time() - step_start:.2f}s")
            
            print(f"🔵 Step 3: Calling LLM...")
            print(f"   Model/Deployment: {self.settings.azure_openai_deployment}")
            print(f"   Endpoint: {self.settings.azure_openai_endpoint}")
            print(f"   API Version: {self.settings.azure_openai_api_version}")
            print(f"   Max Tokens: {self.settings.max_tokens}")
            print(f"   Temperature: {self.settings.temperature}")
            step_start = time.time()
            completion = await self.openai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature
            )
            llm_time = time.time() - step_start
            print(f"   ⏱️  Step 3 (LLM call) took {llm_time:.2f}s")
            
            print("🔵 Step 4: LLM response received, processing content...")
            step_start = time.time()
            review_content = completion.choices[0].message.content
            print(f"🔵 Step 4b: Content length: {len(review_content)} chars")
            print(f"\n{'='*80}")
            print("📄 RAW REVIEW OUTPUT:")
            print(f"{'='*80}")
            print(review_content)
            print(f"{'='*80}\n")
            review_content = review_content.replace('*', '').replace('#', '')
            print(f"   ⏱️  Step 4 took {time.time() - step_start:.2f}s")

            print("🔵 Step 5: Extracting sections...")
            step_start = time.time()
            sections = extract_sections(review_content, selected_capabilities)
            print(f"🔵 Step 5a: Sections extracted: {list(sections.keys())}")
            print(f"🔵 Step 5b: Brief description length: {len(sections.get('brief_description', ''))} chars")
            print(f"   ⏱️  Step 5 took {time.time() - step_start:.2f}s")
            
            print("🔵 Step 6: Generating title...")
            step_start = time.time()
            case_title = await generate_title(sections["brief_description"], self.openai_client, self.settings)
            print(f"🔵 Step 6a: Title generated: '{case_title}'")
            print(f"   ⏱️  Step 6 took {time.time() - step_start:.2f}s")

            print("🔵 Step 7: Creating response object...")
            step_start = time.time()
            response = CaseReviewResponse(
                case_title=case_title,
                review_content=review_content,
                sections=CaseReviewSection(**sections)
            )
            print(f"   ⏱️  Step 7 took {time.time() - step_start:.2f}s")
            
            total_time = time.time() - start_time
            print("✅ Step 8: Response created successfully!")
            print(f"⏱️  TOTAL TIME: {total_time:.2f}s ({total_time/60:.2f} minutes)")
            
            return response

        except Exception as e:
            import traceback
            print(f"❌ Error in generate_case_review: {str(e)}")
            print(f"❌ Traceback: {traceback.format_exc()}")
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
                    "content": f"""

                    You are an AI assistant helping to improve GP portfolio entries.
                    Your task is to enhance specific aspects of case reviews while maintaining the overall structure and other content.
                    
                    Guidelines:
                    1. Only modify content specifically related to the requested improvement
                    2. Maintain the same level of professionalism and medical accuracy
                    3. Keep the same structure and sections (always include the same sections and ensure they are all populated)
                    4. Ensure improvements are specific and evidence-based
                    5. Preserve any existing good content not related to the improvement request
                    6. For demographic corrections, ensure all pronouns and references are updated consistently throughout
                    
                    IMPORTANT: 
                    1. Only modify sections specifically related to the requested improvement, other sections should be kept exactly the same
                    2. Keep all other content exactly the same
                    3. Maintain the same structure and section headings
                    4. Ensure the improvements are specific and detailed
                    5. Write in British English not American
                    
                    Current case review:
                    {original_case}
                    
                    Requested improvement:
                    {improvement_prompt}
                    
                    Selected capabilities to focus on:
                    {formatted_capabilities}
                    """
                }
            ]

            print(f"🔵 Calling LLM for improvement...")
            print(f"   Model/Deployment: {self.settings.azure_openai_deployment}")
            print(f"   Max Tokens: {self.settings.max_tokens}")
            print(f"   Temperature: {self.settings.temperature}")
            response = await self.openai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature
            )

            improved_content = response.choices[0].message.content
            improved_content = improved_content.replace('*', '').replace('#', '')

            sections = extract_sections(improved_content, selected_capabilities)
            
            if "brief_description" in improvement_prompt.lower():
                case_title = await generate_title(sections["brief_description"], self.openai_client, self.settings)
            else:
                case_title = await generate_title(original_case.split("\n")[0], self.openai_client, self.settings)

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
            if not capabilities:
                raise Exception("No capabilities were parsed")
            # Return directly without wrapping in another dict
            return capabilities
        except Exception as e:
            raise Exception(f"Error getting capabilities: {str(e)}")

    async def improve_section(
        self,
        section_type: str,
        section_content: str,
        improvement_prompt: str,
        capability_name: Optional[str] = None
    ) -> str:
        try:
            # Build the system prompt based on section type
            system_prompt = """You are an AI assistant helping to improve specific sections of GP portfolio entries.
            Focus only on improving the requested section while maintaining professional medical language and specific, actionable content."""
            
            # Add section-specific guidance
            if section_type == "brief_description":
                system_prompt += "\nFor brief descriptions: Focus on clarity, structure, and key clinical details."
            elif section_type == "capability":
                system_prompt += "\nFor capabilities: Ensure clear links between actions and the specific capability."
            elif section_type == "reflection":
                system_prompt += "\nFor reflections: Include both clinical and emotional aspects, what went well, and areas for improvement."
            elif section_type == "learning_needs":
                system_prompt += "\nFor learning needs: Be specific about knowledge gaps and actionable learning objectives."
            
            user_content = f"""
            Section type: {section_type}"""

            if section_type == "capability" and capability_name:
                capability_description = globals().get(capability_name.replace(" ", "_"), "")
                user_content += f"""
                Capability: {capability_name}
                
                Capability Description:
                {capability_description}"""

            user_content += f"""
            The user is asking for an improvement to the following section of a GP portfolio entry:

            Current section content:
            {section_content}
            
            Improvement request:
            {improvement_prompt}
            
            Please provide an improved version of this section only, the improved section should be in the same format as the current content but only with the improvements requested.
            Maintain professional medical language and be specific. 
            Only return the improved section, do not include any other text.
            Write in British English not American.
            Make sure the output sounds natural and doesn't directly refer to the improvement request.
            """

            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]

            print(f"🔵 Calling LLM for section improvement...")
            print(f"   Model/Deployment: {self.settings.azure_openai_deployment}")
            print(f"   Section Type: {section_type}")
            completion = await self.openai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature
            )
            
            improved_content = completion.choices[0].message.content
            return improved_content.strip()

        except Exception as e:
            raise Exception(f"Error improving section: {str(e)}")

    async def select_capabilities_for_case(self, case_description: str) -> List[str]:
        """
        Use LLM to intelligently select 2-3 most relevant capabilities for a case.
        """
        try:
            system_prompt = """You are an expert RCGP (Royal College of General Practitioners) assessor. 
Your task is to analyze a clinical case description and select the 2-3 most relevant capabilities 
from the RCGP curriculum that are clearly demonstrated in the case.

Guidelines:
1. Select only capabilities with clear evidence in the case description
2. Choose 2-3 capabilities (not more, not less than 2)
3. Prioritize capabilities that are most prominently demonstrated
4. Return ONLY the capability names, one per line, exactly as listed
5. Do not add explanations or numbering"""

            user_prompt = f"""Available RCGP Capabilities:

{capability_content}

---

Case Description:
{case_description}

---

Based on the case description above, select the 2-3 most relevant capabilities that are clearly demonstrated. 
Return only the capability names, one per line, exactly as they appear in the list above."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            print(f"🔵 Calling LLM for capability selection...")
            print(f"   Model/Deployment: {self.settings.azure_openai_deployment}")
            print(f"   Max Tokens: 200, Temperature: 0.3")
            completion = await self.openai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_tokens=200,
                temperature=0.3  # Lower temperature for more consistent selection
            )

            response_content = completion.choices[0].message.content.strip()
            
            # Parse the response to extract capability names
            selected_capabilities = []
            for line in response_content.split('\n'):
                line = line.strip()
                # Remove any numbering or bullet points
                line = line.lstrip('0123456789.-• ')
                if line and line in self.capabilities:
                    selected_capabilities.append(line)
            
            # Ensure we have 1-3 capabilities
            if not selected_capabilities:
                raise Exception("No valid capabilities were selected by AI")
            
            # Limit to 2-3 capabilities
            selected_capabilities = selected_capabilities[:3]
            
            return selected_capabilities

        except Exception as e:
            raise Exception(f"Error selecting capabilities: {str(e)}")

    async def select_experience_groups(self, case_description: str) -> List[str]:
        """
        Use LLM to select 1-2 Clinical Experience Groups based on the case context.
        Uses the exact prompt from exp_group.prompty.
        """
        try:
            system_prompt = """
            You are an expert Medical Educational Assistant for the 'fourteenfishermen' GP portfolio tool. Your task is to analyze a Clinical Case Log written by a General Practitioner trainee and categorize it into the correct *Clinical Experience Group(s)*.

*CORE INSTRUCTIONS:*
1.  *Analyze Context over Diagnosis:* Do not classify based solely on the medical condition. You must look at the context (patient age, social setting, vulnerability, urgency, and the specific focus of the trainee's reflection).
2.  *Select 1-2 Groups:* Ideally, select *two* groups if the case touches on multiple aspects (e.g., a child with a mental health issue). If only one fits, select one.
3.  *Strict Fallback:* Only use "Clinical problems not linked to a specific clinical experience group" if *absolutely none* of the specific groups apply. This should be infrequent.

*DEFINITIONS OF CLINICAL EXPERIENCE GROUPS:*
1.  *Infants, children and young people (under 19):* Patients <19 years (includes students, parents of young children).
2.  *Gender, reproductive and sexual health:* Women’s/men’s health, LGBTQ+, gynaecology, breast, sexual health/BBV.
3.  *People with long-term conditions:* Cancer, multi-morbidity, disability, chronic illness (diabetes, asthma, etc.).
4.  *Older adults:* Frailty, end-of-life, complex care in >65s.
5.  *Mental health:* Addiction, alcohol, substance misuse, anxiety, depression, health anxiety.
6.  *Urgent and unscheduled care:* Acute/septic presentations, A&E, OOH hubs, same-day triage.
7.  *People with health disadvantage and vulnerabilities:* Veterans, asylum seekers, learning disabilities, safeguarding, capacity issues, sensory impairment (deaf/blind).
8.  *Population Health and health promotion:* Prevention, lifestyle advice, self-management, screening.
9.  *Clinical problems not linked to a specific clinical experience group:* Fallback only.

CRITICAL AGE CONSTRAINT: The age limit of "under 19" is absolute. Any patient aged 19 years or older is STRICTLY excluded from the "Infants, children and young people" group.

*EXTENSIVE REASONING EXAMPLES (Use these to guide your logic):*

*Scenario: Patient with Vertigo*
•⁠  ⁠If context is: History of breast cancer raising suspicion of brain metastasis.
    * -> *People with long term conditions including cancer, multi-morbidity and disability*
•⁠  ⁠If context is: Acute onset, unwell, seen in urgent care setting.
    * -> *Urgent and unscheduled care*
•⁠  ⁠If context is: Elderly/frail patient with capacity difficulties explaining symptoms.
    * -> *Older adults including frailty* AND *People with health disadvantage and vulnerabilities*
•⁠  ⁠If context is: Empowering patient to self-manage symptoms/driving advice.
    * -> *Population Health and health promotion*

*Scenario: Patient with Diabetes*
•⁠  ⁠If context is: Pregnant patient with recurrent thrush/complications.
    * -> *People with long term conditions* AND *Gender, reproductive and sexual health*
•⁠  ⁠If context is: Patient has a learning disability limiting medication compliance.
    * -> *People with health disadvantage and vulnerabilities* AND *People with long term conditions*
•⁠  ⁠If context is: Mental health prevents understanding of medication needs.
    * -> *Mental health (including addiction...)* AND *People with long term conditions*
•⁠  ⁠If context is: New diagnosis in a teenager.
    * -> *Infants, children and young people* AND *People with long term conditions*

*Scenario: Heroin Addict*
•⁠  ⁠If context is: Septic admission seen in same-day access.
    * -> *Urgent and unscheduled care* AND *Mental health (including addiction...)*
•⁠  ⁠If context is: Safeguarding children of the patient.
    * -> *Infants, children and young people* AND *People with health disadvantage and vulnerabilities*
•⁠  ⁠If context is: Sexual implications/Blood-borne virus.
    * -> *Mental health (including addiction...)* AND *Gender, reproductive and sexual health*

*Scenario: Suspected Skin Cancer*
•⁠  ⁠If context is: Melanoma on penis affecting men's health.
    * -> *Gender, reproductive and sexual health* AND *People with long term conditions (cancer)*
•⁠  ⁠If context is: Bedbound patient who previously had a stroke.
    * -> *Older adults including frailty* AND *People with long term conditions*
•⁠  ⁠If context is: Patient has significant health anxiety about the mole.
    * -> *Mental health (including addiction...)*
•⁠  ⁠If context is: Veteran/Naval officer with history of sun exposure abroad.
    * -> *People with health disadvantage and vulnerabilities (veterans)*

*Scenario: Rash (Lyme Disease Concern)*
•⁠  ⁠If context is: Learning disability, attending with carer, capacity issues.
    * -> *People with health disadvantage and vulnerabilities*
•⁠  ⁠If context is: Health promotion on tick prevention.
    * -> *Population Health and health promotion*

*Scenario: Altered Bowel Habit / IBS*
•⁠  ⁠If context is: Deaf patient relying on sign language/interpreter.
    * -> *People with health disadvantage and vulnerabilities*
•⁠  ⁠If context is: Young person (18yo) with family history.
    * -> *Infants, children and young people*
•⁠  ⁠If context is: Older woman, checking CA125 (ovarian cancer risk).
    * -> *Gender, reproductive and sexual health* AND *Older adults including frailty*

*Scenario: Persistent Cough*
•⁠  ⁠If context is: Toddler at nursery with viral illnesses.
    * -> *Infants, children and young people*
•⁠  ⁠If context is: Veteran with previous asbestos exposure in Navy.
    * -> *People with health disadvantage and vulnerabilities*
•⁠  ⁠If context is: History of substance misuse leading to appointment.
    * -> *Mental health (including addiction...)*
            
            """

            print("🟣 Step 1: Building experience groups prompt...")
            user_prompt = f"""Input Log:
{case_description}

Task:
Identify the 1 or 2 most appropriate Clinical Experience Groups based on the specific focus of the reflection above. Return ONLY the group names as a list, one per line."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            print(f"🟣 Step 2: Calling LLM for experience groups...")
            print(f"   Model/Deployment: {self.settings.azure_openai_deployment}")
            print(f"   Max Tokens: 200, Temperature: 0.1")
            completion = await self.openai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_tokens=200,
                temperature=0.1  # Low temperature for consistent classification
            )

            print("🟣 Step 3: LLM response received for experience groups")
            response_content = completion.choices[0].message.content.strip()
            print(f"🟣 Step 4: Raw experience group response: {response_content}")
            
            # Valid experience groups - using shortened names from prompty
            valid_groups = [
                "Infants, children and young people (under 19)",
                "Gender, reproductive and sexual health",
                "People with long-term conditions",
                "Older adults",
                "Mental health",
                "Urgent and unscheduled care",
                "People with health disadvantage and vulnerabilities",
                "Population Health and health promotion",
                "Clinical problems not linked to a specific clinical experience group"
            ]
            
            # Parse the response to extract group names
            selected_groups = []
            for line in response_content.split('\n'):
                line = line.strip()
                # Remove any numbering, bullet points, or asterisks
                line = line.lstrip('0123456789.-•* ')
                line = line.rstrip('*')
                
                # Check if this line matches any valid group
                for valid_group in valid_groups:
                    # Strict matching: The line must CONTAIN the full valid group name
                    if valid_group.lower() in line.lower():
                        if valid_group not in selected_groups:
                            selected_groups.append(valid_group)
                        break
            
            # Limit to 2 groups
            selected_groups = selected_groups[:2]
            
            # Fallback if no groups found
            if not selected_groups:
                selected_groups = ["Clinical problems not linked to a specific clinical experience group"]
            
            return selected_groups

        except Exception as e:
            raise Exception(f"Error selecting experience groups: {str(e)}")