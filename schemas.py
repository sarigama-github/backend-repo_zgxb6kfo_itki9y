"""
Database Schemas for Pill Reminder App

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercase class name (e.g., Medication -> "medication").
"""
from pydantic import BaseModel, Field
from typing import List, Optional

class Medication(BaseModel):
    """Medications prescribed to a person.
    Collection: medication
    """
    name: str = Field(..., description="Medication name")
    dosage: str = Field(..., description="Dosage instructions, e.g. '1 pill' or '5ml'")
    times: List[str] = Field(..., description="Daily reminder times in HH:MM 24h format")
    days: List[int] = Field(default_factory=lambda: [0,1,2,3,4,5,6], description="Days of week (0=Mon..6=Sun)")
    notes: Optional[str] = Field(None, description="Additional notes")
    active: bool = Field(True, description="Whether this medication is active")

class Intake(BaseModel):
    """Log of taken medications for a specific date/time.
    Collection: intake
    """
    medication_id: str = Field(..., description="ID of the medication document")
    time: str = Field(..., description="Scheduled time in HH:MM 24h format")
    date: str = Field(..., description="Calendar date in YYYY-MM-DD")
    taken_at: Optional[str] = Field(None, description="ISO timestamp when marked taken")
