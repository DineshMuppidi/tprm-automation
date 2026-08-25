from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class PlaybookDefinitionOut(BaseModel):
    id: UUID
    code: str
    name: str
    trigger_event: str
    steps: list[dict[str, Any]]
    is_active: bool


class PlaybookExecutionOut(BaseModel):
    id: UUID
    playbook_id: UUID
    playbook_code: str
    playbook_name: str
    vendor_id: UUID | None
    vendor_name: str | None
    status: str
    step_log: list[dict[str, Any]]
    started_at: datetime
    completed_at: datetime | None
