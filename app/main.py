from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from sqlalchemy.orm import Session

from app.database import engine, SessionLocal
from app.models import Base, Widget
from app.schemas import WidgetCreate, WidgetUpdate, WidgetOut
from app.auth_dependency import get_current_user

import os

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.exception_handler(FastAPIHTTPException)
async def custom_http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_embed_snippet(widget_id: int) -> str:
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8001")
    return f'<script src="{base_url}/widget.js?id={widget_id}"></script>'


@app.get("/")
def root():
    return {"name": "Widget Platform API", "version": "1.0"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/widgets", status_code=201, response_model=WidgetOut)
def create_widget(widget: WidgetCreate, current=Depends(get_current_user), db: Session = Depends(get_db)):
    user, token = current
    new_widget = Widget(
        tenant_id=user.id,
        type=widget.type,
        title=widget.title,
        description=widget.description,
        fields=[f.model_dump() for f in widget.fields],
        button_text=widget.button_text,
        display_options=widget.display_options,
    )
    db.add(new_widget)
    db.commit()
    db.refresh(new_widget)

    result = WidgetOut.model_validate(new_widget)
    result.embed_snippet = build_embed_snippet(new_widget.id)
    return result


@app.get("/widgets", response_model=list[WidgetOut])
def list_widgets(current=Depends(get_current_user), db: Session = Depends(get_db)):
    user, token = current
    return db.query(Widget).filter(Widget.tenant_id == user.id).all()


@app.get("/widgets/{widget_id}/config")
def get_widget_config(widget_id: int, response: Response, db: Session = Depends(get_db)):
    widget = db.query(Widget).filter(Widget.id == widget_id).first()
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")

    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["Access-Control-Allow-Origin"] = "*"

    return {
        "id": widget.id,
        "type": widget.type,
        "title": widget.title,
        "description": widget.description,
        "fields": widget.fields,
        "button_text": widget.button_text,
        "display_options": widget.display_options,
    }


@app.put("/widgets/{widget_id}", response_model=WidgetOut)
def update_widget(widget_id: int, update: WidgetUpdate, current=Depends(get_current_user), db: Session = Depends(get_db)):
    user, token = current
    widget = db.query(Widget).filter(Widget.id == widget_id, Widget.tenant_id == user.id).first()
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")

    update_data = update.model_dump(exclude_unset=True)
    if "fields" in update_data and update_data["fields"] is not None:
        update_data["fields"] = [f if isinstance(f, dict) else f.model_dump() for f in update_data["fields"]]

    for key, value in update_data.items():
        setattr(widget, key, value)

    db.commit()
    db.refresh(widget)
    return widget


@app.delete("/widgets/{widget_id}", status_code=204)
def delete_widget(widget_id: int, current=Depends(get_current_user), db: Session = Depends(get_db)):
    user, token = current
    widget = db.query(Widget).filter(Widget.id == widget_id, Widget.tenant_id == user.id).first()
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
    db.delete(widget)
    db.commit()