from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import uuid # For generating unique user IDs

app = FastAPI(
    title="RxRadar Simplified Local Backend",
    description="A simplified FastAPI backend for local Streamlit integration testing (no database).",
    version="0.1.0"
)

# --- In-memory "Database" (for testing without a real DB) ---
# DO NOT use this for production.
# Stores {username: {"password": "plain_text_password", "user_id": "uuid", "medications": []}}
fake_users_db: Dict[str, Dict[str, Any]] = {}

# --- Pydantic Models for Request/Response Bodies ---
class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class MedicationData(BaseModel): # Model for a single medication entry
    name: str
    dosage: str
    frequency: str
    active_ingredients: List[str] = [] # List of strings

class MedicationInput(BaseModel): # Model for medication analysis input
    medications: List[MedicationData] # List of MedicationData objects

class AlertOutput(BaseModel): # Model for simulated alerts
    alert_type: str
    drugs_involved: List[str]
    alert_message: str

# New Pydantic models for saving and loading medications
class SaveMedicationsRequest(BaseModel):
    username: str
    medications: List[MedicationData]

class LoadMedicationsResponse(BaseModel):
    medications: List[MedicationData]

# ---------- API Endpoints ----------

@app.get("/")
async def read_root():
    return {"message": "Simplified FastAPI Backend is running locally!"}

@app.post("/users/register")
async def register_user(user: UserCreate):
    if user.username in fake_users_db:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Store plain password for this demo (NOT secure for production)
    user_id = str(uuid.uuid4()) # Generate a unique ID for the user
    # Initialize medications list for a new user
    fake_users_db[user.username] = {
        "password": user.password,
        "user_id": user_id,
        "medications": [] # Initialize with an empty list of medications
    }
    return {"message": "User registered successfully", "username": user.username, "user_id": user_id}

@app.post("/login")
async def login_user(user: UserLogin):
    stored_user = fake_users_db.get(user.username)
    if not stored_user or stored_user["password"] != user.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    
    # Return user details including saved medications
    return {
        "message": "Login successful",
        "username": user.username,
        "user_id": stored_user["user_id"],
        "medications": stored_user["medications"] # Include medications here
    }

@app.post("/save_medications")
async def save_user_medications(data: SaveMedicationsRequest):
    """
    Saves the user's current medication list to in-memory storage.
    This overwrites any previously saved medications for that user.
    """
    if data.username not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Convert Pydantic models back to dictionaries for simple in-memory storage
    # This ensures consistency if MedicationData changes
    meds_to_store = [med.dict() for med in data.medications]
    fake_users_db[data.username]["medications"] = meds_to_store
    
    return {"message": "Medications saved successfully to in-memory storage."}

@app.get("/load_medications/{username}", response_model=LoadMedicationsResponse)
async def load_user_medications(username: str):
    """
    Loads the user's saved medication list from in-memory storage.
    """
    stored_user = fake_users_db.get(username)
    if not stored_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Convert stored dictionaries back to MedicationData Pydantic models
    loaded_meds = [MedicationData(**med_dict) for med_dict in stored_user["medications"]]
    
    return {"medications": loaded_meds}


@app.post("/analyze_medications") # Changed endpoint name for clarity
async def analyze_medications(med_input: MedicationInput):
    """
    Simulates medication analysis and returns placeholder alerts.
    This replaces the complex logic and database interactions for testing.
    """
    entered_med_names = [med.name for med in med_input.medications] # Access .name directly
    entered_active_ingredients = [
        ai.lower() for med in med_input.medications
        for ai in med.active_ingredients if ai != "UNKNOWN" # Access .active_ingredients directly
    ]

    simulated_alerts = []

    # Simulate duplicate active ingredient check
    ingredient_counts = {}
    for ing in entered_active_ingredients:
        ingredient_counts[ing] = ingredient_counts.get(ing, 0) + 1

    for ing, count in ingredient_counts.items():
        if count > 1:
            # Find which original meds contain this duplicate ingredient
            meds_with_dup = [
                m.name for m in med_input.medications # Access .name directly
                if ing in [ai.lower() for ai in m.active_ingredients] # Access .active_ingredients directly
            ]
            simulated_alerts.append(AlertOutput(
                alert_type="Duplicate",
                drugs_involved=list(set(meds_with_dup)),
                alert_message=f"You have listed multiple medications that contain '{ing}'. This could lead to overdose."
            ).dict()) # .dict() to convert Pydantic model to dict

    # Simulate interactions for specific pairs (if present)
    # Using a simple hardcoded interaction logic for testing
    if "lisinopril" in entered_active_ingredients and "calcium carbonate" in entered_active_ingredients:
        simulated_alerts.append(AlertOutput(
            alert_type="Interaction",
            drugs_involved=["Lisinopril", "Calcium Carbonate"],
            alert_message="Potential minor interaction: Lisinopril absorption may be reduced by Calcium Carbonate. Consult your doctor."
        ).dict())

    if "aspirin" in entered_active_ingredients and "clopidogrel" in entered_active_ingredients:
        simulated_alerts.append(AlertOutput(
            alert_type="Interaction",
            drugs_involved=["Aspirin", "Clopidogrel"],
            alert_message="Increased risk of bleeding when Aspirin and Clopidogrel are taken together. Consult your doctor."
        ).dict())

    # If no specific alerts, return a "No Issue" alert
    if not simulated_alerts:
        simulated_alerts.append(AlertOutput(
            alert_type="No Issue",
            drugs_involved=entered_med_names if entered_med_names else ["No medications entered"],
            alert_message="No significant drug-drug interactions or duplicates detected for the provided medications."
        ).dict())

    return {"alerts": simulated_alerts}


# --- To Run This Simplified FastAPI App Locally ---
# 1. Save this file as `main.py` in  `rxradar_backend` directory.
# 2. Open terminal and navigate to the `rxradar_backend` directory.
# 3. Ensure virtual environment is active. Ensure requirements.txt is installed there, too. 
# 4. Run: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
#    This will start the backend server. Keep this terminal open.
