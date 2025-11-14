import os
import uuid
from datetime import datetime, date as dt_date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from database import db, create_document, get_documents
from schemas import Medication, Intake, CaregiverLink

app = FastAPI(title="Pill Reminder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Pill Reminder Backend Running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# Helper models
class MedicationCreate(Medication):
    pass

class MedicationOut(Medication):
    id: str

class IntakeCreate(Intake):
    pass

class IntakeOut(Intake):
    id: str

class ShareCreate(BaseModel):
    medication_ids: Optional[List[str]] = None
    expires_at: Optional[str] = None  # ISO timestamp

# Core Routes
@app.post("/api/medications", response_model=dict)
async def create_medication(payload: MedicationCreate):
    try:
        med_id = create_document("medication", payload)
        return {"id": med_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/medications", response_model=List[MedicationOut])
async def list_medications():
    try:
        docs = get_documents("medication")
        result: List[MedicationOut] = []
        for d in docs:
            d["id"] = str(d.pop("_id"))
            result.append(MedicationOut(**d))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/intakes", response_model=dict)
async def log_intake(payload: IntakeCreate):
    try:
        intake_id = create_document("intake", payload)
        return {"id": intake_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/intakes", response_model=List[IntakeOut])
async def list_intakes(medication_id: Optional[str] = None, date: Optional[str] = None):
    try:
        filt: Dict[str, Any] = {}
        if medication_id:
            filt["medication_id"] = medication_id
        if date:
            filt["date"] = date
        docs = get_documents("intake", filt)
        result: List[IntakeOut] = []
        for d in docs:
            d["id"] = str(d.pop("_id"))
            result.append(IntakeOut(**d))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Schedule endpoint for a given date
@app.get("/api/schedule")
async def get_schedule(date: Optional[str] = None):
    try:
        if date:
            target = datetime.fromisoformat(date)
        else:
            target = datetime.now()
        weekday = (target.weekday())  # 0=Mon..6=Sun
        meds = get_documents("medication", {"active": True})
        items = []
        for m in meds:
            # Ensure structure
            m_days = m.get("days", [0,1,2,3,4,5,6])
            if weekday in m_days:
                for t in m.get("times", []):
                    items.append({
                        "medication_id": str(m.get("_id")),
                        "name": m.get("name"),
                        "dosage": m.get("dosage"),
                        "time": t
                    })
        items.sort(key=lambda x: x["time"])
        return {"date": target.date().isoformat(), "weekday": weekday, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Caregiver share endpoints
@app.post("/api/share/create")
async def create_share_link(payload: ShareCreate):
    try:
        token = uuid.uuid4().hex[:12]
        doc = {
            "token": token,
            "read_only": True,
            "expires_at": payload.expires_at,
            "medication_ids": payload.medication_ids,
        }
        _id = create_document("caregiverlink", doc)
        base = os.getenv("FRONTEND_URL") or os.getenv("PUBLIC_FRONTEND_URL") or ""
        return {"token": token, "url": f"{base}/?share={token}" if base else token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _validate_share_token(token: str) -> Dict[str, Any]:
    links = get_documents("caregiverlink", {"token": token})
    if not links:
        raise HTTPException(status_code=404, detail="Share link not found")
    link = links[0]
    # optional expiration check
    expires_at = link.get("expires_at")
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) < datetime.utcnow():
                raise HTTPException(status_code=410, detail="Share link expired")
        except ValueError:
            pass
    return link

@app.get("/api/share/{token}/schedule")
async def shared_schedule(token: str, date: Optional[str] = None):
    link = _validate_share_token(token)
    allowed = set(link.get("medication_ids") or [])
    # reuse schedule logic
    sched = await get_schedule(date)
    if allowed:
        sched["items"] = [i for i in sched["items"] if i["medication_id"] in allowed]
    return sched

@app.get("/api/share/{token}/intakes")
async def shared_intakes(token: str, medication_id: Optional[str] = None, date: Optional[str] = None):
    link = _validate_share_token(token)
    allowed = set(link.get("medication_ids") or [])
    if allowed and medication_id and medication_id not in allowed:
        raise HTTPException(status_code=403, detail="Not permitted for this medication")
    filt: Dict[str, Any] = {}
    if date:
        filt["date"] = date
    if medication_id:
        filt["medication_id"] = medication_id
    docs = get_documents("intake", filt)
    # If allowed set exists, filter results
    if allowed:
        docs = [d for d in docs if d.get("medication_id") in allowed]
    # format
    out = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
