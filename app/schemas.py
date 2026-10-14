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
    embed_snippet: Optional[str] = None

    class Config:
        from_attributes = True


class SubmissionCreate(BaseModel):
    widget_id: int
    data: Dict[str, Any]


class SubmissionOut(BaseModel):
    id: int
    widget_id: int
    created_at: str
    country: Optional[str] = None
    city: Optional[str] = None
    geo_provider_used: Optional[str] = None

    class Config:
        from_attributes = True


class SubmissionListItem(BaseModel):
    id: int
    widget_id: int
    data: Dict[str, Any]
    country: Optional[str] = None
    city: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class DailyCount(BaseModel):
    day: str
    count: int


class WidgetStat(BaseModel):
    widget_id: int
    widget_title: str
    submission_count: int


class CountryStat(BaseModel):
    country: Optional[str] = None  # None = no geo data (both providers failed or unavailable)
    count: int


class DashboardStatsOut(BaseModel):
    total_submissions: int
    by_day: List[DailyCount]
    by_widget: List[WidgetStat]
    by_country: List[CountryStat]