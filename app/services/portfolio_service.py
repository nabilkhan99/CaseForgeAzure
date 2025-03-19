# app/services/portfolio_service.py
from typing import Dict, List, Optional
import openai
from openai import AsyncOpenAI, AsyncAzureOpenAI
import asyncio
from ..config import Settings, capability_content
from ..utils.text_processing import extract_sections, generate_title
from ..utils.capabilities import parse_capabilities, format_capabilities
from ..models import CaseReviewResponse, CaseReviewSection


Fitnes_to_practise = """
- This is about professionalism and the actions expected to protect people from harm. This includes the awareness of when an individual's performance, conduct or health, or that of others, might put patients, themselves or their colleagues at risk.
- Understands the GMC document, "Duties of a Doctor".
- Attends to their professional duties.
- Awareness that physical or mental illness, or personal habits, might interfere with the competent delivery of patient care.
- Identifies and notifies an appropriate person when their own or a colleague's performance, conduct or health might be putting others at risk.
- Responds to complaints or performance issues appropriately."""

Maintaining_an_ethical_approach = """
- This is about practising ethically with integrity and a respect for equality and diversity.
- Awareness of the professional codes of practice as described in the GMC document "Good Medical Practice".
- Understands the need to treat everyone with respect for their beliefs, preferences, dignity and rights.
- Recognises that people are different and does not discriminate against them because of those differences.
- Understands that "Good Medical Practice" requires reference to ethical principles."""

Communication_and_consultation_skills = """
- This is about communication with patients, the use of recognised consultation techniques, establishing patient partnership, managing challenging consultations, third-party consultations and the use of interpreters.
- Develops a working relationship with the patient, but one in which the problem rather than the person is the focus.
- Uses a rigid or formulaic approach to achieve the main tasks of the consultation.
- Provides explanations that are relevant and understandable to the patient, using appropriate language.
- The use of language is technically correct but not well adapted to the needs and characteristics of the patient.
- Provides explanations that are medically correct but doctor-centred.
- Communicates management plans but without negotiating with, or involving, the patient.
- Consults to an acceptable standard but lacks focus and requires longer consulting times.
- Aware of when there is a language barrier and can access interpreters either in person or by telephone."""

Data_gathering_and_interpretation = """
- This is about the gathering, interpretation, and use of data for clinical judgement, including information gathered from the history, clinical records, examination and investigations.
- Accumulates information from the patient that is relevant to their problem.
- Uses existing information in the patient records.
- Employs examinations and investigations that are in line with the patient's problems.
- Identifies abnormal findings and results."""

Clinical_examination_and_procedural_skills = """
- This is about clinical examination and procedural skills. By the end of training, the trainee must have demonstrated competence in general and systemic examinations of all of the clinical curriculum areas, this includes the 5 mandatory examinations and a range of skills relevant to General Practice.
- Chooses examinations in line with the patient's problem(s).
- Identifies abnormal signs
- Suggests appropriate procedures related to the patient's problem(s).
- Observes the professional codes of practice including the use of chaperones.
- Arranges the place of the examination to give the patient privacy and to respect their dignity.
- Examination is carried out sensitively and without causing the patient harm
- Performs procedures and examinations with the patient's consent and with a clinically justifiable reason to do so."""

Making_a_decision_diagnosis = """
- This is about a conscious, structured approach to making diagnoses and decision-making.
- Generates an adequate differential diagnosis based on the information available.
- Generates and tests appropriate hypotheses.
- Makes decisions by applying rules, plans or protocols.
- Is starting to develop independent skills in decision making and uses the support of others to confirm these are correct."""

Clinical_management = """
- This is about the recognition and management of patients' problems.
- Uses appropriate management options
- Suggests possible interventions in all cases.
- Arranges follow up for patients
- Makes safe prescribing decisions, routinely checking on drug interactions and side effects.
- Refers safely, acting within the limits of their competence.
- Recognises medical emergencies and responds to them safely.
- Ensures that continuity of care can be provided for the patient's problem, e.g. through adequate record keeping."""

Managing_medical_complexity = """
- This is about aspects of care beyond the acute problem, including the management of co-morbidity, uncertainty, risk and health promotion.
- Manages health problems separately, without necessarily considering the implications of co- morbidity.
- Identifies and tolerates uncertainties in the consultation.
- Attempts to prioritise management options based on an assessment of patient risk.
- Manages patients with multiple problems with reference to appropriate guidelines for the individual conditions.
- Considers the impact of the patient's lifestyle on their health. """

Working_with_colleagues_and_in_teams = """
- This is about working effectively with other professionals to ensure good patient care and includes the sharing of information with colleagues.
- Shows basic awareness of working within a team rather than in isolation.
- Understands the different roles, skills and responsibilities that each member brings to a primary health care team.
- Respects other team members and their contribution but has yet to grasp the advantages of harnessing the potential within the team.
- Responds to the communications from other team members in a timely and constructive manner.
- Understands the importance of integrating themselves into the various teams in which they participate."""

Maintaining_performance_learning_and_teaching = """
- This is about maintaining the performance and effective continuing professional development (CPD) of oneself and others. The evidence for these activities should be shared in a timely manner within the appropriate electronic Portfolio.
- Knows how to access the available evidence, including the medical literature, clinical performance standards and guidelines for patient care.
- Engages in some study reacting to immediate clinical learning needs.
- Changes behaviour appropriately in response to the clinical governance activities of the practice, in particular to the agreed outcomes of the practice's audits, quality improvement activities and significant event analyses.
- Recognises situations, e.g. through risk assessment, where patient safety could be compromised.
- Contributes to the education of others."""


Organisation_management_and_leadership = """
- This is about understanding how primary care is organised within the NHS, how teams are managed and the development of clinical leadership skills.
- Demonstrates a basic understanding of the organisation of primary care and the use of clinical computer systems.
- Uses the patient record and on-line information during patient contacts, routinely recording each clinical contact in a timely manner following the record-keeping standards of the organisation.
- Personal organisational and time- management skills are sufficient that patients and colleagues are not inconvenienced or come to any harm.
- Responds positively to change in the organisation.
- Manages own workload responsibly."""

Practising_holistically_promoting_health_and_safeguarding = """
- This is about the ability of the doctor to operate in physical, psychological, socio-economic and cultural dimensions. The doctor is able to take into account patient's feelings and opinions. The doctor encourages health improvement, self-management, preventative medicine and shared care planning with patients and their carers. The doctor has the skills and knowledge to consider and take appropriate safeguarding actions.
- Enquires into physical, psychological and social aspects of the patient's problem.
- Recognises the impact of the problem on the patient.
- Offers treatment and support for the physical, psychological and social aspects of the patient's problem.
- Recognises the role of the GP in health promotion.
- Understands and demonstrates principles of adult and child safeguarding, recognising potential indicators of abuse, harm and neglect, taking some appropriate action."""

Community_orientation = """
- This is about the management of the health and social care of the practice population and local community.
- Demonstrates understanding of important characteristics of the local population, e.g. patient demography, ethnic minorities, socio-economic differences and disease prevalence, etc.
- Demonstrates understanding of the range of available services in their particular locality.
- Understands limited resources within the local community, e.g. the availability of certain drugs, counselling, physiotherapy or child support services.
- Takes steps to understand local resources in the community – e.g. school nurses, pharmacists, funeral directors, district nurses, local hospices, care homes, social services including child protection, patient participation groups, etc."""


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

            completion = await self.openai_client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=messages,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature
            )
            
            review_content = completion.choices[0].message.content
            review_content = review_content.replace('*', '').replace('#', '')

            sections = extract_sections(review_content, selected_capabilities)
            case_title = await generate_title(sections["brief_description"], self.openai_client, self.settings)

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
            # Add debug logging
            print(f"Parsed capabilities: {capabilities}")  # Temporary debug print
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