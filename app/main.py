from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from sqlalchemy.orm import Session

from app.database import engine, SessionLocal
from app.models import Base, Widget, Submission
from app.schemas import WidgetCreate, WidgetUpdate, WidgetOut, SubmissionCreate, SubmissionOut
from app.auth_dependency import get_current_user
from fastapi.middleware.cors import CORSMiddleware

import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.geo import enrich_ip


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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
def health():
    return {"status": "ok"}


WIDGET_JS_VERSION = "v1"

WIDGET_JS_CONTENT = """
(function() {
  const script = document.currentScript;
  const widgetId = new URLSearchParams(script.src.split('?')[1]).get('id');
  const apiBase = script.src.split('/widget.js')[0];

  fetch(apiBase + '/widgets/' + widgetId + '/config')
    .then(res => res.json())
    .then(config => {
      const container = document.createElement('div');
      container.style.cssText = 'border:1px solid #ccc; padding:16px; border-radius:8px; max-width:300px; font-family:sans-serif;';

      const title = document.createElement('h3');
      title.textContent = config.title;
      container.appendChild(title);

      const form = document.createElement('form');
      config.fields.forEach(field => {
        const input = document.createElement('input');
        input.type = field.type;
        input.name = field.name;
        input.placeholder = field.name;
        input.required = field.required;
        input.style.cssText = 'display:block; width:100%; margin-bottom:8px; padding:6px;';
        form.appendChild(input);
      });

      const button = document.createElement('button');
      button.type = 'submit';
      button.textContent = config.button_text;
      form.appendChild(button);

      form.addEventListener('submit', function(e) {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(form));
        fetch(apiBase + '/submissions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ widget_id: parseInt(widgetId), data: data })
        }).then(() => {
          form.innerHTML = '<p>Thank you!</p>';
        });
      });

      container.appendChild(form);
      script.parentNode.insertBefore(container, script);
    });
})();
"""

@app.get("/widget.js")
def get_widget_js(response: Response):
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["Content-Type"] = "application/javascript"
    return Response(content=WIDGET_JS_CONTENT, media_type="application/javascript", headers=response.headers)


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



@app.post("/submissions", status_code=201, response_model=SubmissionOut)
@limiter.limit("5/minute")
async def create_submission(submission: SubmissionCreate, request: Request, db: Session = Depends(get_db)):
    widget = db.query(Widget).filter(Widget.id == submission.widget_id).first()
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {submission.widget_id} not found")

    if submission.data.get("website"):
        raise HTTPException(status_code=400, detail="Submission rejected")

    import json
    if len(json.dumps(submission.data)) > 5000:
        raise HTTPException(status_code=413, detail="Submission payload too large")

    client_ip = request.client.host if request.client else None
    country, city, geo_provider_used = await enrich_ip(client_ip)

    new_submission = Submission(
        widget_id=widget.id,
        tenant_id=widget.tenant_id,
        data=submission.data,
        ip_address=client_ip,
        country=country,
        city=city,
        geo_provider_used=geo_provider_used,
    )
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)

    return SubmissionOut(
        id=new_submission.id,
        widget_id=new_submission.widget_id,
        created_at=new_submission.created_at.isoformat(),
        country=new_submission.country,
        city=new_submission.city,
        geo_provider_used=new_submission.geo_provider_used,
    )