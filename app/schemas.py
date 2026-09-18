from pydantic import BaseModel
from typing import Optional, Literal, List, Dict, Any


class WidgetField(BaseModel):
    name: str
    type: str
    required: bool = False


class WidgetCreate(BaseModel):
    type: Literal["signup_form", "cta_popover"]
    title: str
    description: Optional[str] = None
    fields: List[WidgetField]
    button_text: str = "Submit"
    display_options: Dict[str, Any] = {}


class WidgetUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[List[WidgetField]] = None
    button_text: Optional[str] = None
    display_options: Optional[Dict[str, Any]] = None


class WidgetOut(BaseModel):
    id: int
    tenant_id: str
    type: str
    title: str
    description: Optional[str]
    fields: List[WidgetField]
    button_text: str
    display_options: Dict[str, Any]

    class Config:
        from_attributes = True