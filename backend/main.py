from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import time

# Define the FastAPI app
app = FastAPI(title="RxRadar Backend Demo")

# Define the data structure for input from the frontend
class PatientData(BaseModel):
    notes: str
    medications: list[str]

# Define a simple endpoint
@app.post("/analyze_medications")
async def analyze_medications(data: PatientData):
    """
    Receives patient data and returns a mock analysis.
    """
    st.write(f"Received notes: '{data.notes[:50]}...'")
    st.write(f"Received medications: {data.medications}")

    # Simulate some processing time
    time.sleep(2)

    # Return a mock response
    mock_alerts = [
        {
            "drugs_involved": ["Warfarin", "Aspirin"],
            "risk_score": 0.85,
            "alert_message": "MOCK: High risk of bleeding with Warfarin and Aspirin. Consider alternative pain management or dose adjustment. (This is a mock alert from the backend!)"
        }
    ]

    # For a truly barebones test, you could just return a simple message:
    # return {"message": "Analysis received and processed (mock response)."}

    return mock_alerts

# This part is typically used when running the file directly for development
# In production, uvicorn is run from the command line
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)