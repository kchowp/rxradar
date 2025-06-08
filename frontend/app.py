import streamlit as st
import requests
import json # For displaying backend response if needed

# --- Page Configuration & Global Settings ---
st.set_page_config(
    page_title="RxRadar: Smart Medication Management",
    layout="wide", # Use wide layout for better use of space
    initial_sidebar_state="expanded"
)

# Define backend URL (placeholder - update when FastAPI is running)
# For local development:
BACKEND_URL = "http://localhost:8000"
# For EC2 deployment:
# BACKEND_URL = "http://EC2_PUBLIC_IP:8000" # !!! IMPORTANT: REPLACE WITH  ACTUAL EC2 IP !!!


# --- Helper Functions ---
def display_color_coded_med(med_name, warning_type=None):
    """Displays a medication name with an optional color-coded warning."""
    color_map = {
        "Duplicate": "orange",
        "Interaction": "red",
        "Missing Info": "gray",
        "No Issue": "green"
    }
    icon_map = {
        "Duplicate": "⚠️",
        "Interaction": "🚨",
        "Missing Info": "❓",
        "No Issue": "✅"
    }
    
    if warning_type and warning_type in color_map:
        color = color_map[warning_type]
        icon = icon_map[warning_type]
        st.markdown(f'<span style="color:{color};">{icon} **{med_name}**</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span>✅ {med_name}</span>', unsafe_allow_html=True)

def display_alert_card(alert_data):
    """Displays a single alert with icons and plain language."""
    drugs = ", ".join(alert_data.get("drugs_involved", []))
    risk_score = alert_data.get("risk_score", "N/A")
    message = alert_data.get("alert_message", "No specific message provided.")
    alert_type = alert_data.get("alert_type", "Interaction") # Default to Interaction for icons

    # Simple icon mapping based on common alert types
    icon_char = "⚠️"
    if alert_type == "Interaction":
        icon_char = "🚨"
    elif alert_type == "Duplicate":
        icon_char = "👯"
    elif alert_type == "Missing Info":
        icon_char = "❓"

    st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h4>{icon_char} {alert_type} Alert: {drugs}</h4>
            <p><strong>Risk Score:</strong> {risk_score:.2f}</p>
            <p>{message}</p>
            <details>
                <summary>Detailed Context (Click to expand)</summary>
                <p><i>(Detailed context would go here - e.g., mechanism of action, specific patient factors.)</i></p>
            </details>
            <div style="text-align: right;">
                <button style="background-color: #4CAF50; color: white; padding: 8px 12px; border: none; border-radius: 5px; cursor: pointer;">Dismiss</button>
                <button style="background-color: #008CBA; color: white; padding: 8px 12px; border: none; border-radius: 5px; cursor: pointer; margin-left: 5px;">Share with Provider</button>
            </div>
        </div>
    """, unsafe_allow_html=True)


# --- Sidebar Navigation ---
st.sidebar.title("RxRadar Navigation")
user_role = st.sidebar.radio(
    "Select Your Role:",
    ("Patient", "Caregiver"),
    key="user_role"
)

st.sidebar.markdown("---")
st.sidebar.header("Account & Profile")
if user_role == "Patient":
    st.sidebar.text_input("Username", key="patient_username", value="demo_patient")
    st.sidebar.text_input("Password", type="password", key="patient_password")
    st.sidebar.button("Login / Create Account", key="patient_login_btn")
else: # Caregiver
    st.sidebar.text_input("Caregiver Username", key="caregiver_username", value="demo_caregiver")
    st.sidebar.text_input("Password", type="password", key="caregiver_password")
    st.sidebar.button("Login / Create Account (Caregiver)", key="caregiver_login_btn")
    st.sidebar.selectbox("Manage Profile For:", ["Mom (97, Seizures)", "Dad (82, Diabetes)"], key="managed_profile")
    st.sidebar.button("Add New Patient Profile", key="add_new_patient_btn")

st.sidebar.markdown("---")
st.sidebar.header("App Features")
st.sidebar.write("✅ Input Medications")
st.sidebar.write("✅ View Alerts")
if user_role == "Caregiver":
    st.sidebar.write("✅ Manage Multiple Profiles")
st.sidebar.write("✅ Monthly Check-ins")
st.sidebar.write("✅ Data Privacy & Sharing")


# --- Main Content Area ---
st.title("RxRadar: Smart Medication Management for Your Health")
st.markdown("Your personalized shield against medication risks.")

# --- Section 1: Tutorial/Onboarding ---
with st.expander("👋 Welcome to RxRadar! Quick Tour & Privacy", expanded=False):
    st.markdown("""
        ### App Purpose
        RxRadar helps you safely manage your medications by flagging potential issues like
        drug interactions, duplicates, and missing information. Our goal is to empower
        you with clear, plain-language insights for better health discussions with your doctor.

        ### Data Privacy (HIPAA Right to Direct)
        Your health data is highly sensitive, and we prioritize your privacy. RxRadar adheres to
        HIPAA guidelines. We will prompt you to explicitly share your personal health
        information (PHI) from providers via the HIPAA Right to Direct rule.
        Your data is encrypted and used only to provide personalized alerts.
        You have full control over your data and can withdraw consent at any time.
    """)
    st.info("💡 **Accessibility Note:** We aim for large text, high contrast, and clear visual hierarchy. Optional voice input is a future goal.")

# --- Section 2: Medication Input ---
st.header("1. Your Current Medications")
st.write("Enter your prescription and over-the-counter medications below.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Manual Entry")
    st.info("Enter one medication name (e.g., Warfarin 5mg daily) per line.")
    manual_meds_input = st.text_area(
        "Prescription Medications (e.g., 'Warfarin 5mg daily'):",
        height=150,
        placeholder="Warfarin 5mg daily\nAspirin 81mg daily\nLisinopril 10mg once a day"
    )
    otc_meds_input = st.text_area(
        "Over-the-Counter & Supplements (e.g., 'Ibuprofen', 'Vitamin D'):",
        height=100,
        placeholder="Ibuprofen 200mg as needed\nVitamin D 1000 IU daily"
    )
    
    # Split input into lists
    current_prescriptions = [m.strip() for m in manual_meds_input.split('\n') if m.strip()]
    current_otc_supps = [m.strip() for m in otc_meds_input.split('\n') if m.strip()]
    all_entered_meds = current_prescriptions + current_otc_supps

with col2:
    st.subheader("Advanced Input (Stretch Goals)")
    st.info("These features aim to make input even easier in the future!")
    st.image("https://placehold.co/400x150/aabbcc/ffffff?text=OCR+Scan+Pill+Bottle+Placeholder", caption="Stretch Goal: OCR Scan Pill Bottle")
    st.button("Upload Pill Bottle Photo", key="ocr_button")
    
    st.image("https://placehold.co/400x150/ccddee/ffffff?text=Pharmacy+Sync+Placeholder", caption="Additional Stretch Goal: Sync from Pharmacy/Providers")
    st.button("Sync from My Pharmacy/Providers", key="sync_button")
    st.caption("Requires HIPAA Right to Direct consent below.")


# --- Section 3: PHI Sharing Prompt ---
st.header("2. Share Your Health Information (Optional)")
st.warning("RxRadar can provide more precise alerts by securely accessing your Personal Health Information (PHI) from providers via HIPAA Right to Direct.")
phi_consent = st.checkbox("✅ I understand and consent to RxRadar requesting my PHI via HIPAA Right to Direct.", key="phi_consent_checkbox")
if phi_consent:
    st.success("Consent received! RxRadar will now attempt to securely request your PHI.")
    # Placeholder for actual PHI request process
    st.button("Initiate PHI Sync Now", key="phi_sync_button")


# --- Section 4: Analyze & View Alerts ---
st.header("3. Analyze & View Alerts")
st.write("Click 'Analyze Medications' to check your current list for potential issues.")

analyze_button = st.button("Analyze Medications", key="analyze_button", type="primary")

st.markdown("---") # Separator for clarity

col_med_list, col_alerts = st.columns([1, 2])

with col_med_list:
    st.subheader("Your Medication List")
    if all_entered_meds:
        for med in all_entered_meds:
            # Simulate some color-coded warnings based on a very simple check
            if "warfarin" in med.lower() and "aspirin" in med.lower():
                display_color_coded_med(med, "Interaction")
            elif "ibuprofen" in med.lower() and "advil" in med.lower(): # Simple duplicate check
                display_color_coded_med(med, "Duplicate")
            elif "unknown" in med.lower(): # Example of missing info
                display_color_coded_med(med, "Missing Info")
            else:
                display_color_coded_med(med, "No Issue")
        st.caption("🚦 Color-coding: Red = Interaction, Orange = Duplicate, Gray = Missing Info, Green = No Issue")
    else:
        st.info("No medications entered yet.")

with col_alerts:
    st.subheader("Potential Concerns & Alerts")
    if analyze_button:
        if not all_entered_meds:
            st.warning("Please enter some medications to analyze.")
        else:
            # --- Prepare data for FastAPI ---
            payload = {
                "notes": patient_notes,
                "medications": all_entered_meds
            }
            headers = {"Content-Type": "application/json"}
            
            st.info("Sending data to RxRadar backend for analysis...")

            # --- Make Request to FastAPI ---
            try:
                with st.spinner('Analyzing... This might take a moment.'):
                    # Call the backend
                    response = requests.post(f"{BACKEND_URL}/analyze_medications", json=payload, headers=headers, timeout=60)
                    response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
                
                alerts_data = response.json()

                if isinstance(alerts_data, list) and alerts_data:
                    st.success("Analysis Complete! Review alerts below.")
                    for alert in alerts_data:
                        display_alert_card(alert)
                else:
                    st.info("No significant medication risks or interactions detected for this patient based on current analysis. (Backend returned no alerts or an unexpected format).")
                    # For debugging, maybe show raw response: st.write(alerts_data)

            except requests.exceptions.ConnectionError:
                st.error(f"❌ Could not connect to the RxRadar backend at {BACKEND_URL}. Is the backend running?")
            except requests.exceptions.Timeout:
                st.error("⌛ The request to the backend timed out. Analysis took too long.")
            except requests.exceptions.HTTPError as e:
                st.error(f"🚨 Backend returned an error: {e}. Status code: {response.status_code}")
                if response.text:
                    st.code(response.text) # Show response body for debugging
            except json.JSONDecodeError:
                st.error("🚫 Backend returned an invalid JSON response.")
                st.code(response.text)
            except Exception as e:
                st.error(f"An unexpected error occurred during analysis: {e}")
    else:
        st.info("Click 'Analyze Medications' to begin. Alerts will appear here.")


# --- Section 5: Caregiver-Specific Features (Conditional) ---
if user_role == "Caregiver":
    st.header("Caregiver Dashboard")
    st.write("Manage medication profiles for multiple patients from a single account.")
    
    st.info("💡 **Monthly Check-in Reminders:** RxRadar can send automated reminders to patients/caregivers to review and update medication lists. (Future Feature)")
    st.info("💡 **Real-time Alerts for Detected Changes:** Get notifications if new data (e.g., from synced pharmacy) suggests a new interaction. (Future Feature)")
    
    st.subheader("Managed Patient Profiles:")
    # Mock data for managed profiles
    st.dataframe({
        "Patient Name": ["Mom (97)", "Dad (82)", "Aunt Carol (75)"],
        "Last Review": ["2025-05-15", "2025-06-01", "2025-04-20"],
        "Active Alerts": ["2 (High)", "0", "1 (Moderate)"],
        "Actions": ["View Profile", "View Profile", "View Profile"]
    })
    
    if st.button("Add New Patient Profile", key="add_profile_bottom"):
        st.write("Redirecting to New Patient Onboarding...") # Placeholder


# --- Section 6: User Feedback & Historical Data ---
st.header("User Engagement & Trust")
st.write("Help us improve RxRadar and review your past analyses.")

col_feedback, col_history = st.columns(2)

with col_feedback:
    st.subheader("Feedback & Usability")
    st.slider("How useful was this alert?", 1, 5, 4, key="alert_usefulness_slider")
    st.text_area("Any suggestions or issues?", key="feedback_text_area")
    st.button("Submit Feedback", key="submit_feedback_btn")
    st.info("💡 **User feedback mechanisms** are crucial for refining RxRadar's usability and accuracy.")

with col_history:
    st.subheader("Analysis History & Audit Log")
    st.dataframe({
        "Date/Time": ["2025-06-07 10:30 AM", "2025-06-01 02:45 PM"],
        "Notes Snapshot": ["Patient reports pain...", "New prescriptions..."],
        "Alerts Count": [2, 1],
        "Overall Risk": ["High", "Low"]
    })
    st.info("💡 **Transparent audit logging** provides a record of past analyses for review.")


# --- Footer ---
st.markdown("---")
st.markdown("""
    <div style="text-align: center; font-size: 0.9em; color: #666;">
        RxRadar Demo Project | Designed for Clarity, Ease of Use, and Empowerment.
        <br>
        <span style="font-style: italic;">Disclaimer: This is a demonstration tool and does not provide medical advice. Consult a healthcare professional for all medication decisions.</span>
    </div>
""", unsafe_allow_html=True)
