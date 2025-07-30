import streamlit as st
import requests
import json # For displaying backend response if needed
import time # For delay
import difflib # For spell-checking/suggestions
from collections import Counter # Added for duplicate active ingredient check
import itertools # For generating combinations
import os # For path manipulation

# --- Page Configuration & Global Settings ---
st.set_page_config(
    page_title="RxRadar: Smart Medication Management",
    layout="wide", # Use wide layout for better use of space
    initial_sidebar_state="collapsed" # Start collapsed for a cleaner look
)

# --- Custom CSS for Consistent Text Sizing ---
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
    p, li, div, .stMarkdown, .stText, .stButton, .stCheckbox, .stRadio, .stTextArea {
        font-size: 1.1em; /* Slightly larger for general text and inputs */
        line-height: 1.5; /* Consistent line height for general text */
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

    /* --- Consistent Styling for Text Inputs and Selectboxes --- */
    /* Target the input fields and text areas directly */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        font-size: 1.1em !important;
        line-height: 1.5 !important; /* Ensure consistent line height */
        padding: 0.5em 0.75em !important; /* Add consistent padding */
    }

    /* Target the displayed value in the closed selectbox */
    .stSelectbox div[data-baseweb="select"] > div {
        font-size: 1.1em !important;
        line-height: 1.5 !important; /* Ensure consistent line height */
        padding-top: 0.5em !important; /* Add consistent padding */
        padding-bottom: 0.5em !important; /* Add consistent padding */
        color: black !important; /* Ensure text is visible */
        height: auto !important; /* Allow height to adjust to content */
        overflow: visible !important; /* Ensure content is not hidden */
    }

    /* Target the options in the opened dropdown list */
    .stSelectbox div[role="listbox"] div[data-baseweb="select"] ul li {
        font-size: 1.1em !important;
        line-height: 1.5 !important; /* Ensure consistent line height */
        padding-top: 0.5em !important; /* Add consistent padding */
        padding-bottom: 0.5em !important; /* Add consistent padding */
        color: black !important; /* Ensure text is visible */
        height: auto !important; /* Allow height to adjust to content */
        overflow: visible !important; /* Ensure content is not hidden */
    }

    /* Target the span element within the list item (where the text actually resides) */
    .stSelectbox div[role="listbox"] div[data-baseweb="select"] ul li span {
        line-height: 1.5 !important; /* Crucial for descenders */
        color: black !important; /* Ensure text is visible */
        overflow: visible !important;
        height: auto !important; /* Allow height to adjust to content */
    }

    /* Additional targeting for the actual text content within the selectbox options (more specific BaseWeb classes) */
    .stSelectbox .css-1dbjc4n.e1tzin5v0 > div > div > div,
    .stSelectbox .css-1dbjc4n.e1tzin5v0 > div > div > div > span {
        line-height: 1.5 !important;
        overflow: visible !important;
        height: auto !important;
        color: black !important;
    }
    </style>
""", unsafe_allow_html=True)


# Define backend URL (for local development)
BACKEND_URL = "http://localhost:8000"

# --- Helper Functions ---
def display_alert_card(alert_data):
    """Displays a single alert with icons and plain language."""
    drugs_capitalized = [drug.title() for drug in alert_data.get("drugs_involved", [])]
    drugs = ", ".join(drugs_capitalized)
    message = alert_data.get("alert_message", "No specific information.")
    icon_char = "🚨"

    st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h4>{icon_char} Alert: {drugs}</h4>
            <p>{message}</p>
        </div>
    """, unsafe_allow_html=True)

# --- Load Drug Data from Local JSON Files ---
@st.cache_data # Cache the data to avoid re-loading from file on every rerun
def get_drug_dictionary():
    """
    Loads comprehensive drug dictionary from local JSON files.
    This includes generic names for spell-checking and brand disambiguation data.
    """
    current_dir = os.path.dirname(__file__)
    data_dir = os.path.join(current_dir, 'data') # Removed trailing slash

    known_names_path = os.path.join(data_dir, 'known_names.json')
    brand_disambiguation_path = os.path.join(data_dir, 'brand_disambiguation.json')

    try:
        with open(known_names_path, 'r', encoding='utf-8') as f:
            known_names = json.load(f)
        
        with open(brand_disambiguation_path, 'r', encoding='utf-8') as f:
            brand_disambiguation = json.load(f)

        return {
            "known_names_for_spellcheck": known_names,
            "brand_disambiguation": brand_disambiguation
        }
    except FileNotFoundError as e:
        st.error(f"Error loading drug data files: {e}. Make sure 'known_names.json' and 'brand_disambiguation.json' are in the 'data/' directory.")
        return {
            "known_names_for_spellcheck": [],
            "brand_disambiguation": {}
        }
    except json.JSONDecodeError as e:
        st.error(f"Error parsing drug data JSON files: {e}. Check file format.")
        return {
            "known_names_for_spellcheck": [],
            "brand_disambiguation": {}
        }
    except Exception as e:
        st.error(f"An unexpected error occurred while loading drug data: {e}")
        return {
            "known_names_for_spellcheck": [],
            "brand_disambiguation": {}
        }


DRUG_DICTIONARY = get_drug_dictionary()
ALL_KNOWN_NAMES_FOR_SPELLCHECK = DRUG_DICTIONARY["known_names_for_spellcheck"]
# OPTIMIZATION: Convert to a set for O(1) average-case lookups
ALL_KNOWN_NAMES_FOR_SPELLCHECK_LOWER_SET = {name.lower() for name in ALL_KNOWN_NAMES_FOR_SPELLCHECK} 
BRAND_DISAMBIGUATION_MAP = DRUG_DICTIONARY["brand_disambiguation"]


# --- Global Session State Initializations ---
# These must be initialized at the top level to ensure they always exist
# before any widget tries to access them, preventing AttributeError.
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'medications' not in st.session_state:
    # Initialize with a default empty entry if no medications are loaded
    st.session_state.medications = [{"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"}]
if 'unrecognized_meds_to_correct' not in st.session_state:
    st.session_state.unrecognized_meds_to_correct = []
if 'meds_to_disambiguate' not in st.session_state: # New state for disambiguation
    st.session_state.meds_to_disambiguate = []
if 'show_spell_check_section' not in st.session_state:
    st.session_state.show_spell_check_section = False
if 'show_disambiguation_section' not in st.session_state: # New state for disambiguation UI
    st.session_state.show_disambiguation_section = False
if 'current_analysis_state' not in st.session_state: # New state variable for controlling flow
    st.session_state.current_analysis_state = "initial"
if 'login_error_message' not in st.session_state: # To store login errors
    st.session_state.login_error_message = ""
if 'login_success_message' not in st.session_state: # New: To store login success messages
    st.session_state.login_success_message = ""
if 'user_id' not in st.session_state: # Store user_id after login
    st.session_state.user_id = None

# --- Flags to trigger reruns outside of callbacks ---
if 'login_redirect_needed' not in st.session_state:
    st.session_state.login_redirect_needed = False
if 'analysis_rerun_needed' not in st.session_state:
    st.session_state.analysis_rerun_needed = False
if 'logout_redirect_needed' not in st.session_state:
    st.session_state.logout_redirect_needed = False


# --- Login Page ---
def login_page():
    st.title("Welcome to RxRadar 📡")
    st.subheader("Your Smart Medication Management Assistant")

    st.markdown("""
        <div style="background-color: #e0f7fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3>About</h3>
            <p><strong>App Purpose:</strong> RxRadar helps you safely manage your medications by flagging potential issues like drug interactions, duplicates, and missing information. Our goal is to empower you with clear, plain-language insights for better health discussions with your doctor. RxRadar does not provide medical advice. Consult with your healthcare professional for all medication decisions.</p>
            <p><strong>Disclaimer:</strong> This is an MVP version of RxRadar meant for demo purposes only. It is still in Beta and is not fully released with proper securities and encryptions. As such, please <strong>do not input any identifiable/sensitive personal or medical information</strong>. </p>
            <p><strong>Disclaimer Again:</strong><strong> DO NOT PUT ANY IDENTIFIABLE/SENSITIVE PERSONAL OR MEDICAL INFORMATION INTO RXRADAR AT THIS TIME!</strong></p> 
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("Login / Create Account")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    # Consent Checkbox and Information
    consent_given = st.checkbox("✅ I agree to the **Data Privacy and Consent Policy**", key="data_consent_checkbox")

    # Login Function
    def do_login():
        st.session_state.login_error_message = "" # Clear previous error at the start of function
        st.session_state.login_success_message = "" # Clear previous success message
        if not st.session_state.login_username or not st.session_state.login_password:
            st.session_state.login_error_message = "Please enter both username and password."
            return
        if not st.session_state.data_consent_checkbox:
            st.session_state.login_error_message = "Please agree to the Data Privacy and Consent Policy to proceed."
            return

        try:
            response = requests.post(
                f"{BACKEND_URL}/login",
                json={"username": st.session_state.login_username, "password": st.session_state.login_password}
            )
            if response.status_code == 200:
                response_data = response.json()
                st.session_state['logged_in'] = True
                st.session_state['username'] = response_data.get("username")
                st.session_state['user_id'] = response_data.get("user_id") # Store user_id

                # --- Load medications for the logged-in user from the response ---
                loaded_meds_data = response_data.get("medications", [])
                if loaded_meds_data:
                    # Convert loaded data to match session state structure (status: resolved)
                    # Ensure all required keys are present for consistency
                    st.session_state.medications = [
                        {
                            "name": med.get("name", ""),
                            "dosage": med.get("dosage", ""),
                            "frequency": med.get("frequency", ""),
                            "active_ingredients": med.get("active_ingredients", []),
                            "status": "resolved" # Mark as resolved if loaded from persistence
                        } for med in loaded_meds_data
                    ]
                    st.success(f"Welcome back, {st.session_state.username}! Your saved medications have been loaded.")
                else:
                    st.session_state.medications = [{"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"}]
                    st.info(f"Welcome, {st.session_state.username}! No saved medications found. Start by adding new ones.")
                
                st.session_state.login_redirect_needed = True # Set flag to trigger rerun outside callback
            else:
                st.session_state.login_error_message = f"Login failed: {response.json().get('detail', 'Invalid username or password')}"
        except requests.exceptions.ConnectionError:
            st.session_state.login_error_message = "Could not connect to the backend. Please ensure the FastAPI service is running."
        except Exception as e:
            st.session_state.login_error_message = f"An unexpected error occurred during login: {e}"

    # Register Function
    def do_register():
        st.session_state.login_error_message = "" # Clear previous error at the start of function
        st.session_state.login_success_message = "" # Clear previous success message
        if not st.session_state.login_username or not st.session_state.login_password:
            st.session_state.login_error_message = "Please enter both username and password."
            return
        if not st.session_state.data_consent_checkbox:
            st.session_state.login_error_message = "Please agree to the Data Privacy and Consent Policy to proceed."
            return

        try:
            response = requests.post(
                f"{BACKEND_URL}/users/register",
                json={"username": st.session_state.login_username, "password": st.session_state.login_password}
            )
            if response.status_code == 200:
                st.session_state.login_success_message = "Account created successfully! Please log in."
            else:
                st.session_state.login_error_message = f"Registration failed: {response.json().get('detail', 'Username might already exist or other error')}"
        except requests.exceptions.ConnectionError:
            st.session_state.login_error_message = "Could not connect to the backend. Please ensure the FastAPI service is running."
        except Exception as e:
            st.session_state.login_error_message = f"An unexpected error occurred during registration: {e}"

    col1, col2 = st.columns(2)
    with col1:
        st.button("Login", key="login_btn", type="primary", on_click=do_login)
    with col2:
        st.button("Create Account", key="register_btn", on_click=do_register)

    # Display error message at the bottom of the login section
    if st.session_state.login_error_message:
        st.error(st.session_state.login_error_message)
    # Display success message at the bottom of the login section
    if st.session_state.login_success_message:
        st.success(st.session_state.login_success_message)
    
    # --- RERUN LOGIC FOR LOGIN PAGE (OUTSIDE CALLBACKS) ---
    if st.session_state.login_redirect_needed:
        st.session_state.login_redirect_needed = False # Reset flag immediately
        st.rerun(scope="app") # This rerun is now outside the callback, no warning


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

    # Initialize medication list if not already present or empty
    if 'medications' not in st.session_state or not st.session_state.medications:
        st.session_state.medications = [{"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"}]
    
    # Function to add a new medication input row
    def add_medication_row():
        st.session_state.medications.append({"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"})
        # Reset all flags that control conditional sections when adding a new row
        st.session_state.unrecognized_meds_to_correct = []
        st.session_state.meds_to_disambiguate = []
        st.session_state.show_spell_check_section = False
        st.session_state.show_disambiguation_section = False
        st.session_state.current_analysis_state = "initial" # Reset state to initial


    # Function to delete a medication row
    def delete_medication_row(index_to_delete):
        if len(st.session_state.medications) > 1: # Ensure at least one row remains
            st.session_state.medications.pop(index_to_delete)
            # Reset analysis state as deleting a medication might change pending issues
            st.session_state.unrecognized_meds_to_correct = []
            st.session_state.meds_to_disambiguate = []
            st.session_state.current_analysis_state = "initial"
            st.session_state.analysis_rerun_needed = True # Trigger rerun outside callback
        else:
            st.warning("You must have at least one medication row.")


    # Display dynamic medication input fields
    for i, med in enumerate(st.session_state.medications):
        st.subheader(f"Medication {i+1}")
        # Use columns to align the text input and the delete button
        cols = st.columns([0.4, 0.3, 0.2, 0.1]) # Adjust column widths as needed
        
        with cols[0]:
            # Display current name, which might be the original input or a corrected/disambiguated one
            st.session_state.medications[i]['name'] = st.text_input(
                "Name (e.g., Metformin, Advil, Zyrtec)",
                value=st.session_state.medications[i]['name'],
                key=f"med_name_input_{i}"
            )

        with cols[1]:
            st.session_state.medications[i]['dosage'] = st.text_input(
                "Dosage (e.g., 2.5mg, 5mg, 10mg)",
                value=st.session_state.medications[i]['dosage'],
                key=f"med_dosage_{i}"
            )
        with cols[2]:
            st.session_state.medications[i]['frequency'] = st.text_input(
                "Frequency (e.g., daily, twice a day, weekly)",
                value=st.session_state.medications[i]['frequency'],
                key=f"med_frequency_{i}"
            )
        
        with cols[3]:
            # Add a delete button for each row, only if there's more than one row
            if len(st.session_state.medications) > 1:
                st.markdown("<div style='height: 2.8em;'></div>", unsafe_allow_html=True) # Spacer for alignment
                st.button(
                    "X",
                    key=f"delete_med_{i}",
                    on_click=delete_medication_row,
                    args=(i,), # Pass the index of the current medication to the callback
                    help="Delete this medication row"
                )

    st.button("Add Another Medication", on_click=add_medication_row)

    # Filter out empty medication entries for analysis
    all_entered_meds = [
        med for med in st.session_state.medications
        if med['name'].strip() and med['dosage'].strip() and med['frequency'].strip()
    ]

    st.markdown("---") 

    # --- Section 2: Analyze Medications (includes conditional sections) ---
    st.header("2. Analyze Medications")
    st.write("Click 'Analyze Medications' to check your current list for potential issues.")
    analyze_button_clicked = st.button("Analyze Medications", key="analyze_button_main", type="primary")

    # Define the function for performing analysis and displaying alerts
    def perform_analysis_and_display_alerts(meds_list_for_analysis):
        # Prepare data for FastAPI: only send name and active_ingredients
        meds_to_send = [
            {
                "name": med['name'],
                "dosage": med['dosage'],
                "frequency": med['frequency'],
                "active_ingredients": med['active_ingredients']
            }
            for med in meds_list_for_analysis
        ]
        
        st.info("Sending medications to backend for analysis...")
        try:
            response = requests.post(
                f"{BACKEND_URL}/analyze_medications",
                json={"medications": meds_to_send}
            )
            if response.status_code == 200:
                backend_response = response.json()
                alerts_from_backend = backend_response.get("alerts", [])
                
                if alerts_from_backend:
                    st.success("Analysis Complete! Review alerts below.")
                    for alert in alerts_from_backend:
                        display_alert_card(alert)
                else:
                    st.info("No significant medication risks or interactions detected for this patient based on backend analysis.")
            else:
                st.error(f"Backend analysis failed: {response.json().get('detail', 'Unknown error')}")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the backend. Please ensure the FastAPI service is running.")
        except Exception as e:
            st.error(f"An unexpected error occurred during analysis: {e}")


    # --- State Transition Logic ---
    # This block determines the next state of the analysis flow
    if analyze_button_clicked or st.session_state.current_analysis_state in ["disambiguating", "spell_checking"]:
        # If the button was clicked, or we are returning from a disambiguation/spell-check step
        if analyze_button_clicked: # Only reset if the button was explicitly clicked
            st.session_state.current_analysis_state = "checking_inputs"
            # Clear previous issues found
            st.session_state.unrecognized_meds_to_correct = []
            st.session_state.meds_to_disambiguate = []
            # Reset medication statuses for re-evaluation
            for med in st.session_state.medications:
                med['status'] = "pending"
                # Only clear active ingredients if they were not explicitly set by disambiguation/correction
                # Otherwise, preserve them for re-evaluation
                if not med['active_ingredients'] or med['status'] != "resolved":
                    med['active_ingredients'] = [] 

        if st.session_state.current_analysis_state == "checking_inputs":
            if not all_entered_meds:
                st.warning("Please enter at least one complete medication (name, dosage, frequency) to analyze.")
                st.session_state.current_analysis_state = "initial" # Go back to initial state
            else:
                needs_disambiguation = False
                needs_spell_check = False

                # Clear lists for this pass
                st.session_state.unrecognized_meds_to_correct = []
                st.session_state.meds_to_disambiguate = []

                for i, med_entry in enumerate(st.session_state.medications):
                    # Skip medications that are already resolved
                    if med_entry['status'] == "resolved":
                        continue

                    typed_name_raw = med_entry['name']
                    typed_name_lower = typed_name_raw.strip().lower()

                    if not typed_name_raw.strip(): # Skip empty entries
                        continue

                    # NEW CHECK: Direct match to a known disambiguated display name (e.g., "Tylenol (Acetaminophen)")
                    found_direct_disambiguated_match = False
                    for brand_key, options_list in BRAND_DISAMBIGUATION_MAP.items():
                        for option in options_list:
                            if typed_name_lower == option['display_name'].lower():
                                st.session_state.medications[i]['name'] = option['display_name']
                                st.session_state.medications[i]['active_ingredients'] = option['active_ingredients']
                                st.session_state.medications[i]['status'] = "resolved"
                                found_direct_disambiguated_match = True
                                break # Found a match, break inner loop
                        if found_direct_disambiguated_match:
                            break # Found a match, break outer loop
                    
                    if found_direct_disambiguated_match:
                        continue # IMPORTANT: If directly matched a disambiguated name, move to next medication.


                    # 1. Check for brand name disambiguation (exact match on brand name)
                    if typed_name_lower in BRAND_DISAMBIGUATION_MAP:
                        options = BRAND_DISAMBIGUATION_MAP[typed_name_lower]
                        if len(options) > 1: # Multiple options, needs disambiguation
                            st.session_state.meds_to_disambiguate.append({
                                'index': i,
                                'original_name': typed_name_raw, # Store original for the placeholder option
                                'options': options,
                                'selected_disambiguation': typed_name_raw # Default to original until user selects
                            })
                            st.session_state.medications[i]['status'] = "needs_disambiguation"
                            needs_disambiguation = True
                        elif len(options) == 1: # Single clear brand name, auto-disambiguate
                            st.session_state.medications[i]['active_ingredients'] = options[0]['active_ingredients']
                            st.session_state.medications[i]['name'] = options[0]['display_name'] # Update displayed name
                            st.session_state.medications[i]['status'] = "resolved"
                        continue # IMPORTANT: If handled by brand logic, move to next medication.

                    # 2. Check for direct generic match (after brand check, if not already handled)
                    # This now only runs if it wasn't an exact brand match.
                    # Use the optimized set for lookup
                    if typed_name_lower in ALL_KNOWN_NAMES_FOR_SPELLCHECK_LOWER_SET:
                        st.session_state.medications[i]['active_ingredients'] = [typed_name_raw]
                        st.session_state.medications[i]['status'] = "resolved"
                        continue # IMPORTANT: If handled by generic logic, move to next medication.

                    # 3. If still pending (not resolved by brand or generic), perform spell check
                    # This block now only executes if the medication hasn't been resolved by the above checks.
                    suggestions = difflib.get_close_matches(typed_name_lower, ALL_KNOWN_NAMES_FOR_SPELLCHECK, n=5, cutoff=0.6)
                    
                    # Always add to unrecognized_meds_to_correct if not resolved by direct match/disambiguation
                    # And set needs_spell_check to True to ensure the section is displayed.
                    if suggestions:
                        st.session_state.unrecognized_meds_to_correct.append({
                            'index': i,
                            'original_name': typed_name_raw,
                            'suggestions': suggestions, # Store raw suggestions for the selectbox
                            'selected_correction': typed_name_raw # Default to original until user selects
                        })
                    else: # Truly unknown, no suggestions
                        st.session_state.unrecognized_meds_to_correct.append({
                            'index': i,
                            'original_name': typed_name_raw,
                            'suggestions': ["Unrecognized medication spelling. Please check and retype this medication."],
                            'selected_correction': typed_name_raw # Default to original
                        })
                    st.session_state.medications[i]['status'] = "needs_spell_check" # Mark as needing spell check
                    needs_spell_check = True


                # Determine next state based on what was found in this pass
                # Prioritize disambiguation over spell-checking
                if needs_disambiguation:
                    st.session_state.current_analysis_state = "disambiguating"
                elif needs_spell_check:
                    st.session_state.current_analysis_state = "spell_checking"
                else:
                    # If all medications that were *actually entered* are resolved
                    resolved_count = 0
                    total_valid_entered = 0
                    for med in st.session_state.medications:
                        if med['name'].strip() and med['dosage'].strip() and med['frequency'].strip():
                            total_valid_entered += 1
                            if med['status'] == "resolved":
                                resolved_count += 1
                    
                    if total_valid_entered > 0 and resolved_count == total_valid_entered:
                        st.session_state.current_analysis_state = "displaying_results" # All clear, ready for final display
                    elif total_valid_entered == 0:
                        st.session_state.current_analysis_state = "initial" # No valid meds, go back to initial
                    else:
                        # This else means there are still pending meds but no new issues found in this pass.
                        # This indicates a logical flaw or anhandled status.
                        st.session_state.current_analysis_state = "initial" # Fallback to initial if not fully resolved


    # --- Display Disambiguation Section (Conditional) ---
    if st.session_state.current_analysis_state == "disambiguating":
        st.markdown("---")
        st.subheader("Medication Clarification (Active Ingredients)")
        st.error("Some brand names have multiple versions. Please select the correct formulation/active ingredient(s) for the following:")

        def update_single_disambiguation_in_state(disambiguation_entry_idx):
            # This callback only updates the 'selected_disambiguation' for the specific entry
            # It does NOT trigger a rerun or change the analysis state.
            st.session_state.meds_to_disambiguate[disambiguation_entry_idx]['selected_disambiguation'] = \
                st.session_state[f"disambiguation_select_{disambiguation_entry_idx}"]

        for disambiguation_entry_idx, entry in enumerate(st.session_state.meds_to_disambiguate):
            med_index = entry['index']
            original_input_name = entry['original_name']
            
            # Options for the selectbox: original input + specific formulations
            options = [original_input_name] + [opt['display_name'] for opt in entry['options']]
            
            # Determine default index based on current 'selected_disambiguation'
            current_selected = entry.get('selected_disambiguation', original_input_name)
            try:
                default_index = options.index(current_selected)
            except ValueError:
                default_index = 0 # Fallback if current_selected isn't in options

            st.write(f"**Clarify Medication {med_index + 1}:** `{original_input_name}`")
            
            st.selectbox(
                f"Select the correct formulation for '{original_input_name}':",
                options=options,
                index=default_index,
                key=f"disambiguation_select_{disambiguation_entry_idx}", # Use disambiguation_entry_idx for unique key
                on_change=update_single_disambiguation_in_state,
                args=(disambiguation_entry_idx,) # Pass the index to the callback
            )
            st.markdown("---") 

        # Add a confirm button for disambiguation
        def confirm_disambiguations():
            for entry in st.session_state.meds_to_disambiguate:
                med_idx = entry['index']
                selected_name_display = entry['selected_disambiguation']
                original_input_name = entry['original_name']

                if selected_name_display != original_input_name:
                    # Find the full option data (display_name and active_ingredients)
                    selected_full_option = next((opt for opt in entry['options'] if opt['display_name'] == selected_name_display), None)
                    if selected_full_option:
                        st.session_state.medications[med_idx]['name'] = selected_full_option['display_name']
                        st.session_state.medications[med_idx]['active_ingredients'] = selected_full_option['active_ingredients']
                        st.session_state.medications[med_idx]['status'] = "resolved"
                    else:
                        # Should not happen if options are correctly populated, but fallback
                        st.session_state.medications[med_idx]['status'] = "pending"
                        st.session_state.medications[med_idx]['active_ingredients'] = []
                else:
                    # User re-selected the original name (placeholder), so it's still pending disambiguation
                    st.session_state.medications[med_idx]['status'] = "pending"
                    st.session_state.medications[med_idx]['active_ingredients'] = []
            
            st.session_state.meds_to_disambiguate = [] # Clear the list after confirming
            st.session_state.current_analysis_state = "checking_inputs" # Go back to re-check all meds
            st.session_state.analysis_rerun_needed = True # Set flag to trigger rerun outside callback

        st.button("Confirm Active Ingredient(s)", on_click=confirm_disambiguations, type="primary")


    # --- Display Spell Check Section (Conditional) ---
    if st.session_state.current_analysis_state == "spell_checking":
        st.markdown("---")
        st.subheader("Medication(s) Need Review (Check Spelling)")
        st.error("Please correct the following medication name(s) before analysis can proceed.")

        def update_single_correction_in_state(unrecognized_entry_idx):
            # This callback only updates the 'selected_correction' for the specific entry
            # It does NOT trigger a rerun or change the analysis state.
            st.session_state.unrecognized_meds_to_correct[unrecognized_entry_idx]['selected_correction'] = \
                st.session_state[f"correction_select_{unrecognized_entry_idx}"]

        # Display selectboxes for each unrecognized medication
        for unrecognized_entry_idx, entry in enumerate(st.session_state.unrecognized_meds_to_correct):
            med_index = entry['index']
            original_input_name = entry['original_name']
            
            # Options for the selectbox: original input + suggestions.
            # If "Unrecognized medication spelling..." is the only suggestion, it means no actual suggestions were found.
            if entry['suggestions'] == ["Unrecognized medication spelling. Please check and retype this medication."]:
                options = entry['suggestions'] # Only the custom message
            else:
                options = [original_input_name] + sorted(entry['suggestions']) # Add original and sorted suggestions

            # Determine default index based on current 'selected_correction'
            current_selected = entry.get('selected_correction', original_input_name)
            try:
                default_index = options.index(current_selected)
            except ValueError:
                default_index = 0 # Fallback if current_selected isn't in options

            st.write(f"**Original Input for Medication {med_index + 1}:** `{original_input_name}`")
            
            st.selectbox(
                f"Select correction for '{original_input_name}':",
                options=options,
                index=default_index,
                key=f"correction_select_{unrecognized_entry_idx}", # Use unrecognized_entry_idx for unique key
                on_change=update_single_correction_in_state,
                args=(unrecognized_entry_idx,) # Pass the index to the callback
            )
            st.markdown("---") 
        
        
        def confirm_spell_checks():
            for entry in st.session_state.unrecognized_meds_to_correct:
                med_idx = entry['index']
                selected_name = entry['selected_correction']
                typed_name_lower = selected_name.strip().lower()

                # If the user selected the "Unrecognized..." message, keep the original input
                if selected_name == "Unrecognized medication spelling. Please check and retype this medication.":
                    st.session_state.medications[med_idx]['name'] = entry['original_name'] # Keep original input
                    st.session_state.medications[med_idx]['active_ingredients'] = [] # Clear active ingredients
                    st.session_state.medications[med_idx]['status'] = "pending" # Keep status as pending to re-prompt
                    continue # Move to the next entry

                st.session_state.medications[med_idx]['name'] = selected_name
                st.session_state.medications[med_idx]['active_ingredients'] = [] # Reset for re-determination
                st.session_state.medications[med_idx]['status'] = "pending" # Start as pending for re-evaluation

                resolved_this_med = False

                # 1. Check for direct match to a known disambiguated display name (e.g., "Tylenol (Acetaminophen)")
                for brand_key, options_list in BRAND_DISAMBIGUATION_MAP.items():
                    for option in options_list:
                        if typed_name_lower == option['display_name'].lower():
                            st.session_state.medications[med_idx]['name'] = option['display_name'] # Update to canonical display name
                            st.session_state.medications[med_idx]['active_ingredients'] = option['active_ingredients']
                            st.session_state.medications[med_idx]['status'] = "resolved"
                            resolved_this_med = True
                            break
                    if resolved_this_med:
                        break

                if resolved_this_med:
                    continue # Move to next medication in the loop

                # 2. Check for brand name disambiguation (exact match on brand name)
                if typed_name_lower in BRAND_DISAMBIGUATION_MAP:
                    options = BRAND_DISAMBIGUATION_MAP[typed_name_lower]
                    if len(options) > 1: # Multiple options, needs disambiguation
                        # This will cause a re-run to the disambiguation section.
                        st.session_state.meds_to_disambiguate.append({
                            'index': med_idx,
                            'original_name': selected_name,
                            'options': options,
                            'selected_disambiguation': selected_name
                        })
                        st.session_state.medications[med_idx]['status'] = "needs_disambiguation"
                    elif len(options) == 1: # Single clear brand name, auto-disambiguate
                        st.session_state.medications[med_idx]['active_ingredients'] = options[0]['active_ingredients']
                        st.session_state.medications[med_idx]['name'] = options[0]['display_name'] # Update displayed name
                        st.session_state.medications[med_idx]['status'] = "resolved"
                        resolved_this_med = True
                
                if resolved_this_med:
                    continue # Move to next medication in the loop

                # 3. Check for direct generic match (after brand check, if not already handled)
                if typed_name_lower in ALL_KNOWN_NAMES_FOR_SPELLCHECK_LOWER_SET:
                    st.session_state.medications[med_idx]['active_ingredients'] = [selected_name]
                    st.session_state.medications[med_idx]['status'] = "resolved"
                    resolved_this_med = True
                
                if resolved_this_med:
                    continue # Move to next medication in the loop

                # If still not resolved after all checks (should only happen if selected_name is truly unknown)
                if not resolved_this_med:
                    st.session_state.medications[med_idx]['active_ingredients'] = ["UNKNOWN"]
                    st.session_state.medications[med_idx]['status'] = "pending" # Keep as pending for re-evaluation

            st.session_state.unrecognized_meds_to_correct = [] # Clear the list after confirming

            # Determine the next state based on whether new disambiguations were triggered
            if st.session_state.meds_to_disambiguate:
                st.session_state.current_analysis_state = "disambiguating"
            else:
                st.session_state.current_analysis_state = "checking_inputs" # Go back to re-check all meds (should now be resolved)
            st.session_state.analysis_rerun_needed = True # Set flag to trigger rerun outside callback

        st.button("Confirm Medication Name(s)", on_click=confirm_spell_checks, type="primary")


    # --- Display Analysis Results (Conditional) ---
    if st.session_state.current_analysis_state == "displaying_results":
        st.markdown("---") # Add a separator before results
        st.subheader("Potential Concerns & Alerts") # Moved subheader here
        perform_analysis_and_display_alerts(all_entered_meds)
    elif st.session_state.current_analysis_state == "initial":
        st.info("Click 'Analyze Medications' to begin. Alerts will appear here.")


    # --- Logout Button ---
    st.markdown("---")
    if st.button("Logout", key="logout_btn"):
        # Prepare medication data for saving
        # Only include the fields that the backend's MedicationData Pydantic model expects
        meds_to_save = [
            {
                "name": med['name'],
                "dosage": med['dosage'],
                "frequency": med['frequency'],
                "active_ingredients": med['active_ingredients']
            }
            for med in st.session_state.medications if med['name'].strip() # Only save non-empty entries
        ]

        # Send medications to backend to save
        try:
            save_response = requests.post(
                f"{BACKEND_URL}/save_medications",
                json={
                    "username": st.session_state.get('username'),
                    "medications": meds_to_save
                }
            )
            if save_response.status_code == 200:
                st.success("Medications saved successfully! Logging out...")
            else:
                st.warning(f"Failed to save medications: {save_response.json().get('detail', 'Unknown error')}")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to backend to save medications. Data might not be persisted.")
        except Exception as e:
            st.error(f"An unexpected error occurred during saving medications: {e}")
        
        # Clear session state and trigger logout redirect
        st.session_state['logged_in'] = False
        st.session_state.pop('username', None)
        st.session_state.pop('user_id', None) # Clear user_id
        st.session_state.pop('medications', None) # Clear meds on logout
        st.session_state.logout_redirect_needed = True # Set flag to trigger rerun outside callback

    # --- RERUN LOGIC FOR MAIN APP PAGE (OUTSIDE CALLBACKS) ---
    if st.session_state.analysis_rerun_needed:
        st.session_state.analysis_rerun_needed = False # Reset flag immediately
        st.rerun(scope="app") # This rerun is now outside the callback, no warning
    
    if st.session_state.logout_redirect_needed:
        st.session_state.logout_redirect_needed = False # Reset flag immediately
        st.rerun(scope="app") # This rerun is now outside the callback, no warning


# --- Main App Logic ---
# This top-level logic controls which page is displayed
if st.session_state.login_redirect_needed:
    st.session_state.login_redirect_needed = False # Ensure flag is reset before rerunning
    st.rerun(scope="app") # This will trigger the main_app_page() to run next

elif st.session_state.logout_redirect_needed:
    st.session_state.logout_redirect_needed = False # Ensure flag is reset before rerunning
    st.rerun(scope="app") # This will trigger the login_page() to run next

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
