from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ComponentStatus:
    id: str
    name: str
    status: str
    updated_at: str
    position: int


@dataclass
class IncidentUpdate:
    id: str
    body: str
    created_at: str
    display_at: str
    status: str
    incident_id: str


@dataclass
class Incident:
    id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
    impact: str
    updates: List[IncidentUpdate]
