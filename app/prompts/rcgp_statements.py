"""RCGP SCA feedback statement library (anchor headings + educator notes).

Source: FF SCA Feedback Engine Build Package, Part 4. The 26 statement TITLES are
the anchor headings the engine uses for failed-domain feedback (Section 9.1). The
EDUCATOR_NOTES are the published RCGP Explanation, Suggestions, and Capability
areas, bundled verbatim into the marking prompt so the model grounds its
"how to improve" guidance in RCGP wording and populates capability_links.

This file is generated from the source document; do not hand-edit the notes.
"""
from __future__ import annotations

STATEMENT_TITLES: dict[str, list[str]] = {
    'data_gathering': [
        'Data gathering was insufficient to enable safe assessment of the condition or situation.',
        'Existing information about the case was insufficiently utilised.',
        'Relevant psychological or social information insufficiently recognised or responded to.',
        'Data gathering was unsystematic or disorganised.',
        'Ineffective approach or prioritisation in data gathering, when presented with multiple or complex problems.',
        'The implications of relevant findings identified during the data gathering were insufficiently recognised or understood.',
        'Differential diagnoses or hypotheses were inadequately generated or tested.',
        'Decision making or diagnosis was illogical, incorrect or incomplete.',
    ],
    'clinical_management': [
        'The management plan relating to referral was inappropriate or not reflective of current practice.',
        'The management plan relating to prescribing of medication was inappropriate or not reflective of current practice.',
        'The management plan relating to investigations was inappropriate or not reflective of current practice.',
        'The management plan relating to prevention, health promotion or rehabilitation was inadequate or inappropriate.',
        'The plan relating to the medical management of risk was inadequate or inappropriate.',
        'The implications of co morbidity were insufficiently considered.',
        'Uncertainty, including that experienced by the patient, was managed ineffectively.',
        'Inappropriate or inadequate arrangements for follow up, continuity or safety netting.',
        'Time management in the consultation was ineffective.',
    ],
    'relating_to_others': [
        'Communication skills, including the non verbal, responding to cues or active listening, were insufficiently demonstrated.',
        "The person's agenda, health beliefs or preferences were insufficiently explored.",
        'The circumstances, relevant cultural differences or preferences of those involved were insufficiently responded to.',
        "Explanations were inadequately shared or adapted for the person's needs.",
        'A judgemental approach was shown to the person.',
        'Respect or sensitivity shown to the person was inadequate or inappropriate.',
        'Ownership or responsibility for decision making was inadequate or inappropriate.',
        "Teamwork or understanding of others' roles was insufficiently recognised or responded to.",
        'Safeguarding concerns were inadequately recognised or responded to.',
    ],
}

ALL_STATEMENT_TITLES: list[str] = [t for ts in STATEMENT_TITLES.values() for t in ts]

EDUCATOR_NOTES: str = r'''
Feedback statements for the SCA Publication date: 08 August 2023 The provision of examination feedback is critically important for ongoing examination preparation, and this will be provided for all candidates in the SCA. The feedback statements below relate to the [standards document for the SCA](https://www.rcgp.org.uk/mrcgp-exams/simulated-consultation-assessment#marking). This maps to the capabilities used in WPBA. Your ability and familiarity with the capabilities for WPBA should support your performance in the SCA. Feedback will be case-specific and linked to the [marking domains](https://www.rcgp.org.uk/mrcgp-exams/simulated-consultation-assessment#marking). The feedback statements are not performance indicators and play no part in the marking process for the examination. The examiner will have marked the case before selecting the relevant feedback statements. They are not designed to provide a justification of the mark, and may be offered to passing candidates as well as to those who fail a particular domain. Any domain which is failed by the examiner will receive feedback. Any selected statement should guide your future preparation particularly if these appear more than once. Feedback will be released with your results. It is important to remember that feedback highlights general areas for improvement. There will have been many areas that were done well, which cannot be documented in the allocated marking time for the examiners. In addition to the feedback statements, educational notes have been written on all the feedback statements. These link to the [capabilities used in WPBA](https://www.rcgp.org.uk/mrcgp-exams/wpba/capability-framework), and it would be recommended to review the competent word pictures within that capability on the RCGP website. The educator notes define the feedback statement. They also make suggestions using specific examples to help support your understanding and learning on how you might demonstrate this area in the future. We would encourage you to share this feedback with your supervisor. Domain 1 - Data gathering and diagnosis Standard for marking domain 1 (passing level)
Systematically gathers and organises relevant and targeted information to address the needs of the patient and their problem(s).
Adopts a structured and informed approach to problem-solving, generating an appropriate differential diagnosis or relying on first principles where the presentation is undifferentiated, uncertain or complex. Feedback statements for domain 1 1Data gathering was insufficient to enable safe assessment of the condition/situation
Explanation
Examiners felt that the history taken was insufficient in terms of breadth or depth to enable you to safely assess the condition and its severity.
Suggestions
Ensure you consider the presence or absence of relevant ‘red flags’.
An exhaustive enquiry into a list of all possible symptoms is unnecessary and impractical; but ask enough to demonstrate you have considered the relevant serious possibilities.
Be curious and interested in the severity of the patient’s presentation and how the symptoms are affecting them.
Watch videos of your consultations, or role play scenarios with your supervisor or peer study group.
Have you enough information to form a differential diagnosis and distinguish significant illness from something more minor or self-limiting? For example, if you decide a patient has mechanical back pain, have you excluded cauda equina? If they are bleeding PV, have you considered pregnancy, or if their smear is up-to-date? With each consultation consider, what else could this be? What do I need to exclude?
Create short lists to prompt red flags for common presentations in GP.
Watching other more experienced colleagues consult will help.
Capability areas
      * Data gathering and interpretation.2Existing information about the case was insufficiently utilised

Explanation
Examiners felt that the consultation would have benefitted from reference to information provided in the case notes. Data gathering includes understanding and incorporating data from the patient record to inform the consultation.
For example, if a patient has seen a doctor previously, refer to this. ‘I note you saw my colleague last week about nose bleeds and she made some suggestions. How have you been since then?’ Or ‘Our notes say you are taking metformin, atorvastatin and ramipril, is that correct?’ Rather than, ‘are you taking any medication?’
You might notice a patient has an allergy or has previously tried a medication. Perhaps their smear is due. They may have suffered a recent bereavement. Consider if this might be relevant or referred to in your consultation.
A low MCV might indicate iron deficiency anaemia, so a change in bowel habit may need more urgent investigation than a normal Hb might suggest. A change in eGFR may mean that medications such as metformin need their dose adjusting.
Suggestions
Take time before starting a consultation in your surgery. What information is helpful for you to know? What is the patient’s past medical history? What medications are they taking? How recently have they been seen and for what reason? Are there any ongoing health issues that should be raised?
Notice how familiarity with the patient record informs the consultation, compared to seeing someone ‘blind’ with no record, for example, in an Urgent Unscheduled Care or A&E setting.
Plan a tutorial on record keeping and the function(s) of GP notes.
Capability areas
         * Data gathering and interpretation.
         * Organisation, management and leadership.3Relevant psychological or social information insufficiently recognised or responded to

Explanation
Examiners felt that you needed to explore the patient’s social or psychological situation further, to establish context. Or that this contextual information was not sufficiently conveyed in your discussion or decision-making. Often patients present with a physical problem, but its effect may be provoked, magnified or complicated by their social or psychological situation.
This is about seeing and valuing the whole person, rather than simply their symptom. Recognising that no two patients’ experience of an illness are the same.
For example, a diagnosis of “tennis elbow / lateral epicondylitis” might appear to be relatively straightforward. However, if the patient is self-employed, currently out of work with a newly pregnant partner, suggesting a Fit Note or time away from the factors exacerbating the elbow pain might be unhelpful. A different approach to a cough or rash will be needed for someone about to take a flight to start a gap year abroad, from someone who is street homeless or someone who is a current star of musical theatre. Without establishing the psycho-social context, it is harder to produce a management plan that is appropriate and acceptable to the individual patient.
Suggestions
Be curious about your patients and their experiences. Establish the impact of an illness on their lives. Recognise and value their needs and priorities. This is not a tick box exercise, but a demonstration of wishing to understand how to make this consultation relevant, responsive and unique for the individual concerned.
Ask for feedback from your supervisor on this aspect of your consulting; role play cases you have encountered with your peers, with you ‘role reversing’ by playing the part of the patient.
Practice being curious about the person, their social or psychological situation and how this might affect their experience of symptoms, or their preferences for management/next steps.
Capability areas
            * Practicing holistically, promoting health and safeguarding.4Data gathering was unsystematic and/or disorganised

Explanation
Examiners did not feel that the consultation had a logical structure.
Consultations are not scripted or linear, it is often necessary to return to aspects of data gathering or test new hypotheses as information comes to light. The consultation is a conversation between two people and as such, may be unpredictable.
However, your data gathering may have appeared disjointed, your questioning failing to show a reasoned way of thinking. The consultation may have appeared disorganised or even chaotic, with some elements apparently occurring at random. This gives the impression of a doctor who may miss important clinical issues because he/she is not systematic; or one who is at a loss for what to ask.
For example, for a patient with long COVID, a systematic approach to their symptoms, rather than a ‘scattergun’ enquiry of irrelevant, disjointed questions may be more helpful both diagnostically and therapeutically. It may seem topsy-turvy or presumptuous to give a diagnosis before data has been gathered. Or to agree to a prescription prior to establishing safety.
Aim for a stepwise approach to systematically gather information, focus your enquiry and target questions to the problem.
Suggestions
Consider the various GP consultation models (such as Neighbour, Pendleton or Cambridge-Calgary). Ask a colleague or your supervisor to critique the structure or organisation of your consulting.
Using open questions to explore the presenting features, before focussing on specific detail with closed questions, is often helpful.
Try signposting, where you signal to the patient what you are about to do. For example, ‘I would like to ask you some questions about your health in the past.’ If you should need to return to aspects of data gathering later in the consultation, consider saying, ‘I realise I need to return to some other questions now...’
Summarising also demonstrates that you are collating and processing the collected information; and is useful in allowing the patient to clarify anything misunderstood.
Capability area
               * Data gathering and interpretation.5Ineffective approach or prioritisation in data gathering, when presented with multiple or complex problems

Explanation
The examiner felt you were insufficiently able to generate functional solutions for data gathering when the presentation was complex or multifactorial.
This may be about prioritisation; recognising the most pressing or important issues for this encounter and negotiating this with the patient. For example, if a patient has hay fever, longstanding headaches and bleeding on passing stool we might agree to focus on the latter today, offering time for the other issues in future.
Or this may be about seeing the bigger picture, rather than attempting an exhaustive evaluation of each of the symptoms in turn. For example, if a patient has symptoms in multiple bodily systems, might there be a unifying diagnosis? Or might exploring why all this is happening at once and what the patient is most worried about be more helpful than an exhaustive enquiry into each and every symptom, as long as this is safe?
Suggestion
Ensure you see plenty of complex patients, including those with co-morbidity. This may need triaging as new practice members often have more ‘book on the day’ single-issue consultations; complex patients may have a ‘usual doctor’ already. Discuss cases with your supervisor, as CBDs. Consider tutorials or peer study group sessions on complexity and negotiating priorities with patients.
Capability area
                  * Managing medical complexity.6The implications of relevant findings identified during the data gathering were insufficiently recognised or understood

Explanation
Examiners felt that you did not demonstrate an ability to identify or recognise significant findings in the consultation. Some findings may have been identified but not acted upon appropriately, so that examiners conclude you did not recognise their significance. This skill requires you to correctly recognise and respond to the significance of information in the consultation. The abnormal findings will often relate to common or important conditions.
A patient who you find to be cognitively impaired may not be able to follow complex management instructions without additional support. Or perhaps a patient experiencing unilateral headache was diagnosed as migraine rather than temporal arteritis, despite tenderness on brushing their hair.
A newly confused patient who takes DOACs may need an urgent CT head to exclude a subdural.
Suggestions
Consider how you pick up on abnormal findings and respond safely and appropriately. Discuss your consultations with colleagues, asking them to comment, particularly on your response to abnormal findings that emerge in the consultation.
Capability areas
                     * Data gathering and interpretation.7Differential diagnoses or hypotheses were inadequately generated or tested

Explanation
Examiners felt that you did not consider relevant conditions in the differential diagnosis. Perhaps you should have considered and explored a broader range of possibilities, before narrowing your diagnosis. Or perhaps the examiners felt it was impossible or unnecessary to make a single diagnosis during the consultation and that different options should be explored further.
For example, although the patient may appear anxious, before concluding she has anxiety disorder, might it be helpful to consider ADHD, might she use cocaine, or might she have issues with her thyroid gland?
Suggestions
Try to consider and test a range of possible diagnoses. Avoid assumptions about patients. Notice if you employ confirmation bias, where you favour new information that confirms previous beliefs, disregarding other evidence that may not align.
Sharing insight into your diagnostic reasoning with the patient (and thereby the examiner) is helpful too. For example, ‘I had thought about X but as your Y is not painful this is less likely, however if Z happens, we will need to reconsider this next time.’
Capability area
                        * Making diagnosis/decisions.8Decision-making or diagnosis was illogical, incorrect or incomplete

Explanation
Examiners felt that you failed to make the appropriate diagnosis and/or that the reasoning behind your conclusions did not make sense, clinically.
Making a diagnosis or reaching a decision means making a conclusion about what is likely, from the information you have available to you.
For example, did you conclude someone had psoriasis when the rash and history were those of a fungal skin infection? Did you decide someone has restless legs, despite them being vegan and have a very low B12? Could that URTI more likely be hay fever, based on the information available. Perhaps the ECG provided showed Atrial Fibrillation but you did not diagnose this.
Or did you appear to sit on the fence and avoid communicating a diagnosis that seemed obvious, for fear of getting it wrong in the examination?
Suggestions
Try to reach a decision before debriefing a patient with your supervisor and ensure you challenge yourself about the likely diagnosis. Is your decision-making in line with that of your colleagues?
Do you tend to be dogmatic or quick to jump to conclusions in your diagnoses?
Is there an area of the curriculum you are less confident in?
Consider proactively addressing this in your reading, your patient experience and your other learning opportunities.
Random case analyses and case-based discussions are also very helpful in putting your decision-making in the spotlight.
Capability areas
                           * Making diagnosis/decisions.
                           * Clinical Management.
                           * Managing medical complexity.Domain 2 - Clinical management and medical complexity
Standard for marking domain 2 (passing level)
                              * Demonstrates the ability to formulate safe and appropriate management options which includes effective prioritisation, time, self-management and continuity.
                              * Demonstrates commitment to providing optimum care in the short and long-term, whilst acknowledging the challenges.
Feedback statements for domain 21The management plan relating to referral was inappropriate or not reflective of current practice

Explanation
You are expected to show that your clinical management skills are in line with current UK best practice. You may not have developed a plan at all, where a referral was needed. Or you may have referred to an inappropriate place. Or you may have referred when this was not necessary/appropriate in this case.
You are expected to understand and value the role of the multi-disciplinary team. In addition to secondary care, the referral in question may be to counselling, community or social services. It may also be about encouraging/signposting self-referral.
For example, a referral to a rheumatologist for gout may be unnecessary. Or a two-week wait, rather than routine referral for unexplained PR bleeding in a 54-year-old could have been more suitable.
Suggestions
Your management plan should be coherent and feasible. You should be familiar with current national guidelines such as those published by NICE (National Institute of Clinical Excellence) and SIGN (Scottish Intercollegiate Guidelines Network).
Use the concept of PUNs (Patients’ Unmet Needs) and DENs (Doctors’ Educational Needs) to improve management. This means learning on the job from dilemmas and challenges as they arise, case by case: Make a habit of referring to guidelines after you have seen each patient at work. Notice areas in the MRCGP (curriculum clinical topic guides) that you need more experience with. Plan tutorials or peer learning to support these areas, or use your self-directed learning sessions to attend specialist clinics.
Capability area
                              * Clinical Management.2The management plan relating to prescribing of medication was inappropriate or not reflective of current practice

Explanation
You are expected to show that your clinical management skills are in line with current UK best practice, making safe prescribing decisions, considering relevant drug interactions, dosing, and side effects. You may not have developed a plan at all, where a prescription was needed. You may have prescribed or failed to stop an inappropriate medication; or issued an incorrect dose. Or you may have prescribed when no prescription was necessary in this case. 
This may also refer to the suggestion of over the counter (non-prescription) medication. For example, perhaps tamsulosin rather than finasteride would have been more suitable for a gentleman with LUTS, first line. Or when prescribing alendronic acid, advice about side effects and how to take should have been given, enhancing patient safety.
Suggestions
Your management plan should be coherent and feasible. You should be familiar with current national guidelines such as those published by NICE (National Institute of Clinical Excellence) and SIGN (Scottish Intercollegiate Guidelines Network). 
Make a habit of referring to prescribing guidelines and/or the BNF after you have seen each patient at work. Where appropriate, consider other options before prescribing and be aware of the risks of polypharmacy and the need to deprescribe, too.
Get involved with the work of repeat prescribing in your surgery, complete your Prescribing Assessment for WPBA. Attend prescribing meetings at work with your team and community pharmacist.
Capability area
                                 * Clinical Management3The management plan relating to investigations was inappropriate or not reflective of current practice

Explanation
You are expected to show that your clinical management skills are in line with current UK best practice. You may not have suggested investigations at all, where they were needed. You may have suggested inappropriate or unjustifiable investigations. Or you may have arranged investigations when none were needed in this case.
For example, it may not be necessary to request an MRI scan for simple back pain, or a sputum sample for an URTI. If someone has symptoms of irritable bowel syndrome it may be unclear why a vitamin D level is suggested. Alternatively, after a cough worsening over several weeks, it may have been advisable to request a chest Xray.
Suggestions
Your management plan should be coherent and feasible. You should be familiar with current national guidelines such as those published by NICE (National Institute of Clinical Excellence) and SIGN (Scottish Intercollegiate Guidelines Network).
Investigations requested should be targeted and relevant, answering a specific clinical question. It should be clear why they are being chosen, based on the probability of disease and with an awareness of budgetary governance.
You may feel that it would be better to be ‘on the safe side’ by ordering a battery of tests and whilst understandable, this can make you appear indiscriminate.
Collect a list of all the investigations you have requested over a few sessions at work. Compare with others, peers or your supervisor. What was the reason for choosing those investigations? Were they helpful and/or justified? Plan a tutorial where you share and action your supervisor’s results list and vice versa.
Capability area
                                    * Clinical Management.4The management plan relating to prevention, health promotion or rehabilitation was inadequate or inappropriate

Explanation
You are expected to encourage prevention of illness, offer health promotion and rehabilitation strategies, where needed. These may include issuing a sick note, encouraging patient autonomy and self-care, prioritising ‘lifestyle’ advice. Sometimes this might include recognising the ‘gatekeeper’ role of the GP in prioritising NHS resources and/or reducing dependency on healthcare.
For example, a patient with COPD would benefit from pulmonary rehabilitation, smoking cessation and flu vaccination. Did you focus mainly on which inhaler to provide?
Another patient may need a sick note due to their psoriasis flare. Did you refuse this unnecessarily? Or grant one that may be unhelpfully long in duration, when self-certification may be a good first step?
Someone with threadworms might be gently signposted to the pharmacist for simple over the counter medications in future, assuming they can afford this.
Suggestion
Consider whether there are important areas of prevention, health promotion or rehabilitation you might encourage. For example, do you know some simple exercises for mild knee pain? Or understand how to support someone locally with smoking cessation or weight loss? Are you aware of NHS screening programs? How do you respond to requests for housing letters or fit notes?
Think about the different types of NHS resource that GPs are ‘gatekeepers’ for, and how reference to these emerge in our consultations. This does not mean that you are expected to refuse access to services, new medications or ‘fit notes’, but that you show your awareness of the issues and responsible use of resources.
Capability area
                                       * Practicing holistically, promoting health and safeguarding.
5The plan relating to the medical management of risk was inadequate or inappropriate

Explanation
Medical management of risk means ‘the forecasting and evaluation of risks together with identification of procedures to avoid or minimise their impact’. Risk management prioritises patient safety and ensures an appropriate response to preventing risk or managing error.
Examiners did not feel that you managed risk appropriately. This could mean either that you failed to identify the potential risks or that having done so you did not respond in an appropriate way. Perhaps you didn't seem aware of the responsibility for a systems' response, for example significant event analysis or the complaints process.
Alternatively, you may have been too risk-averse in an otherwise safe encounter.
For example, was the risk of a patient falling, or the impact on their eGFR, greater than the risk of their slightly raised blood pressure? Should those risks have been prioritised before following a BP guideline?
Was the risk of overdose greater than the convenience of issuing three months’ of medication?
Did a temporary patient with no records receive care without reference to his registered GP in a way that created risk?
Did a concerned daughter who identified a problem with her cognitively impaired father’s care fail to receive supportive signposting to the complaints procedure and a willingness to investigate via a significant event analysis with the team?
Were documents shared without consideration of data protection?
Suggestions
Be aware of NHS guidelines around medical risk management. Engage in partners’ meetings and significant event / complaints analyses in the practice to become familiar with the practical applications of risk management in the workplace. Discuss risk with your supervisor and consider risk management as a priority in your patient encounters.
Capability areas
                                       * Clinical Management.
                                       * Organisation management and leadership.
6The implications of co-morbidity were insufficiently considered

Explanation
You are expected to recognise the inevitable conflicts that arise when managing patients with multiple problems and takes steps to adjust care appropriately.
It is also important to simultaneously manage the patient’s health problems, both acute and chronic.
For example, although a guideline for managing one chronic disease may indicate best practice for prescribing for that single condition, sometimes the other conditions a patient is living with may mean it is necessary to alter or even avoid prescribing. This may be particularly true for frail older adults and in the case of polypharmacy.
Or a patient with hands affected by rheumatoid arthritis, who has CKD may not be able to open bottles of ibuprofen during a flare, nor be safe to take them, given their eGFR.
Suggestion
Ensure you regularly consult with people experiencing multiple illnesses or chronic disease. This may mean pro-actively triaging your cases or taking over the care of frail vulnerable adults. Participate in team meetings for example where housebound patients are discussed with district/palliative nurses. Use self-directed learning time to attend community falls clinics, or care of the older adult outpatients. Be aware of the literature surrounding over-medicalisation and the downsides of polypharmacy.
Capability areas
                                       * Managing medical complexity
                                       * Making diagnosis/decisions
                                       * Maintaining an ethical approach7Uncertainty, including that experienced by the patient, was managed ineffectively

Explanation
Examiners felt that clinical uncertainty and/or that experienced by the patient was ineffectively managed.
It may be that time as a diagnostic aid was not used appropriately. Or that you were unable to tolerate or ‘hold’ uncertainty effectively. Or that management strategies used to respond to the patient’s uncertainty were not helpful.
For example: Another scan may not be helpful for a patient with medically unexplained symptoms. It might be reasonable to wait a week or so before prescribing for, or investigating a symptom that is likely to be self-limiting. On the other hand, someone who declines antenatal testing for Down Syndrome may need additional support and information while she completes her pregnancy.
Suggestion
Be aware of the literature surrounding over-medicalisation. Plan a tutorial or peer study group session on uncertainty in General Practice. Consider how uncertainty might be safely tolerated or responded to.
Capability area
                                          * Managing medical complexity.
                                          * Practising holistically, promoting health and safeguarding.
8Inappropriate or inadequate arrangements for follow-up, continuity and/or safety netting

Explanation
Examiners felt that your follow-up arrangements were not adequate or that you did not ensure that there was an appropriate safety net.
Making arrangements for follow-up demonstrates your commitment to the continuity of care of patients. It shows that you are prepared to take responsibility for managing the ongoing presentation of the condition until the problem has been resolved. However, inappropriate or unrealistic follow-up is unhelpful both for the index patient and for other patients who may be unable to access their GP, with limited appointment availability.
Safety-netting describes the information you should be giving to each patient about what to expect, including a time scale if appropriate, and what to do if symptoms get worse or develop in some unexpected way. However, safety-netting may cause unnecessary alarm if performed without care.
For example, having diagnosed upper abdominal pain as simple indigestion, consider how a safety net that suggests going to A&E if it recurs ‘in case it is your heart’ might be received.
Suggestion
Consider how you end your consultations. Is it always with a safety net and if so, is that appropriately tailored to the consultation? Be aware of the literature surrounding the benefits of continuity of care in GP and discuss the systems that enable this in your practice, with the team. Notice if you are booking a follow-up and consider if this is necessary or practical.
Capability area
                                          * Clinical Management.
9Time management in the consultation was ineffective

Explanation
Examiners felt that you showed poor time management during the cases, perhaps taking too long over certain tasks or failing to cover what was thought to be essential as time ran out.
The ability to consult within a short time is essential for current practice. We must manage time as a resource for the sake of ourselves, our other patients and the whole team.
A common reason for running out of time in cases is taking too long over data gathering, and then having to rush clinical management, explanations and follow-up arrangements. Pace yourself and consider roughly how long you should be taking for the different parts of the consultation. Remember the SCA cases are designed to be possible in the twelve-minute time frame.
A reminder: Data gathering requires us to be appropriately selective in the questions we ask, tailored to the circumstances of the patient, rather than being an ‘all inclusive’ review of systems.
Suggestions
Try to see patients within a limited time frame at work. Set up a clock within eyeshot of your desk. Role play strategies for managing time, especially in challenging situations. Observe clinicians who consult effectively but efficiently and incorporate their techniques into your practice.
Capability areas
                                          * Clinical management.
                                          * Managing medical complexity.
                                          * Communication and consultation skills.Domain 3 – Relating to others: Feedback statements
Standard for marking domain 3 (passing level)
                                             * Demonstrates ethical awareness.
                                             * Shows ability to communicate in a person-centred way.
                                             * Demonstrates initiative and flexibility in using various consultation approaches in order to overcome any communication barriers and to reach a shared understanding with the patient.
Feedback statements for domain 31Communication skills, including the non-verbal, responding to cues and/or active listening were insufficiently demonstrated

Explanation
The examiner felt you did not demonstrate sufficient communication skills for independent practice. This may include responding to cues that could have enhanced your understanding. They may have felt your listening skills were poor, for example you may have asked questions, but not listened to or responded to the answers. Or that your consulting was ‘formulaic’, meaning it felt rigid or even scripted: Perhaps you used phrases that did not seem relevant or helpful to the person, or did not appear to acknowledge their reply appropriately.
For example, if you repeat a stock phrase such as ‘I am sorry to hear that’ too frequently it loses its impact. Perhaps when a patient says ‘I am not sociable these days’ you should have been curious as to what that means, or why. Perhaps when a patient tells you they are worried about a breast lump there is a better response than ‘OK, is there anything else you’d like to discuss today?’
Suggestions
Active listening includes paying attention and responding appropriately. It is essential for building a relationship of trust with the patient. It is helped by clarifying and summarising what has been shared to demonstrate understanding.
Cues can include non-verbal gestures, pauses in speech or facial expressions. Cues are moments in the patient’s account that indicate there are additional areas to explore.
To avoid ‘formulaic’ consulting, try to avoid rigidly applying a set consulting ‘model’ to the consultation that does not respond to the individual patient.
Watch videos of your consultations, seeking feedback from your supervisor. Notice how you demonstrate you are listening, how you facilitate the consultation and the timing of your interruptions.
Practice different phrases to respond authentically to the patient’s contribution. Watch your colleagues consult and write down every possible cue you notice.
Capability area
                                             * Communication and consultation skills.
2The person’s agenda, health beliefs and/or preferences were insufficiently explored

Explanation
The examiners felt the consultation was insufficiently person-centred.
It is important to understand the context of the illness; and attach importance to the subjective aspects of medicine. This means always seeing the patient as a unique person and being curious; then valuing patient preferences and expectations.
For example, a patient whose neighbour has lung cancer may have fears about their own cough. Another patient may be vaccine hesitant due to health beliefs which are understandable and strongly held in their community.
Suggestion
Ensure you explore the person's ideas, concerns and expectations; also consider the impact the situation has had on their life.
Capability areas
                                             * Communication and consultation skills.
                                             * Practising holistically, promoting health and safeguarding.3The circumstances, relevant cultural differences and/or preferences of those involved were insufficiently responded to

Explanation
Examiners felt that you might not have made full use of the information given by the patient to you during the consultation. You may not have sufficiently demonstrated the ability to work in partnership with your patient to develop a shared management plan. It is important to take account of the patient’s agenda, health beliefs or preferences in the development of a management plan.
For example, a coughing patient whose neighbour has lung cancer may need particular reassurance or investigation to assuage their fear. Another patient who is vaccine hesitant due to health beliefs which are understandable and strongly held in their community might be receptive to signposting of resources produced by community leaders and a non-pressurising approach.
Patient-centred doctors are responsive to patient preferences about their health. This does not mean you can/should always be patient led. But the information about their unique situation and preferences should inform how you proceed and what you do next.
Suggestions
Practice responding appropriately to your patients’ agenda and preferences, incorporating these where possible into your plans and explanations. Try to involve patients in making decisions wherever possible.
There are many educational resources about consulting skills (both in print and online) that will help.
Capability area
                                                * Communication and consultation skills.
                                                * Practising holistically, promoting health and safeguarding.
                                                * Community orientation.
4Explanations were inadequately shared or adapted for the person’s needs

Explanation
The examiner felt that your explanations were unclear or insufficient for patient understanding.
Explanations should be relevant and understandable to patients and carers, using clear language that is both appropriate and accessible. People living with disability may need special consideration.
For example, ‘There is a small lesion on your film’ contains jargon that may have little meaning to your patient. Or ‘You have some proteins causing joint pain as your body is fighting itself’ may not be useful to a Rheumatology Nurse Specialist. A hearing-impaired person may benefit from visual aids or written explanations. A child of eleven may need an adaptation of the explanation given to their adult carer/parent.
Suggestion
Try to employ communication techniques and materials that may adapt explanations to the needs of the person and/or carer.
Consider what do they need to know, and how can I explain it in a way that is accessible and helpful for them? Then how might I check they understand?
Capability area
                                                * Communication and consultation skills.
5A judgemental approach was shown to the person

Explanation
Examiners felt that you conveyed judgement about the person and/or their behaviour/situation in your response to them during the consultation. This may have been implied.
There are many ways a judgement can be expressed or perceived. For example, doctors may inadvertently ‘fat shame’ someone with obesity by implying ‘we get the body we deserve’; or comment ‘what did you expect?’ when a person becomes pregnant from unprotected sex. A person who has recently left prison may experience judgement when an unnecessary line of questioning about their crime ensues. Although reasonable challenge may be appropriate, criticism of parental decisions about vaccinations, food choices or smoking in the flat may be unhelpfully judgemental and therefore alienating.
It may be that people with certain protected characteristics generate a less empathic, supportive response. For example, an undocumented migrant may be only superficially helped or even dismissed.
Suggestion
We all carry unconscious bias. Recognise which consultations may challenge your assumptions. Understand why some people may be more vulnerable, more susceptible to illness or less able to make changes that improve health. Try to consult with a diverse range of people and demonstrate empathy, compassion and partnership with them all where possible.
Capability areas
                                                * Communication and consultation skills.
                                                * Maintaining an ethical approach.6Respect and/or sensitivity shown to the person was inadequate or inappropriate

Explanation
The examiner felt that you failed to treat the patient with sufficient respect or sensitivity. This may involve a sufficient introduction, consent where needed or assurance of privacy or confidentiality. Being sensitive to the patient involves noticing distress and responding sensitively. Or approaching emotionally charged areas carefully and/or seeking permission before proceeding to explore areas that are difficult or intrusive for the patient.
For consultations with children or patients with cognitive impairment, respect can be shown by engaging with the patient rather than entirely relying on their carer.
Insufficient respect may include excessive familiarity with the patient, dismissive body language and/or patronising behaviour.
Suggestions
You can check that you are being respectful by sharing your consultations with experienced colleagues in the practice. Ask whether you are being sufficiently respectful/sensitive to the patient? Notice the times when sensitivity is more challenging, perhaps when you are under time pressure or for certain patient groups.
Watch others consult and notice times when they are being sensitive and times when they could be more so.
Capability areas
                                                   * Fitness to practice.
                                                   * Maintaining an ethical approach.7Ownership or responsibility for decision-making was inadequate or inappropriate

Explanation
The examiners felt that you did not take adequate ownership or responsibility for your decision-making. It may have appeared you were overly risk-averse, or unsure how to manage a simple situation without unnecessary input from other sources.
For example, this may involve suggesting you will ‘Run this past my colleagues’ or ‘Drop an email to Advice and Guidance from the specialist’ or arrange a physio opinion ‘just in case’ where it was not needed or warranted.
It is clearly important, safe and good practice for GPs to share decisions, refer to literature and involve others. Nevertheless, sometimes a simple decision is robust, defensible and adequate, without need for additional input. This is partly about the gate-keeping role we hold in GP, but also the message we convey to patients (including raising anxiety or expectations) when it is reasonable and safe for the GP to be the only clinician involved, because in this situation the answer is straightforward or clear.
Suggestions
Try to make decisions before debriefing a patient with your supervisor, even if you do not implement the decision until discussed. Develop confidence in recognising when your decision-making is good enough. Watch experienced GPs and notice what a good enough GP will do, too.
Capability area
                                                      * Fitness to practice.
                                                      * Making diagnosis/decisions.
                                                      * Maintaining an ethical approach.8Teamwork and/or understanding of others’ roles was insufficiently recognised or responded to

Explanation
The examiners felt you did not demonstrate an adequate understanding or application of teamwork.
This may mean you did not recognise, value or involve the various team members who work in primary care. Perhaps you did not demonstrate an understanding of the context within which different team members are working, for examples Health Visitors and their role in safeguarding. Or perhaps your communication with team members did not enhance team-work or patient care.
For example, should the palliative care team be involved when cancer treatment comes to an end? Or might the physiotherapist have a role to play for shoulder pain? On the other hand, is it reasonable to ask your practice mental health practitioner to offer weekly appointments to someone with mild anxiety?
Suggestions
Attend and contribute to MDT meetings in your practice. Sit in with Allied Health Professionals in your practice or beyond. Try to develop an understanding of the context of their work, including how best to liaise and collaborate in the best interest of patient care.
Capability areas
                                                         * Working with Colleagues and in teams.9Safeguarding concerns were inadequately recognised or responded to

Explanation
The examiner felt you did not understand and/or demonstrate principles of adult and child safeguarding. Perhaps you did not recognise or practice in a manner that sufficiently sought to reduce the risk of potential abuse, harm and neglect. Perhaps you did not take appropriate action including ensuring information is shared/referrals made appropriately.
For example, if a parent is experiencing substance dependency did you consider the risk to his children? If a woman is disclosing partner abuse, did you have sensitive patient-centred suggestions for keeping safe and signposting specialist services? If a young female patient is being taken out of the country by her relatives, might the risk of FGM be important to consider in her case? If an older adult appears frail and unkempt, might a home visit, team discussion or even safeguarding referral to explore possible self-neglect be sensible?
Suggestions
Meet with your practice Safeguarding Lead and/or attend their safeguarding meetings. Ensure your Level 3 Safeguarding training is up-to-date and implemented. Have a tutorial on local safeguarding procedures and pathways.
Capability area
                                                            * Practicing holistically, promoting health and safeguarding.Using the feedback
Following the result the candidate is encouraged to discuss the feedback with their trainer and/or Educational Supervisor. The feedback may raise similar themes to those that have been previously identified, or it may suggest some new areas to work on for the future.
Experience shows that it is often most useful if a particular feedback statement is repeatedly marked. Or if the feedback is found repeatedly in a particular domain. The odd, single feedback statement relating to one case may be less useful. However, it will be linked to the case, so the candidate will know which case the feedback refers to.
Should the candidate need to make future attempts at the SCA, it is encouraged to avoid focussing solely on the areas where they received negative feedback. For example, if the candidate received feedback about inadequate safety-netting, over-emphasising safety-netting may be to the detriment of these consultations where it is not needed, appears formulaic or takes up too much time.
'''
