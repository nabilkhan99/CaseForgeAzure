# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # API Keys
    openai_api_key: str
    anthropic_api_key: str
    
    # URLs
    frontend_url: str = "http://localhost:3000"
    
    # AI Model Settings
    openai_model: str = "gpt-4"
    anthropic_model: str = "claude-3-opus-20240229"
    max_tokens: int = 4000
    temperature: float = 0.7
    
    # Application Settings
    debug: bool = False
    environment: str = "development"

    # System prompts
    SYSTEM_PROMPT: str = """You are an AI assistant helping GP trainees write portfolio entries. You will generate detailed case reviews following the exact format shown in the examples, maintaining professional medical language and making specific, actionable points throughout. Focus on connecting capabilities to concrete actions and including both clinical and emotional aspects in reflections. 
Do not use any special characters in the output at all. E.g no *,$,&,- etc."""
    EXAMPLE_1: str = """During a duty day I noticed VH, an elderly gentleman..."""
    EXAMPLE_1_RESPONSE: str = """Brief Description: Elderly patient VH with hearing impairment..."""
    EXAMPLE_2: str = """I worked a busy weekend on call covering general psychiatry..."""
    EXAMPLE_2_RESPONSE: str = """Brief Description: During a busy weekend on call covering general psychiatry..."""
    MAIN_PROMPT: str = """I am a GP Trainee. Write a clinical case review for my GP Portfolio based on the case description below. Please structure the response with ALL of the following sections in order:

Brief Description:
[Provide a clear, structured 2-3 paragraph summary of the key points, clinical decisions, and outcomes]

{formatted_capabilities}

Reflection: What will I maintain, improve or stop?
[Reflect on:
- What went well and why (to maintain these behaviors)
- What could be improved in future similar cases
- What should be stopped or done differently
- Your emotional response to the case]

Learning needs identified from this event:
[List specific learning needs, knowledge gaps, or skills to develop based on this case]

Here is the case to review:
{case_description}"""

    def __init__(self, **kwargs):
        # Get values from Azure Function app settings
        kwargs['openai_api_key'] = os.environ.get('OPENAI_API_KEY', '')
        kwargs['anthropic_api_key'] = os.environ.get('ANTHROPIC_API_KEY', '')
        kwargs['frontend_url'] = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
        kwargs['openai_model'] = os.environ.get('OPENAI_MODEL', 'gpt-4')
        kwargs['max_tokens'] = int(os.environ.get('MAX_TOKENS', '4000'))
        kwargs['temperature'] = float(os.environ.get('TEMPERATURE', '0.7'))
        kwargs['debug'] = os.environ.get('DEBUG', 'false').lower() == 'true'
        kwargs['environment'] = os.environ.get('ENVIRONMENT', 'development')
        
        super().__init__(**kwargs)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

# Import the capability content from your original config
capability_content = """
Fitness to practise
- This is about professionalism and the actions expected to protect people from harm. This includes the awareness of when an individual's performance, conduct or health, or that of others, might put patients, themselves or their colleagues at risk.
- Understands the GMC document, "Duties of a Doctor".
- Attends to their professional duties.
- Awareness that physical or mental illness, or personal habits, might interfere with the competent delivery of patient care.
- Identifies and notifies an appropriate person when their own or a colleague's performance, conduct or health might be putting others at risk.
- Responds to complaints or performance issues appropriately.

Maintaining an ethical approach
- This is about practising ethically with integrity and a respect for equality and diversity.
- Awareness of the professional codes of practice as described in the GMC document "Good Medical Practice".
- Understands the need to treat everyone with respect for their beliefs, preferences, dignity and rights.
- Recognises that people are different and does not discriminate against them because of those differences.
- Understands that "Good Medical Practice" requires reference to ethical principles.

Communication and consultation skills
- This is about communication with patients, the use of recognised consultation techniques, establishing patient partnership, managing challenging consultations, third-party consultations and the use of interpreters.
- Develops a working relationship with the patient, but one in which the problem rather than the person is the focus.
- Uses a rigid or formulaic approach to achieve the main tasks of the consultation.
- Provides explanations that are relevant and understandable to the patient, using appropriate language.
- The use of language is technically correct but not well adapted to the needs and characteristics of the patient.
- Provides explanations that are medically correct but doctor-centred.
- Communicates management plans but without negotiating with, or involving, the patient.
- Consults to an acceptable standard but lacks focus and requires longer consulting times.
- Aware of when there is a language barrier and can access interpreters either in person or by telephone.

Data gathering and interpretation
- This is about the gathering, interpretation, and use of data for clinical judgement, including information gathered from the history, clinical records, examination and investigations.
- Accumulates information from the patient that is relevant to their problem.
- Uses existing information in the patient records.
- Employs examinations and investigations that are in line with the patient's problems.
- Identifies abnormal findings and results.

Clinical examination and procedural skills
- This is about clinical examination and procedural skills. By the end of training, the trainee must have demonstrated competence in general and systemic examinations of all of the clinical curriculum areas, this includes the 5 mandatory examinations and a range of skills relevant to General Practice.
- Chooses examinations in line with the patient's problem(s).
- Identifies abnormal signs
- Suggests appropriate procedures related to the patient's problem(s).
- Observes the professional codes of practice including the use of chaperones.
- Arranges the place of the examination to give the patient privacy and to respect their dignity.
- Examination is carried out sensitively and without causing the patient harm
- Performs procedures and examinations with the patient's consent and with a clinically justifiable reason to do so.

Making a decision/diagnosis
- This is about a conscious, structured approach to making diagnoses and decision-making.
- Generates an adequate differential diagnosis based on the information available.
- Generates and tests appropriate hypotheses.
- Makes decisions by applying rules, plans or protocols.
- Is starting to develop independent skills in decision making and uses the support of others to confirm these are correct.

Clinical management
- This is about the recognition and management of patients' problems.
- Uses appropriate management options
- Suggests possible interventions in all cases.
- Arranges follow up for patients
- Makes safe prescribing decisions, routinely checking on drug interactions and side effects.
- Refers safely, acting within the limits of their competence.
- Recognises medical emergencies and responds to them safely.
- Ensures that continuity of care can be provided for the patient's problem, e.g. through adequate record keeping.

Managing medical complexity
- This is about aspects of care beyond the acute problem, including the management of co-morbidity, uncertainty, risk and health promotion.
- Manages health problems separately, without necessarily considering the implications of co- morbidity.
- Identifies and tolerates uncertainties in the consultation.
- Attempts to prioritise management options based on an assessment of patient risk.
- Manages patients with multiple problems with reference to appropriate guidelines for the individual conditions.
- Considers the impact of the patient's lifestyle on their health.

Working with colleagues and in teams
- This is about working effectively with other professionals to ensure good patient care and includes the sharing of information with colleagues.
- Shows basic awareness of working within a team rather than in isolation.
- Understands the different roles, skills and responsibilities that each member brings to a primary health care team.
- Respects other team members and their contribution but has yet to grasp the advantages of harnessing the potential within the team.
- Responds to the communications from other team members in a timely and constructive manner.
- Understands the importance of integrating themselves into the various teams in which they participate.

Maintaining performance, learning and teaching
- This is about maintaining the performance and effective continuing professional development (CPD) of oneself and others. The evidence for these activities should be shared in a timely manner within the appropriate electronic Portfolio.
- Knows how to access the available evidence, including the medical literature, clinical performance standards and guidelines for patient care.
- Engages in some study reacting to immediate clinical learning needs.
- Changes behaviour appropriately in response to the clinical governance activities of the practice, in particular to the agreed outcomes of the practice's audits, quality improvement activities and significant event analyses.
- Recognises situations, e.g. through risk assessment, where patient safety could be compromised.
- Contributes to the education of others.

Organisation, management and leadership
- This is about understanding how primary care is organised within the NHS, how teams are managed and the development of clinical leadership skills.
- Demonstrates a basic understanding of the organisation of primary care and the use of clinical computer systems.
- Uses the patient record and on-line information during patient contacts, routinely recording each clinical contact in a timely manner following the record-keeping standards of the organisation.
- Personal organisational and time- management skills are sufficient that patients and colleagues are not inconvenienced or come to any harm.
- Responds positively to change in the organisation.
- Manages own workload responsibly.

Practising holistically, promoting health and safeguarding
- This is about the ability of the doctor to operate in physical, psychological, socio-economic and cultural dimensions. The doctor is able to take into account patient's feelings and opinions. The doctor encourages health improvement, self-management, preventative medicine and shared care planning with patients and their carers. The doctor has the skills and knowledge to consider and take appropriate safeguarding actions.
- Enquires into physical, psychological and social aspects of the patient's problem.
- Recognises the impact of the problem on the patient.
- Offers treatment and support for the physical, psychological and social aspects of the patient's problem.
- Recognises the role of the GP in health promotion.
- Understands and demonstrates principles of adult and child safeguarding, recognising potential indicators of abuse, harm and neglect, taking some appropriate action.

Community orientation
- This is about the management of the health and social care of the practice population and local community.
- Demonstrates understanding of important characteristics of the local population, e.g. patient demography, ethnic minorities, socio-economic differences and disease prevalence, etc.
- Demonstrates understanding of the range of available services in their particular locality.
- Understands limited resources within the local community, e.g. the availability of certain drugs, counselling, physiotherapy or child support services.
- Takes steps to understand local resources in the community – e.g. school nurses, pharmacists, funeral directors, district nurses, local hospices, care homes, social services including child protection, patient participation groups, etc."""
