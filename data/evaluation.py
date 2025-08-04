'''Non-production workfile - only provided to show context. Necessary dependencies must be installed seperately if this file is to be run'''

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import re

# --- Configurable paths ---
DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
BASELINE_PATH = DATA_DIR / "baseline_model_data.csv"
MODEL_OUTPUT_PATH = DATA_DIR / "model_output.csv"

# --- Load Data ---
df_baseline = pd.read_csv(BASELINE_PATH)
df_model_output = pd.read_csv(MODEL_OUTPUT_PATH)

# --- Alert Generation (Ground Truth Reference) ---
def generate_geriatric_alert(drugs: str) -> str:
    drug_list = [d.strip() for d in drugs.split(",")]
    if len(drug_list) != 2:
        return "Please provide exactly two drug names, separated by a comma."

    drug1, drug2 = drug_list
    row = df_baseline[
        ((df_baseline['min_drug_name'].str.lower() == drug1.lower()) &
         (df_baseline['max_drug_name'].str.lower() == drug2.lower())) |
        ((df_baseline['min_drug_name'].str.lower() == drug2.lower()) &
         (df_baseline['max_drug_name'].str.lower() == drug1.lower()))
    ]

    if row.empty:
        return f"No known interaction found between {drug1.title()} and {drug2.title()} in the system."

    row = row.iloc[0]
    alert_lines = [f"Interaction Alert: {row['min_drug_name']} + {row['max_drug_name']}"]
    severity = row['severity'].capitalize()
    alert_lines.append(f"- Severity Level: {severity if severity.lower() != 'unknown' else 'Not formally determined'}")

    if row['description'] != "Information not available":
        alert_lines.append(f"\nWhat this means: {row['description']}")
    if row['effects_summary'] != "Information not available":
        alert_lines.append(f"\nReported Side Effects:\n{row['effects_summary']}")
    if row['min_mechanism_of_action'] != "Information not available":
        alert_lines.append(f"\n{row['min_drug_name']} works by: {row['min_mechanism_of_action']}")
    if row['max_mechanism_of_action'] != "Information not available":
        alert_lines.append(f"{row['max_drug_name']} works by: {row['max_mechanism_of_action']}")

    return "\n".join(alert_lines)

# --- Evaluation Utilities ---
def is_no_interaction(text): return "no known interaction found" in text.lower()

def extract_severity(text):
    text = text.lower()
    for level in ["major", "moderate", "minor", "unknown"]:
        if level in text:
            return level
    if "no known interaction" in text or "not formally determined" in text:
        return "unknown"
    return None

def extract_ground_truth_severity(text):
    if is_no_interaction(text): return "none"
    if "severity: not formally determined" in text.lower(): return "unknown"
    match = re.search(r"severity level:\s+\*\*(\w+)\*\*", text.lower())
    return match.group(1) if match else None

def evaluate_severity(row):
    gt = generate_geriatric_alert(row["query"])
    pred = row["agent_response"]
    gt_severity = extract_ground_truth_severity(gt)
    pred_severity = extract_severity(pred)
    match = pred_severity == gt_severity if gt_severity != "none" else is_no_interaction(pred)
    return pd.Series({
        "Predicted_Severity": pred_severity,
        "Expected_Severity": gt_severity,
        "Severity_Match": match,
        "Ground_Truth_Alert": gt
    })

# --- Additional Metric Checks ---
def normalize(text): return re.sub(r"[^\w\s]", "", text.lower()) if isinstance(text, str) else ""

def extract_keywords(alert):
    alert = normalize(alert)
    parts = []
    if "what this means" in alert:
        parts.append(alert.split("what this means", 1)[-1])
    if "reported side effects" in alert:
        parts.append(alert.split("reported side effects", 1)[-1])
    keywords = [word for part in parts for word in part.split() if len(word) > 4]
    return set(keywords)

def extract_mechanisms(alert):
    alert = normalize(alert)
    patterns = [r"works by\s+(.*?)\n", r"affects\s+(.*?)\n", r"blocks\s+(.*?)\n"]
    phrases = []
    for pattern in patterns:
        phrases += re.findall(pattern, alert)
    return set(word for phrase in phrases for word in phrase.split())

def match_metrics(row):
    agent_text = normalize(row["agent_response"])
    gt_keywords = extract_keywords(row["Ground_Truth_Alert"])
    gt_mechs = extract_mechanisms(row["Ground_Truth_Alert"])

    keyword_hits = [kw for kw in gt_keywords if kw in agent_text]
    mechanism_match = bool(set(agent_text.split()) & gt_mechs) or row["Expected_Severity"] == "none"

    return pd.Series({
        "Matched_Keywords": keyword_hits,
        "Mechanism_Match": mechanism_match,
        "Keyword_Coverage": round(len(keyword_hits) / len(gt_keywords), 2) if gt_keywords else None
    })

def drugs_mentioned(row):
    return all(d.strip().lower() in row["agent_response"].lower() for d in row["query"].split(","))

def is_concise(text, limit=80): return len(text.split()) <= limit

def avoids_jargon(text):
    terms = [
        "antiplatelet", "vasodilation", "pharmacokinetics", "contraindicated", "hepatic", "renal",
        "bioavailability", "synergistic", "myocardial", "hypokalemia"
    ]
    return not any(term in text.lower() for term in terms)

def has_risk_language(text):
    patterns = ["talk to your doctor", "consult your doctor", "may cause", "dangerous interaction"]
    return any(p in text.lower() for p in patterns)

def has_explanation(text):
    explanation_patterns = [
        r"may increase.*risk", r"may reduce.*effect", r"interferes with.*absorption",
        r"because", r"which can", r"leading to", r"resulting in"
    ]
    return any(re.search(p, text.lower()) for p in explanation_patterns)

def safe_explanation(row):
    return True if row["Expected_Severity"] == "unknown" else has_explanation(row["agent_response"])

# --- Main Evaluation ---
df_eval = df_model_output.copy()
df_eval = df_eval.join(df_eval.apply(evaluate_severity, axis=1))
df_eval = df_eval.join(df_eval.apply(match_metrics, axis=1))

df_eval["Drugs_Mentioned"] = df_eval.apply(drugs_mentioned, axis=1)
df_eval["Concise"] = df_eval["agent_response"].apply(is_concise)
df_eval["Avoids_Jargon"] = df_eval["agent_response"].apply(avoids_jargon)
df_eval["Has_Risk_Language"] = df_eval["agent_response"].apply(has_risk_language)
df_eval["Has_Explanation"] = df_eval.apply(safe_explanation, axis=1)

# --- Visual Summary ---
def plot_overall_pass_rate(df):
    metric_cols = ['Severity_Match', 'Mechanism_Match', 'Drugs_Mentioned',
                   'Concise', 'Avoids_Jargon', 'Has_Risk_Language', 'Has_Explanation']
    pass_rates = df[metric_cols].mean().sort_values()
    pass_rates.plot(kind="barh", color="steelblue")
    plt.title("Pass Rate by Metric")
    plt.xlabel("Rate")
    plt.tight_layout()
    plt.show()

def plot_pass_rate_by_severity(df):
    df["Severity_Level"] = df["Expected_Severity"].apply(lambda x: x if x in ["major", "moderate", "minor"] else "unknown")
    metric_cols = ['Severity_Match', 'Mechanism_Match', 'Drugs_Mentioned',
                   'Concise', 'Avoids_Jargon', 'Has_Risk_Language', 'Has_Explanation']
    colors = {'major': 'firebrick', 'moderate': 'darkorange', 'minor': 'mediumseagreen', 'unknown': 'slateblue'}
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    axs = axs.flatten()

    for idx, severity in enumerate(colors.keys()):
        subset = df[df["Severity_Level"] == severity]
        if subset.empty: continue
        rates = subset[metric_cols].mean().sort_values()
        axs[idx].barh(rates.index, rates.values, color=colors[severity])
        axs[idx].set_title(f"{severity.capitalize()} Interactions")
        axs[idx].set_xlim(0, 1)

    plt.tight_layout()
    plt.suptitle("Pass Rate by Severity", y=1.02)
    plt.show()

if __name__ == "__main__":
    print("✅ Evaluation completed.")
    plot_overall_pass_rate(df_eval)
    plot_pass_rate_by_severity(df_eval)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_eval.to_csv(OUTPUT_DIR / "evaluation_results.csv", index=False)
