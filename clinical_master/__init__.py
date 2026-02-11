# Clinical Master - ElevenLabs Voice Agent for SCA Simulation
# This module runs alongside the existing Azure Functions

from .server import app as clinical_master_app

__all__ = ["clinical_master_app"]
