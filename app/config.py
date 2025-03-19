# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # API Keys
    openai_api_key: str
    anthropic_api_key: str
    azure_openai_api_key: str
    
    # URLs
    frontend_url: str = "http://localhost:3000"
    
    # AI Model Settings
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-opus-20240229"
    max_tokens: int = 800
    temperature: float = 0.7
    
    # Azure OpenAI Settings
    azure_openai_endpoint: str = "https://ai-caseforge2025a060083517978.openai.azure.com"
    azure_openai_api_version: str = "2024-07-18"
    azure_openai_deployment: str = "gpt-4o-mini"
    
    # Application Settings
    debug: bool = False
    environment: str = "development"

    # System prompts
    SYSTEM_PROMPT: str = """You are an AI assistant helping GP trainees write portfolio entries. You will generate detailed case reviews following the exact format shown in the examples, maintaining professional medical language and making specific, actionable points throughout. Focus on connecting capabilities to concrete actions and including both clinical and emotional aspects in reflections. 
Do not use any special characters in the output at all. E.g no *,$,&,- etc."""
    # EXAMPLE_1: str = """During a duty day I noticed VH, an elderly gentleman..."""
    # EXAMPLE_1_RESPONSE: str = """Brief Description: Elderly patient VH with hearing impairment..."""
    # EXAMPLE_2: str = """I worked a busy weekend on call covering general psychiatry..."""
    # EXAMPLE_2_RESPONSE: str = """Brief Description: During a busy weekend on call covering general psychiatry..."""
    MAIN_PROMPT: str = """I am a GP Trainee. Write a clinical case review for my GP Portfolio based on the case description below. Please structure the response with ALL of the following sections in order:

Brief Description:
[Provide a clear, structured 2-3 paragraph summary of the key points, clinical decisions, and outcomes]

{formatted_capabilities}

Reflection:
[Reflect on:
- What went well and why (to maintain these behaviors)
- What could be improved in future similar cases
- What should be stopped or done differently
- Your emotional response to the case i.e. how did it make you feel?]


Learning needs identified from this event:
[List specific learning needs, knowledge gaps, or skills to develop based on this case]

Note: 
- Do not include the specific points like "What should be stopped or done differently" in the reflection and learning needs sections. it should be a general reflection on the case using the points above as a guide.
- Write in British English not American

Here is the case to review:
"""

# Example 1 - Original case
    EXAMPLE_1: str = """During a duty day I noticed VH, an elderly gentleman was on the list requesting a call back. The telephone number had a code in front of it. I was aware VH was very hard of hearing. The telephone number took me through a text telephone service. I witnessed the use of the text telephone system and conveyed my questions via an operator. VH in turn answered the questions. VH was concerned he may have had a recurrence of his piles and was keen for something to help. We had a brief conversation on the telephone. I became acutely aware that I needed to ask short and simple questions that could be conveyed via a text. Having never seen VH with a similar problem, nor could I see a recent documentation of treatment for haemorrhoids and that it was harder to communicate over the telephone I arranged to see him to further assess face to face."""

    # Example 1 - Model response
    EXAMPLE_1_RESPONSE: str = """Brief Description:
    Elderly patient VH with hearing impairment requested a callback regarding possible recurrence of hemorrhoids. Initial contact was made through a text telephone service, requiring adaptation of communication style to work effectively through an operator. Given the communication challenges and lack of previous documentation regarding hemorrhoid treatment, a face to face assessment was arranged for thorough evaluation.

    Communication and consultation skills
    It was interesting to experience the text telephone system. I have now had experience of using a different communication modality. I was able to adapt the language that I used to take into consideration his individual needs. I was able to manage the consultation effectively with the patient through using the text telephone interpreter, which required me to be organized and structured.

    Reflection:
    When asking questions via an operator it is important to be precise with the questions to. It made me consider the importance of e 3 system as well as improving communication with patients using different modalities. Overall I felt this telephone consultation and the process of the consultation was successful.

    Learning needs identified from this event:
    I would like to gain experience of using a translation telephone line (something we do not use regularly in my current practice). I would also like to develop further strategies to communicate effectively with patients who have a loss of hearing should they present alone, or with a signer."""

    # Example 2 - Original case
    EXAMPLE_2: str = """I worked a busy weekend on call covering general psychiatry over several hospital sites."""

    # Example 2 - Model response
    EXAMPLE_2_RESPONSE: str = """Brief Description: 
            During a busy weekend on call covering general psychiatry across several hospital sites, I encountered a range of cases that tested my clinical skills and decision-making abilities. One of the key cases involved a patient presenting with acute psychosis exacerbated by substance misuse. The patient exhibited disorganized speech, hallucinations, and agitation, requiring prompt assessment and management. I collaborated with the multidisciplinary team to ensure the patient was stabilized, initiated appropriate pharmacotherapy, and arranged for further psychiatric evaluation. The outcome was positive; the patient was stabilized and referred for inpatient care, highlighting the importance of timely intervention in psychiatric emergencies.
    Throughout the weekend, I faced challenges related to the demands of managing multiple patients simultaneously, which necessitated effective prioritization and communication with both colleagues and patients. I utilized clinical guidelines to inform my treatment decisions and ensured a holistic approach by considering the patient's history, social circumstances, and potential triggers for the acute episode. The experience reinforced my understanding of the complexities of psychiatric care and the critical nature of teamwork in achieving optimal patient outcomes.

    Working with colleagues and in teams: 
    I find that during on calls you have to use a very particular type of team working skills, as you have to create a mini, instant team for the on calls without knowing who is going to be in the team in advance. The same doctors do nights and days for the weekend, so you hand over to them at the start and end of the shifts, and this continuity is really helpful for patient care. Since the pandemic, there has been a meeting every night at 21.30 via skype, which includes the SHOs, registrar, consultant and matron or nurse in charge. It is really helpful to have the nursing staff represented at the meeting. In one meeting, I discussed a patient who had just become unwell and the meeting meant that the consultant was able to share an experience of Covid19 presenting in a manner like my patient, and the nursing staff being present meant they could immediately go and put the plan we came up with into place, as well as me phoning the nurse directly after the meeting. It facilitated improved patient care. 

    Clinical examination and procedural skills:
    I was attended one of the psychiatric hospitals to review a male patient with abdominal pain. In order to assess him I examined him. At the moment, in a psychiatric hospital, this involves reviewing them in a locked treatment room with a nurse present. I also wear PPE with gloves, a mask and apron. I tried to be sensitive to the fact that I knew he was in a lot of pain and very anxious, and that examining his abdomen was likely to be very uncomfortable, but very important as it meant I could elicit signs such as guarding, which added to my concerns about him needing to go to hospital to rule out serious pathology. 

    Organisation, management and leadership: 
    During this busy weekend, I attended Ravenswood Hospital, which is geographically remote and therefore I needed to manage my time well to ensure I did tasks at hospitals which were on my way to Ravenswood. When I arrived, there was a major incident occurring and therefore I could not immediately do the seclusion reviews which I had attended to do. Once I established that there was nothing I could do to help, I asked if there was somewhere I could work, so that whilst I was waiting I could continue to work remotely on my laptop. This allowed me to ensure that the delay did not effect patients which still needed my attention, for example medications prescribing remotely, as I could access their records online and prescribe remotely. 

    Reflection:
    I will continue to improve my time management skills during busy working periods. I feel that every job I have done have been busy in different ways and have required me to juggle tasks and prioritise tasks differently. I am now imminently going to be moving to GP and am excited to see how my skills transfer and what new ones I need to learn. The experience of covering multiple different sites has been unique with this job and is extremely challenging at times, when you cannot be everywhere at once. There will also be a different type of team in GP, which I am looking forward to, especially after having quite minimal contact with a team for much of this rotation. 

    Learning needs identified from this event:
    I am aware that I need to continue to improve my skills in seeing patients in remote of nonclinical environments, for example on home visits. There are parallels with seeing patients with medical problems OOH in a psychiatric hospital with doing home visits, as psychiatric 5 hospitals are not set up for medical emergencies, and is it very limited in terms of what medical problems can be dealt with. 
    """

        # Example 1 - Original review (from generation API)
    IMPROVEMENT_EXAMPLE_1: str = """Brief Description:
    Elderly patient VH with hearing impairment requested a callback regarding possible recurrence of hemorrhoids. Initial contact was made through a text telephone service, requiring adaptation of communication style to work effectively through an operator. Given the communication challenges and lack of previous documentation regarding hemorrhoid treatment, a face to face assessment was arranged for thorough evaluation.

    Communication and consultation skills
    It was interesting to experience the text telephone system. I have now had experience of using a different communication modality. I was able to adapt the language that I used to take into consideration his individual needs. I was able to manage the consultation effectively with the patient through using the text telephone interpreter, which required me to be organized and structured.

    Reflection: 
    When asking questions via an operator it is important to be precise with the questions to. It made me consider the importance of e 3 system as well as improving communication with patients using different modalities. Overall I felt this telephone consultation and the process of the consultation was successful.

    Learning needs identified from this event:
    I would like to gain experience of using a translation telephone line (something we do not use regularly in my current practice). I would also like to develop further strategies to communicate effectively with patients who have a loss of hearing should they present alone, or with a signer."""

    # Example 1 - Improvement request
    IMPROVEMENT_REQUEST_1: str = """Please add more specific details about the communication adaptations made and expand on the reflection section to include concrete examples of what worked well."""

    # Example 1 - Improved response
    IMPROVEMENT_RESPONSE_1: str = """Brief Description:
    Elderly patient VH with severe hearing impairment requested a callback regarding possible recurrence of hemorrhoids. Initial contact was made through a text telephone service, requiring adaptation of communication style to work effectively through an operator. Given the communication challenges and lack of previous documentation regarding hemorrhoid treatment, a face to face assessment was arranged for thorough evaluation.

    Communication and consultation skills
    The text telephone system provided valuable learning experience in adapting communication methods. I modified my usual consultation style by breaking down complex questions into shorter, clearer segments that could be easily relayed by the operator. For example, instead of asking "Can you tell me about your symptoms and when they started?", I separated this into "When did the symptoms begin?" and "What symptoms are you experiencing?". I consciously avoided medical jargon, using plain language that could be clearly transmitted through the text system. I confirmed understanding after each exchange by asking VH to repeat key information back to me, ensuring accurate communication despite the technical interface.

    Reflection:
    When asking questions via an operator, I learned that precision and simplicity are crucial. Short, focused questions received clearer responses than longer, compound ones. The systematic approach of waiting for each response before proceeding helped maintain clarity. For future similar consultations, I will maintain the practice of breaking down complex questions and confirming understanding at each step. I could improve by preparing a structured list of essential questions in advance, anticipating the need for clarity in text-based communication. The use of closed questions for specific symptoms and open questions for broader concerns worked particularly well in this format.

    Learning needs identified from this event:
    I would like to gain experience of using a translation telephone line (something we do not use regularly in my current practice). I would also like to develop further strategies to communicate effectively with patients who have a loss of hearing should they present alone, or with a signer. Specifically, I plan to learn basic sign language greetings and medical terms, and familiarize myself with various assistive communication technologies available in our practice."""

    # Example 2 - Original review (from generation API)
    IMPROVEMENT_EXAMPLE_2: str = """Brief Description: 
    During a busy weekend on call covering general psychiatry across several hospital sites, I encountered a range of cases that tested my clinical skills and decision-making abilities. One of the key cases involved a patient presenting with acute psychosis exacerbated by substance misuse. The patient exhibited disorganized speech, hallucinations, and agitation, requiring prompt assessment and management. I collaborated with the multidisciplinary team to ensure the patient was stabilized, initiated appropriate pharmacotherapy, and arranged for further psychiatric evaluation. The outcome was positive; the patient was stabilized and referred for inpatient care, highlighting the importance of timely intervention in psychiatric emergencies.

    Working with colleagues and in teams: 
    I find that during on calls you have to use a very particular type of team working skills, as you have to create a mini, instant team for the on calls without knowing who is going to be in the team in advance. The same doctors do nights and days for the weekend, so you hand over to them at the start and end of the shifts, and this continuity is really helpful for patient care. Since the pandemic, there has been a meeting every night at 21.30 via skype, which includes the SHOs, registrar, consultant and matron or nurse in charge. It is really helpful to have the nursing staff represented at the meeting.

    Clinical examination and procedural skills:
    I was attended one of the psychiatric hospitals to review a male patient with abdominal pain. In order to assess him I examined him. At the moment, in a psychiatric hospital, this involves reviewing them in a locked treatment room with a nurse present. I also wear PPE with gloves, a mask and apron.

    Organisation, management and leadership: 
    During this busy weekend, I attended Ravenswood Hospital, which is geographically remote and therefore I needed to manage my time well to ensure I did tasks at hospitals which were on my way to Ravenswood.

    Reflection:
    I will continue to improve my time management skills during busy working periods. I feel that every job I have done have been busy in different ways and have required me to juggle tasks and prioritise tasks differently.

    Learning needs identified from this event:
    I am aware that I need to continue to improve my skills in seeing patients in remote of nonclinical environments, for example on home visits."""

    # Example 2 - Improvement request
    IMPROVEMENT_REQUEST_2: str= """Please expand on the clinical examination section with more specific details about the assessment process and safety considerations in a psychiatric setting."""

    # Example 2 - Improved response
    IMPROVEMENT_RESPONSE_2: str = """Brief Description: 
    During a busy weekend on call covering general psychiatry across several hospital sites, I encountered a range of cases that tested my clinical skills and decision-making abilities. One of the key cases involved a patient presenting with acute psychosis exacerbated by substance misuse. The patient exhibited disorganized speech, hallucinations, and agitation, requiring prompt assessment and management. I collaborated with the multidisciplinary team to ensure the patient was stabilized, initiated appropriate pharmacotherapy, and arranged for further psychiatric evaluation. The outcome was positive; the patient was stabilized and referred for inpatient care, highlighting the importance of timely intervention in psychiatric emergencies.

    Working with colleagues and in teams: 
    I find that during on calls you have to use a very particular type of team working skills, as you have to create a mini, instant team for the on calls without knowing who is going to be in the team in advance. The same doctors do nights and days for the weekend, so you hand over to them at the start and end of the shifts, and this continuity is really helpful for patient care. Since the pandemic, there has been a meeting every night at 21.30 via skype, which includes the SHOs, registrar, consultant and matron or nurse in charge. It is really helpful to have the nursing staff represented at the meeting.

    Clinical examination and procedural skills:
    I attended one of the psychiatric hospitals to review a male patient with acute abdominal pain. The examination required careful consideration of both clinical needs and safety protocols. Before beginning, I conducted a brief risk assessment with the ward staff, reviewing the patient's recent mental state and behavior. The examination took place in a dedicated locked treatment room with a nurse present and panic alarm accessible. I wore appropriate PPE including gloves, mask, and apron, explaining each step to maintain the patient's comfort and cooperation.

    The examination itself needed to be thorough yet efficient given the patient's agitated state. I maintained a clear exit route while systematically examining his abdomen, noting marked right upper quadrant tenderness and guarding. I adapted my technique to the patient's anxiety levels, talking through each step and pausing when needed. The presence of guarding, combined with the patient's elevated heart rate (110 bpm) and fever (38.2°C), raised concerns about possible acute cholecystitis, leading to my decision to arrange urgent transfer to the acute medical unit.

    This case highlighted the importance of maintaining physical health assessment skills in a psychiatric setting while adhering to safety protocols. The challenge was balancing the need for a thorough examination with the patient's mental state and the environmental constraints.

    Organisation, management and leadership: 
    During this busy weekend, I attended Ravenswood Hospital, which is geographically remote and therefore I needed to manage my time well to ensure I did tasks at hospitals which were on my way to Ravenswood.

    Reflection:
    I will continue to improve my time management skills during busy working periods. I feel that every job I have done have been busy in different ways and have required me to juggle tasks and prioritise tasks differently.

    Learning needs identified from this event:
    I am aware that I need to continue to improve my skills in seeing patients in remote of nonclinical environments, for example on home visits."""

    # Example 3 - Original review (from generation API)
    IMPROVEMENT_EXAMPLE_3: str = """Brief Description:
    During a medication review for a 68-year-old female patient with type 2 diabetes, I conducted a comprehensive assessment of her current medication regimen and recent blood sugar readings.

    Communication and consultation skills:
    I discussed her medications and asked about any side effects. The patient mentioned some concerns about her morning dose timing.

    Clinical examination and procedural skills:
    I checked her blood pressure and reviewed her blood sugar diary.

    Reflection:
    The medication review was completed successfully. I will continue to conduct thorough reviews.

    Learning needs identified from this event:
    I need to learn more about diabetes medication combinations."""

    # Example 3 - Improvement request
    IMPROVEMENT_REQUEST_3: str = """Please update the patient's age to 72 years old and add specific details about her medication regimen and the changes made."""

    # Example 3 - Improved response
    IMPROVEMENT_RESPONSE_3: str = """Brief Description:
    During a medication review for a 72-year-old female patient with type 2 diabetes, I conducted a comprehensive assessment of her current medication regimen and recent blood sugar readings.

    Communication and consultation skills:
    I discussed her medications and asked about any side effects. The patient mentioned some concerns about her morning dose timing.

    Clinical examination and procedural skills:
    I checked her blood pressure and reviewed her blood sugar diary.

    Reflection:
    The medication review was completed successfully. I will continue to conduct thorough reviews.

    Learning needs identified from this event:
    I need to learn more about diabetes medication combinations."""


    def __init__(self, **kwargs):
        # Get values from Azure Function app settings
        kwargs['openai_api_key'] = os.environ.get('OPENAI_API_KEY', '')
        kwargs['anthropic_api_key'] = os.environ.get('ANTHROPIC_API_KEY', '')
        kwargs['frontend_url'] = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
        kwargs['openai_model'] = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        kwargs['max_tokens'] = int(os.environ.get('MAX_TOKENS', '800'))
        kwargs['temperature'] = float(os.environ.get('TEMPERATURE', '0.7'))
        kwargs['debug'] = os.environ.get('DEBUG', 'false').lower() == 'true'
        kwargs['environment'] = os.environ.get('ENVIRONMENT', 'development')
        
        # Update initialization to include Azure settings
        kwargs['azure_openai_api_key'] = os.environ.get('AZURE_OPENAI_API_KEY', '')
        kwargs['azure_openai_endpoint'] = os.environ.get('AZURE_OPENAI_ENDPOINT', 'https://ai-caseforge2025a060083517978.openai.azure.com')
        kwargs['azure_openai_api_version'] = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01')
        kwargs['azure_openai_deployment'] = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o-mini')
        
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
