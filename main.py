import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Medication, Intake

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

# Helper
class MedicationCreate(Medication):
    pass

class MedicationOut(Medication):
    id: str

class IntakeCreate(Intake):
    pass

class IntakeOut(Intake):
    id: str

# Routes
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
        filt = {}
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
