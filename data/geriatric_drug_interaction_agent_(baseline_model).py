'''Non-production workfile - only provided to show context. Necessary dependencies must be installed seperately if this file is to be run'''
import os
import re
import asyncio
import pandas as pd
from tqdm import tqdm
from pathlib import Path
import warnings
import logging

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)

# === Configuration ===
DATA_PATH = Path("data/baseline_model_data.csv")
OUTPUT_PATH = Path("outputs/baseline_eval.csv")

API_KEY = os.getenv("GOOGLE_API_KEY")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

if not API_KEY:
    raise EnvironmentError("GOOGLE_API_KEY not set in environment.")

MODEL_GEMINI = "gemini-2.0-flash"
MODEL_GPT4O = "openai/gpt-4.1"
MODEL_CLAUDE = "anthropic/claude-sonnet-4-20250514"

MODELS = [MODEL_GEMINI, MODEL_GPT4O, MODEL_CLAUDE]

# === Load Data ===
df_baseline_table = pd.read_csv(DATA_PATH)

# === Alert Generation Function ===
def generate_geriatric_alert(drugs: str) -> str:
    drug_list = [d.strip() for d in drugs.split(",")]
    if len(drug_list) != 2:
        return "Please provide exactly two drug names, separated by a comma."

    drug1, drug2 = drug_list
    row = df_baseline_table[
        ((df_baseline_table['min_drug_name'].str.lower() == drug1.lower()) &
         (df_baseline_table['max_drug_name'].str.lower() == drug2.lower())) |
        ((df_baseline_table['min_drug_name'].str.lower() == drug2.lower()) &
         (df_baseline_table['max_drug_name'].str.lower() == drug1.lower()))
    ]

    if row.empty:
        return f"No known interaction found between {drug1.title()} and {drug2.title()} in the system."

    row = row.iloc[0]
    min_drug = row['min_drug_name']
    max_drug = row['max_drug_name']

    lines = [f"Interaction Alert: {min_drug} + {max_drug}"]

    severity = row['severity'].capitalize()
    lines.append(f"- Severity Level: {severity if severity.lower() != 'unknown' else 'Not formally determined'}")

    if row['description'] != "Information not available":
        lines.append(f"\nWhat this means: {row['description']}")
    if row['atc_group_context'] != "Information not available":
        lines.append(f"\nShared treatment group: {row['atc_group_context']}")
    lines.append(f"\n{min_drug} is a type of {row['min_drug_class']}")
    lines.append(f"{max_drug} is a type of {row['max_drug_class']}")

    if row['min_mechanism_of_action'] != "Information not available":
        lines.append(f"\n{min_drug} mechanism: {row['min_mechanism_of_action']}")
    if row['max_mechanism_of_action'] != "Information not available":
        lines.append(f"{max_drug} mechanism: {row['max_mechanism_of_action']}")

    if row['min_route_of_elimination'] != "Information not available":
        lines.append(f"\n{min_drug} elimination: {row['min_route_of_elimination']}")
    if row['max_route_of_elimination'] != "Information not available":
        lines.append(f"{max_drug} elimination: {row['max_route_of_elimination']}")

    if row['min_toxicity'] != "Information not available":
        lines.append(f"\n{min_drug} toxicity: {row['min_toxicity']}")
    if row['max_toxicity'] != "Information not available":
        lines.append(f"{max_drug} toxicity: {row['max_toxicity']}")

    if row['effects_summary'] != "Information not available":
        lines.append(f"\nReported Side Effects:\n{row['effects_summary']}")

    lines.append("\nPlease consult your doctor or pharmacist before taking these medications together.")
    return "\n".join(lines)

# === Prompt Variants ===
prompt_variants = {
    "baseline": "...",  # Keep full strings from your notebook here
    "few_shot": "...",
    "chain_of_thought": "...",
    "persona_prompting": "...",
    "fallback_reasoning": "..."
}

def make_agent(model, prompt, label):
    name = f"agent_{re.sub(r'\\W+', '_', model)}_{re.sub(r'\\W+', '_', label)}".lower()
    return Agent(
        name=name,
        model=model,
        description="Geriatric drug interaction assistant.",
        instruction=prompt,
        tools=[generate_geriatric_alert]
    )

async def call_agent_async(query, runner, user_id, session_id):
    content = types.Content(role="user", parts=[types.Part(text=query)])
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response() and event.content and event.content.parts:
            return event.content.parts[0].text.strip()
    return "[No valid response]"

async def main():
    queries = [
        "Warfarin, Amiodarone", "Simvastatin, Amlodipine", "Omeprazole, Clopidogrel",
        "Atorvastatin, Clarithromycin", "Allopurinol, Azathioprine",
        "Metformin, Furosemide", "Levothyroxine, Calcium Carbonate",
        "Ibuprofen, Lisinopril", "Simvastatin, Atorvastatin", "Omeprazole, Warfarin"
    ]

    results = []
    session_service = InMemorySessionService()
    session = await session_service.create_session("drug_app", "user1", "session1")

    for model in tqdm(MODELS, desc="Models"):
        for label, prompt in prompt_variants.items():
            agent = make_agent(model, prompt, label)
            runner = Runner(agent=agent, app_name="drug_app", session_service=session_service)
            for query in queries:
                try:
                    response = await call_agent_async(query, runner, "user1", "session1")
                    results.append({"query": query, "prompt": label, "response": response})
                    await asyncio.sleep(2)
                except Exception as e:
                    results.append({"query": query, "prompt": label, "response": f"[Error: {e}]"})
    
    df = pd.DataFrame(results)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"✅ Saved results to {OUTPUT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
