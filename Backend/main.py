import sys
import os
import itertools 
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from db import SessionLocal, engine
from models import InteractionLog, User, Medication, UserMedication, Base
from agent import analyze_interaction


Base.metadata.create_all(bind=engine)

app = FastAPI()

from pydantic import BaseModel
from typing import List

class MedicationData(BaseModel):
    name: str
    dosage: str
    frequency: str
    active_ingredients: List[str] = []
class AlertOutput(BaseModel): 
    drugs_involved: List[str]
    alert_message: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "RxRadar backend is alive!"}

class MedInput(BaseModel):
    medications: List[str]

class MedicationInput(BaseModel):
    medications: List[MedicationData]

@app.post("/analyze_medications")
async def analyze_medications(med_input: MedicationInput):
    """
    Analyze meds - includes extracting active ingredients, pairing, identifying duplicates, and sending non-duplicate pairs for retrieving context + querying of LLM. 
    """
    

    entered_active_ingredients = [
        ai.lower() for med in med_input.medications
        for ai in med.active_ingredients if ai != "UNKNOWN" 
    ]


    pairs = list(itertools.combinations(entered_active_ingredients, 2))


    interaction_pairs = []
    duplicate_pairs = []
    for pair in pairs:
        if pair[0] == pair[1]:
            duplicate_pairs.append(pair)
        else:
            if pair not in interaction_pairs and (pair[1],pair[0]) not in interaction_pairs: 
                interaction_pairs.append(pair)

    

    alerts = []


    for dupe in duplicate_pairs:
        meds_with_dup = [
            m.name for m in med_input.medications 
            if dupe[0] in [ai.lower() for ai in m.active_ingredients] 
        ]
        alerts.append(AlertOutput(
                drugs_involved=list(set(meds_with_dup)),
                alert_message=f"You have entered medications with the same active ingredient:'{dupe[0].title()}'. Please review your medications to avoid potential overdosing, dangerous side effects, and/or unecessary medication."
            ).dict())


    for inter in interaction_pairs:
        drug1 = inter[0]
        drug2 = inter[1]
        llm_alert = analyze_interaction(drug1, drug2) 

   
        med_1_for_inter = [
            m.name for m in med_input.medications
            if inter[0] in [ai.lower() for ai in m.active_ingredients] 
        ]
        med_2_for_inter = [
            m.name for m in med_input.medications 
            if inter[1] in [ai.lower() for ai in m.active_ingredients]
        ]

       
        med_1_disp = " / ".join(med_1_for_inter)
        med_2_disp = " / ".join(med_2_for_inter)

   
        interaction_drugs_invovled = [med_1_disp, med_2_disp]

        alerts.append(AlertOutput(
                drugs_involved = interaction_drugs_invovled,
                alert_message=f"{llm_alert}"
            ).dict()) 

    return {"alerts": alerts}



class MedRequest(BaseModel):
    drug1: str
    drug2: str
    summary: Optional[str] = ""

@app.post("/check_meds")
def check_meds(payload: MedRequest, db: Session = Depends(get_db)):
    explanation = analyze_interaction(payload.drug1, payload.drug2)
    new_log = InteractionLog(
        drug1=payload.drug1,
        drug2=payload.drug2,
        summary=explanation
    )
    db.add(new_log)
    db.commit()
    return {"explanation": explanation}


class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        return {"error": "Username already exists."}
    new_user = User(username=user.username, password=user.password)
    db.add(new_user)
    db.commit()
    return {"message": "User registered successfully."}


class MedicationAdd(BaseModel):
    username: str
    medications: List[str]

@app.post("/add_medications")
def add_medications(data: MedicationAdd, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        return {"error": "User not found"}

    for med_name in data.medications:
        medication = db.query(Medication).filter(Medication.name == med_name).first()
        if not medication:
            medication = Medication(name=med_name)
            db.add(medication)
            db.commit()
            db.refresh(medication)

        exists = db.query(UserMedication).filter_by(
            user_id=user.id, medication_id=medication.id
        ).first()
        if not exists:
            db.add(UserMedication(user_id=user.id, medication_id=medication.id))
            db.commit()

    return {"message": "Medications added successfully."}

from fastapi import HTTPException

@app.post("/login")
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(
        User.username == user.username,
        User.password == user.password
    ).first()
    if db_user:

        user_meds = db.query(UserMedication).filter(UserMedication.user_id == db_user.id).all()
        medications = []
        for um in user_meds:
            med_obj = db.query(Medication).filter(Medication.id == um.medication_id).first()
            medications.append({
                "name": med_obj.name if med_obj else "",
                "dosage": getattr(um, "dosage", ""),
                "frequency": getattr(um, "frequency", ""),
                "active_ingredients": um.active_ingredients.split(",") if um.active_ingredients else []
            })
        return {
            "username": db_user.username,
            "user_id": db_user.id,
            "medications": medications
        }
    raise HTTPException(status_code=401, detail="Invalid username or password")


class SaveMedicationsRequest(BaseModel):
    username: str
    medications: List[MedicationData]

@app.post("/save_medications")
def save_user_medications(request: SaveMedicationsRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    

    db.query(UserMedication).filter(UserMedication.user_id == user.id).delete()
    db.commit()


    for med in request.medications:
        medication = db.query(Medication).filter(Medication.name == med.name).first()
        if not medication:
            medication = Medication(name=med.name)
            db.add(medication)
            db.commit()
            db.refresh(medication)
        
        user_med = UserMedication(
            user_id=user.id,
            medication_id=medication.id,
            dosage=med.dosage,
            frequency=med.frequency,
            active_ingredients=",".join(med.active_ingredients)
        )
        db.add(user_med)
    db.commit()
    return {"message": "Medications saved successfully."}


class LoadMedicationsResponse(BaseModel):
    medications: List[MedicationData]

@app.get("/load_medications/{username}", response_model=LoadMedicationsResponse)
def load_user_medications(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user_meds = db.query(UserMedication).filter(UserMedication.user_id == user.id).all()
    meds = []
    for um in user_meds:
        meds.append(MedicationData(
            name=um.medication.name,
            dosage=getattr(um, "dosage", ""),
            frequency=getattr(um, "frequency", ""),
            active_ingredients=um.active_ingredients.split(",") if um.active_ingredients else []
        ))
    return {"medications": meds}
