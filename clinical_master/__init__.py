# Clinical Master - Voice Agent for SCA Simulation
# This module runs alongside the existing Azure Functions

from .server import app as clinical_master_app
from .agents.patient import get_patient_agent
from .session.manager import SessionManager

__all__ = ["clinical_master_app", "get_patient_agent", "SessionManager"]
