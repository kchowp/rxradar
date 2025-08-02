import pandas as pd
import os
import requests
from functools import lru_cache
from fuzzywuzzy import process
import asyncio

API_KEYS = os.getenv("GEMINI_API_KEY","").split(",")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = BASE_DIR  # CSVs are in the project root

alt_names_df = pd.read_csv(os.path.join(PROJECT_DIR, "rxradar_alternate_drug_names.csv"))
baseline_df = pd.read_csv(os.path.join(PROJECT_DIR, "baseline_model_data.csv"))

@lru_cache(maxsize=500)
def resolve_drugbank_id(name: str) -> str:
    match = alt_names_df[alt_names_df['alternate_drug_name'].str.lower() == name.lower()]
    if not match.empty:
        return match.iloc[0]['drugbank_id']
    return name

known_drug_names = alt_names_df['alternate_drug_name'].dropna().unique().tolist()

def suggest_closest_drug_name(name: str, threshold=80) -> str:
    match, score = process.extractOne(name, known_drug_names)
    return match if score >= threshold else None


def generate_geriatric_alert(drugs: str) -> str:
    """
    Takes a comma-separated string with two drug names, returns a plain-language alert.
    Example: "Lepirudin, Bivalirudin"
    """
    drug_list = [d.strip() for d in drugs.split(",")]
    if len(drug_list) != 2:
        return "Please provide exactly two drug names, separated by a comma."

    drug1, drug2 = drug_list

    row = baseline_df[
        ((baseline_df['min_drug_name'].str.lower() == drug1.lower()) &
         (baseline_df['max_drug_name'].str.lower() == drug2.lower())) |
        ((baseline_df['min_drug_name'].str.lower() == drug2.lower()) &
         (baseline_df['max_drug_name'].str.lower() == drug1.lower()))
    ]

    if row.empty:
        return f"No known interaction found between {drug1.title()} and {drug2.title()} in the system."

    row = row.iloc[0]

    # Extract common fields
    min_drug = row['min_drug_name']
    max_drug = row['max_drug_name']
    alert_lines = [f"**Interaction Alert: {min_drug} + {max_drug}**"]

    severity = row['severity'].capitalize()
    if severity.lower() == "unknown":
        alert_lines.append("- Severity: Not formally determined")
    else:
        alert_lines.append(f"- Severity Level: **{severity}**")

    # Description and interaction meaning
    if row['description'] != "Information not available":
        alert_lines.append(f"\n🧾 What this means: {row['description']}")

    if row['atc_group_context'] != "Information not available":
        alert_lines.append(f"\n🧪 These drugs belong to the same treatment group: {row['atc_group_context']}")

    # Drug classes
    alert_lines.append(f"\n🔍 {min_drug} is a type of {row['min_drug_class']}")
    alert_lines.append(f"🔍 {max_drug} is a type of {row['max_drug_class']}")

    # Optional: mechanism of action
    if row['min_mechanism_of_action'] != "Information not available":
        alert_lines.append(f"\n🧬 {min_drug} works by: {row['min_mechanism_of_action']}")
    if row['max_mechanism_of_action'] != "Information not available":
        alert_lines.append(f"🧬 {max_drug} works by: {row['max_mechanism_of_action']}")

    # Optional: elimination
    if row['min_route_of_elimination'] != "Information not available":
        alert_lines.append(f"\n🚽 {min_drug} leaves the body through: {row['min_route_of_elimination']}")
    if row['max_route_of_elimination'] != "Information not available":
        alert_lines.append(f"🚽 {max_drug} leaves the body through: {row['max_route_of_elimination']}")

    # Optional: toxicity
    if row['min_toxicity'] != "Information not available":
        alert_lines.append(f"\n☠️ Toxicity concern for {min_drug}: {row['min_toxicity']}")
    if row['max_toxicity'] != "Information not available":
        alert_lines.append(f"☠️ Toxicity concern for {max_drug}: {row['max_toxicity']}")

    # Side effects summary
    if row['effects_summary'] != "Information not available":
        alert_lines.append(f"\n⚠️ Reported Side Effects:\n{row['effects_summary']}")

    alert_lines.append("\n👩‍⚕️ Please consult your doctor or pharmacist before taking these medications together.")

    return "\n".join(alert_lines)

def analyze_interaction(drug1: str, drug2: str) -> str:
    drug1_clean = drug1.strip().lower()
    drug2_clean = drug2.strip().lower()

    # Build your plain-language context
    context = generate_geriatric_alert(f"{drug1_clean}, {drug2_clean}")

    # Compose the new prompt
    prompt = f"""
#Task
You are a clear, calm, and professional assistant who explains drug interactions in a way that is easy for older adults to understand.
#Step1
Use this information to get the medical interaction details in your response: {context}
#Step2
Think step-by-step:
- What is the severity?
- What does each drug do?
- What are the important mechanisms, risks, or side effects?
#Step3
Summarize this in plain language, starting with the key risk.
Avoid casual or conversational fillers. Use short, clear sentences. Do not start with 'Okay' or 'Let's break it down.'
Finish with a gentle reminder to talk to a healthcare provider.
"""

    return call_gemini(prompt)

def call_gemini(prompt: str) -> str:
    print("DEBUG: Prompt being sent to Gemini:", prompt)
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ]
            }
    headers = {
                "Content-Type": "application/json",
            }
    for api_key in API_KEYS:
            headers["x-goog-api-key"] = api_key.strip()
            response = requests.post(url, headers=headers, json=payload) 
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"] 
            
async def analyze_all_pairs(meds):
    results = []
    for i in range(len(meds)):
        for j in range(i + 1, len(meds)):
            drug1, drug2 = meds[i], meds[j]
            try:
                alert_message = await asyncio.to_thread(analyze_interaction, drug1, drug2)
                results.append({
                    "pair": f"{drug1} + {drug2}",
                    "alert_type": "Interaction",
                    "drugs_involved": [drug1, drug2],
                    "alert_message": alert_message,
                })
            except Exception as e:
                results.append({
                    "pair": f"{drug1} + {drug2}",
                    "alert_type": "Error",
                    "drugs_involved": [drug1, drug2],
                    "alert_message": f"Error analyzing: {str(e)}"
                })
    return results
