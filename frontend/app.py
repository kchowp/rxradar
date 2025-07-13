import streamlit as st
import requests
import json # For displaying backend response if needed
import time # For delay
import difflib # For spell-checking/suggestions



# --- Page Configuration & Global Settings ---
st.set_page_config(
    page_title="RxRadar: Smart Medication Management",
    layout="wide", # Use wide layout for better use of space
    initial_sidebar_state="collapsed" # Start collapsed for a cleaner look
)

# --- Custom CSS for Larger Text ---
st.markdown("""
    <style>
    html, body, [class*="st-emotion"] {
        font-size: 18px; /* Base font size for the entire app */
    }
    h1 {
        font-size: 2.5em !important; /* Larger for main titles */
    }
    h2 {
        font-size: 2em !important; /* Larger for section titles */
    }
    h3 {
        font-size: 1.75em !important; /* Larger for sub-sections */
    }
    h4 {
        font-size: 1.5em !important; /* Larger for alert card titles */
    }
    p, li, div, .stMarkdown, .stText, .stTextInput, .stButton, .stCheckbox, .stRadio, .stSelectbox, .stTextArea {
        font-size: 1.1em; /* Slightly larger for general text and inputs */
    }
    .stAlert {
        font-size: 1.1em;
    }
    .stSpinner {
        font-size: 1.1em;
    }
    /* Adjust button text size */
    .stButton > button {
        font-size: 1.1em !important;
    }
    /* Adjust input field text size */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        font-size: 1.1em !important;
    }
    /* Adjust selectbox text size */
    .stSelectbox > div > label + div > div > div {
        font-size: 1.1em !important;
    }
    </style>
""", unsafe_allow_html=True)


# Define backend URL (placeholder - update when FastAPI is running)
# For local development:
BACKEND_URL = "http://localhost:8000"
# For Fargate deployment:
# BACKEND_URL = "http://FASTAPI_SERVICE_URL:8000" # !!! IMPORTANT: REPLACE WITH ACTUAL FARGATE SERVICE URL !!!

# --- Helper Functions ---
def display_alert_card(alert_data):
    """Displays a single alert with icons and plain language."""
    drugs = ", ".join(alert_data.get("drugs_involved", []))
    message = alert_data.get("alert_message", "No specific message provided.")
    alert_type = alert_data.get("alert_type", "Interaction") # Default to Interaction for icons

    # Simple icon mapping based on common alert types
    icon_char = "⚠️"
    if alert_type == "Interaction":
        icon_char = "🚨"
    elif alert_type == "Duplicate":
        icon_char = "2️⃣"
    elif alert_type == "No Issue": # Added for explicit "No Issue" icon
        icon_char = "✅"

    st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h4>{icon_char} {alert_type} Alert: {drugs}</h4>
            <p>{message}</p>
            <details>
                <summary>Detailed Context (Click to expand)</summary>
                <p><i>(Detailed context would go here - e.g., mechanism of action, pharmaceutical overlap, etc.)</i></p>
            </details>
            <div style="text-align: right;">
                <button style="background-color: #4CAF50; color: white; padding: 8px 12px; border: none; border-radius: 5px; cursor: pointer;">Dismiss</button>
                <button style="background-color: #008CBA; color: white; padding: 8px 12px; border: none; border-radius: 5px; cursor: pointer; margin-left: 5px;">Share with Provider</button>
            </div>
        </div>
    """, unsafe_allow_html=True)
# --- Mock/Placeholder for Known Drug Names ---
# In a real application, this list would be fetched from FastAPI backend
# which would query Amazon RDS PostgreSQL database.
@st.cache_data # Cache the data to avoid re-fetching on every rerun
def get_known_drug_names():
    """
    Simulates fetching a list of known drug names from a backend.
    In actual implementation, this would be a requests.get(f"{BACKEND_URL}/drugs/names") call.
    """
    # For now, use a hardcoded list.
    # try:
    #     response = requests.get(f"{BACKEND_URL}/drugs/names", timeout=5)
    #     response.raise_for_status()
    #     return response.json()
    # except requests.exceptions.RequestException as e:
    #     st.error(f"Could not fetch drug names from backend: {e}")
    #     return [] # Return empty list on error
    return [
        "Aspirin", "Clopidogrel", "Lisinopril", "Calcium Carbonate",
        "Warfarin", "Ibuprofen", "Advil", "Paracetamol", "Acetaminophen",
        "Metformin", "Insulin", "Simvastatin", "Omeprazole", "Amoxicillin",
        "Hydrochlorothiazide", "Losartan", "Atorvastatin", "Levothyroxine",
        "Albuterol", "Prednisone", "Gabapentin", "Tramadol", "Sertraline"
    ]

KNOWN_DRUG_NAMES = get_known_drug_names()
KNOWN_DRUG_NAMES_LOWER = [name.lower() for name in KNOWN_DRUG_NAMES] # Pre-process for faster lookup

# --- Global Session State Initializations ---
# These must be initialized at the top level to ensure they always exist
# before any widget tries to access them, preventing AttributeError.
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'medications' not in st.session_state:
    st.session_state.medications = [{"name": "", "dosage": "", "frequency": ""}]
if 'unrecognized_meds_to_correct' not in st.session_state:
    st.session_state.unrecognized_meds_to_correct = []
if 'show_spell_check_section' not in st.session_state:
    st.session_state.show_spell_check_section = False

# --- Login Page ---
def login_page():
    st.title("Welcome to RxRadar 📡")
    st.subheader("Your Smart Medication Management Assistant")

    st.markdown("""
        <div style="background-color: #e0f7fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3>About</h3>
            <p><strong>App Purpose:</strong> RxRadar helps you safely manage your medications by flagging potential issues like drug interactions, duplicates, and missing information. Our goal is to empower you with clear, plain-language insights for better health discussions with your doctor.</p>
            <p><strong>Disclaimer:</strong> RxRadar does not provide medical advice. Consult a healthcare professional for all medication decisions.</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("Login / Create Account")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    # Consent Checkbox and Information
    consent_given = st.checkbox("✅ I agree to the **Data Privacy and Consent Policy**", key="data_consent_checkbox")

    if st.button("Login", key="login_btn", type="primary"):
        if not username or not password:
            st.error("Please enter both username and password.")
        elif not consent_given:
            st.error("Please agree to the Data Privacy and Consent Policy to proceed.")
        else:
            # Simulate successful login for any non-empty credentials
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.success("Login successful! Redirecting to main application...")
            st.rerun() # Rerun to switch to the main app page

    with st.expander("Click here to read the Data Privacy and Consent Policy"):
        st.markdown("""
            ### RxRadar Data Privacy and Consent Policy

            At RxRadar, your privacy and control over your health data are our highest priorities. This policy outlines how your data is handled and your rights.

            **1. Patient Data Collection:**
            * **Medication Information:** We collect medication names, dosages, and frequencies that you input into the application. This data is essential for providing medication interaction and duplication alerts.

            **2. Data Usage:**
            * Your medication information is used solely for the purpose of analyzing potential drug interactions, duplicates, and providing relevant health alerts.
            * We **do not** use your personal health information for marketing, advertising, or any purpose unrelated to the direct functionality of RxRadar.
            * **No Sale of Data:** Your personal health data will never be sold to third parties.

            **3. Data Anonymization and Aggregation:**
            * **Anonymized Usage Data:** We may collect anonymized, aggregated usage data (e.g., number of analyses performed, types of alerts generated) to improve the application's performance and features.
            * Whenever possible, data used for analytical improvements or research will be de-identified and aggregated so that it cannot be associated with any individual. This process ensures your privacy while allowing us to enhance the service for all users.

            **4. Data Access:**
            * Access to your personal medication data is strictly limited to authorized personnel directly involved in maintaining and operating the RxRadar service, and only when necessary for troubleshooting or support, under strict confidentiality agreements.
            * We employ robust security measures, including encryption at rest and in transit, to protect your data from unauthorized access.

            **5. Your Control Over Your Data:**
            * **Access and Review:** You have the right to access and review the medication data you have provided at any time within the application.
            * **Correction:** You can correct or update your medication information as needed.
            * **Deletion:** You have the right to request the deletion of your account and all associated personal medication data. Upon such a request, we will permanently delete your data in accordance with applicable laws and our data retention policies.
            * **Consent Withdrawal:** By checking the box below, you provide consent for RxRadar to process your data as described in this policy. You can withdraw this consent at any time by contacting our support. Please note that withdrawing consent may limit or terminate your ability to use certain features of the application.

            **By proceeding, you acknowledge that you have read, understood, and agree to this Data Privacy and Consent Policy.**
        """)


# --- Main Application Page ---
def main_app_page():
    st.title(f"RxRadar: Welcome, {st.session_state.get('username', 'User')}!")
    st.markdown("Your personalized shield against medication risks.")

    # --- Section 1: Medication Input ---
    st.header("1. Your Current Medications")
    st.write("Enter your prescription and over-the-counter medications below.")

    # Initialize spell-check state variables
    if 'unrecognized_meds_to_correct' not in st.session_state:
        st.session_state.unrecognized_meds_to_correct = []
    if 'show_spell_check_section' not in st.session_state:
        st.session_state.show_spell_check_section = False

    # Function to add a new medication input row
    def add_medication_row():
        st.session_state.medications.append({"name": "", "dosage": "", "frequency": ""})
        # Reset spell-check state when a new row is added
        st.session_state.show_spell_check_section = False
        st.session_state.unrecognized_meds_to_correct = []


    # Display dynamic medication input fields
    for i, med in enumerate(st.session_state.medications):
        st.subheader(f"Medication {i+1}")
        cols = st.columns(3)
        
        with cols[0]:
            # Text input for medication name - no real-time autocomplete here
            st.session_state.medications[i]['name'] = st.text_input(
                "Name (e.g., Warfarin)",
                value=st.session_state.medications[i]['name'],
                key=f"med_name_input_{i}"
            )

        with cols[1]:
            st.session_state.medications[i]['dosage'] = st.text_input(
                "Dosage (e.g., 5mg)",
                value=st.session_state.medications[i]['dosage'],
                key=f"med_dosage_{i}"
            )
        with cols[2]:
            st.session_state.medications[i]['frequency'] = st.text_input(
                "Frequency (e.g., daily)",
                value=st.session_state.medications[i]['frequency'],
                key=f"med_frequency_{i}"
            )

    st.button("Add Another Medication", on_click=add_medication_row)

    # Filter out empty medication entries for analysis
    all_entered_meds = [
        med for med in st.session_state.medications
        if med['name'].strip() and med['dosage'].strip() and med['frequency'].strip()
    ]

    st.markdown("---") 

    # --- Section 2: Analyze & View Alerts ---
    st.header("2. Analyze & View Alerts")
    st.write("Click 'Analyze Medications' to check your current list for potential issues.")

    analyze_button = st.button("Analyze Medications", key="analyze_button", type="primary")

    st.subheader("Potential Concerns & Alerts")

    if analyze_button:
        if not all_entered_meds:
            st.warning("Please enter at least one complete medication (name, dosage, frequency) to analyze.")
            st.session_state.show_spell_check_section = False # Hide spell check if no meds
            st.session_state.unrecognized_meds_to_correct = []
        else:
            # --- Perform Spell Check First ---
            st.session_state.unrecognized_meds_to_correct = []
            
            for i, med_entry in enumerate(st.session_state.medications):
                typed_name_raw = med_entry['name']
                typed_name_lower = typed_name_raw.strip().lower()

                if typed_name_raw.strip() and typed_name_lower not in KNOWN_DRUG_NAMES_LOWER:
                    # Find close matches for suggestions
                    suggestions = difflib.get_close_matches(typed_name_lower, KNOWN_DRUG_NAMES, n=5, cutoff=0.6)
                    if suggestions:
                        # Add original typed name as a suggestion option
                        suggestions_with_original = [typed_name_raw] + sorted(suggestions)
                    else:
                        suggestions_with_original = [typed_name_raw] # No close matches, just keep original

                    st.session_state.unrecognized_meds_to_correct.append({
                        'index': i,
                        'original_name': typed_name_raw,
                        'suggestions': suggestions_with_original
                    })
            
            if st.session_state.unrecognized_meds_to_correct:
                st.session_state.show_spell_check_section = True
                st.warning("Some medication names were not recognized. Please review and correct them below.")
            else:
                st.session_state.show_spell_check_section = False # All recognized, proceed to analysis
                # --- Placeholder Alerts (No FastAPI call) ---
                st.info("Simulating analysis with placeholder alerts...")
                with st.spinner('Analyzing... This might take a moment.'):
                    time.sleep(2) # Simulate network delay

                    # Generate placeholder alerts based on input
                    placeholder_alerts = []
                    
                    # Check for specific interaction: Lisinopril and Calcium Carbonate
                    has_lisinopril = any("lisinopril" in med['name'].lower() for med in all_entered_meds)
                    has_calcium_carbonate = any("calcium carbonate" in med['name'].lower() for med in all_entered_meds)

                    # Check for specific interaction: Aspirin and Clopidogrel
                    has_aspirin = any("aspirin" in med['name'].lower() for med in all_entered_meds)
                    has_clopidogrel = any("clopidogrel" in med['name'].lower() for med in all_entered_meds)

                    if has_lisinopril and has_calcium_carbonate:
                        placeholder_alerts.append({
                            "alert_type": "Interaction",
                            "drugs_involved": ["Lisinopril", "Calcium Carbonate"],
                            "alert_message": (
                                "Okay, here's a summary of the interaction between Lisinopril and Calcium Carbonate, explained in plain language:\n\n"
                                "**Key Interaction:**\n\n"
                                "* **Severity:** Minor\n"
                                "* The tool did not provide specific interaction details, but it does state that you should consult with your doctor or pharmacist before taking these medications together.\n\n"
                                "**What this means for you:**\n\n"
                                "Both Lisinopril and Calcium Carbonate are related to the alimentary tract and metabolism. Lisinopril is a type of ACE inhibitor used to treat high blood pressure and heart failure, while Calcium Carbonate is often used as an antacid or calcium supplement.\n\n"
                                "**How the drugs work:**\n\n"
                                "* **Lisinopril:** It lowers blood pressure by preventing the body from producing a substance called angiotensin II, which narrows blood vessels.\n"
                                "* **Calcium Carbonate:** It neutralizes stomach acid, providing relief from heartburn and indigestion.\n\n"
                                "**How the drugs leave your body:**\n\n"
                                "* **Lisinopril:** Entirely through the urine.\n"
                                "* **Calcium Carbonate:** Mainly in the feces.\n\n"
                                "**Things to watch out for:**\n\n"
                                "* **Lisinopril:** Overdose can cause low blood pressure.\n"
                                "* **Calcium Carbonate:** While the tool did not list specific toxicities, it's important to take it as directed.\n\n"
                                "**What you should do:**\n\n"
                                "Even though the interaction is labeled as minor, it's always a good idea to talk to your doctor or pharmacist before taking these medications together. They can provide personalized advice based on your specific health situation and other medications you may be taking."
                            )
                        })
                    if has_aspirin and has_clopidogrel:
                        placeholder_alerts.append({
                            "alert_type": "Interaction",
                            "drugs_involved": ["Aspirin", "Clopidogrel"],
                            "alert_message": (
                                "Okay, let's see about Aspirin and Clopidogrel.\n\n"
                                "The system doesn't show any known interactions between Aspirin and Clopidogrel.\n\n"
                                "However, it's worth mentioning that both of these medications affect your blood's ability to clot:\n\n"
                                "* Aspirin is often used to prevent blood clots.\n"
                                "* Clopidogrel belongs to a group called Carboxylic acids and derivatives and is also used to prevent blood clots.\n\n"
                                "Because they both have similar effects, using them together could potentially increase your risk of bleeding.\n\n"
                                "To make sure you're on the safe side, please consult your doctor or pharmacist."
                            )
                        })
                    # Keep the previous interaction/duplicate checks for other scenarios
                    elif any("warfarin" in med['name'].lower() for med in all_entered_meds) and \
                         any("aspirin" in med['name'].lower() for med in all_entered_meds):
                        placeholder_alerts.append({
                            "alert_type": "Interaction",
                            "drugs_involved": ["Warfarin", "Aspirin"],
                            "alert_message": (
                                "Taking Warfarin and Aspirin together significantly increases the risk of bleeding. "
                                "This combination requires close medical supervision. Please consult your "
                                "healthcare provider immediately to review your medication regimen."
                            )
                        })
                    
                    elif any("ibuprofen" in med['name'].lower() for med in all_entered_meds) and \
                         any("advil" in med['name'].lower() for med in all_entered_meds):
                        placeholder_alerts.append({
                            "alert_type": "Duplicate",
                            "drugs_involved": ["Ibuprofen", "Advil"],
                            "alert_message": (
                                "You have listed both Ibuprofen and Advil. These are the same active medication. "
                                "Taking both simultaneously can lead to an overdose and adverse effects. "
                                "Please ensure you are not taking duplicate medications."
                            )
                        })

                    # If no specific alerts, provide a general "No Issue" message
                    if not placeholder_alerts:
                        placeholder_alerts.append({
                            "alert_type": "No Issue",
                            "drugs_involved": ["All entered medications"],
                            "alert_message": (
                                "Based on the medications provided, no significant drug-drug interactions or "
                                "duplicates were detected. Always consult your healthcare provider for personalized medical advice."
                            )
                        })

                if isinstance(placeholder_alerts, list) and placeholder_alerts:
                    st.success("Analysis Complete! Review alerts below.")
                    for alert in placeholder_alerts:
                        display_alert_card(alert)
                else:
                    st.info("No significant medication risks or interactions detected for this patient based on current analysis.")

    else: # If analyze_button was not clicked (initial load or after a rerun)
        st.info("Click 'Analyze Medications' to begin. Alerts will appear here.")
    
    # --- Display Spell Check Section if needed ---
    if st.session_state.show_spell_check_section:
        st.markdown("---")
        st.subheader("Medications Needing Review (Spell Check)")
        st.error("Please correct the following medication names before analysis can proceed.")

        # Callback function to update medication name when a suggestion is selected
        # Streamlit passes the new value of the widget as the first argument to on_change
        # Any items in 'args' are passed as subsequent arguments.
        def update_medication_name_from_suggestion_callback(selected_value_from_widget, index_of_med_to_update):
            if selected_value_from_widget: # Only update if a non-empty suggestion is chosen
                st.session_state.medications[index_of_med_to_update]['name'] = selected_value_from_widget
                # No st.rerun() here, as the main script loop will naturally rerun.


        for entry in st.session_state.unrecognized_meds_to_correct:
            med_index = entry['index']
            original_name = entry['original_name']
            suggestions = entry['suggestions']

            st.write(f"**Original Input for Medication {med_index + 1}:** `{original_name}`")
            
            # Find the index of the original_name in suggestions to set as default if available
            try:
                default_index = suggestions.index(original_name)
            except ValueError:
                default_index = 0 # Fallback if original name isn't in suggestions (shouldn't happen with current logic)

            st.selectbox(
                f"Select correction for '{original_name}':",
                options=suggestions,
                index=default_index,
                key=f"correction_select_{med_index}",
                on_change=update_medication_name_from_suggestion_callback,
                args=(med_index,) # Pass only the index as an additional argument
            )
            st.markdown("---") # Separator for clarity between corrections



    # --- Logout Button ---
    st.markdown("---")
    if st.button("Logout", key="logout_btn"):
        st.session_state['logged_in'] = False
        st.session_state.pop('username', None)
        st.session_state.pop('medications', None) # Clear meds on logout
        st.rerun()

# --- Main App Logic ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    main_app_page()
else:
    login_page()

# --- Footer ---
st.markdown("---")
st.markdown("""
    <div style="text-align: center; font-size: 0.9em; color: #666;">
        RxRadar Demo Project | Designed for Clarity, Ease of Use, and Empowerment.
        <br>
        Support: kchow2020@berkeley.edu, (908) 337-8242 
        <br>    
        <span style="font-style: italic;">Disclaimer: RxRadar does not provide medical advice. Consult a healthcare professional for all medication decisions.</span>
    </div>
""", unsafe_allow_html=True)
