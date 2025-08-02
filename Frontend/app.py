import streamlit as st
import requests
import json 
import difflib 
import os


st.set_page_config(
    page_title="RxRadar: Smart Medication Management",
    page_icon="💊",
    layout="wide", 
    initial_sidebar_state="collapsed" 
)


st.markdown("""
    <style>
        body {
            background-color: #fff !important;
            color: #222 !important;
        }
        [data-testid="stAppViewContainer"] {
            background-color: #fff !important;
            color: #222 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f9f9f9 !important;
        }
    </style>
""", unsafe_allow_html=True)


st.markdown("""
    <meta name="color-scheme" content="light only">
""", unsafe_allow_html=True)

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
    .stButton > button {
        font-size: 1.1em !important;
    }

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

    .stSelectbox div[role="listbox"] div[data-baseweb="select"] ul li span {
        line-height: 1.5 !important; /* Crucial for descenders */
        color: black !important; /* Ensure text is visible */
        overflow: visible !important;
        height: auto !important; /* Allow height to adjust to content */
    }

    .stSelectbox .css-1dbjc4n.e1tzin5v0 > div > div > div,
    .stSelectbox .css-1dbjc4n.e1tzin5v0 > div > div > div > span {
        line-height: 1.5 !important;
        overflow: visible !important;
        height: auto !important;
        color: black !important;
    }
    </style>
""", unsafe_allow_html=True)


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


@st.cache_data
def get_drug_dictionary():
    """
    Loads comprehensive drug dictionary from local JSON files.
    This includes generic names for spell-checking and brand disambiguation data.
    """
    current_dir = os.path.dirname(__file__)
    data_dir = os.path.join(current_dir, 'data') 

    known_names_path = os.path.join(data_dir, 'known_names.json')
    brand_disambiguation_path = os.path.join(data_dir, 'brand_disambiguation.json')
    

    try:
        with open(known_names_path, 'r', encoding='utf-8') as f:
            known_names = json.load(f)
        
        with open(brand_disambiguation_path, 'r', encoding='utf-8') as f:
            brand_disambiguation = json.load(f)
        brand_disambiguation = {k.lower(): v for k, v in brand_disambiguation.items()}

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

ALL_KNOWN_NAMES_FOR_SPELLCHECK_LOWER_SET = {name.lower() for name in ALL_KNOWN_NAMES_FOR_SPELLCHECK} 
BRAND_DISAMBIGUATION_MAP = DRUG_DICTIONARY["brand_disambiguation"]


if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'medications' not in st.session_state:
    st.session_state.medications = [{"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"}]
if 'unrecognized_meds_to_correct' not in st.session_state:
    st.session_state.unrecognized_meds_to_correct = []
if 'meds_to_disambiguate' not in st.session_state:
    st.session_state.meds_to_disambiguate = []
if 'show_spell_check_section' not in st.session_state:
    st.session_state.show_spell_check_section = False
if 'show_disambiguation_section' not in st.session_state: 
    st.session_state.show_disambiguation_section = False
if 'current_analysis_state' not in st.session_state: 
    st.session_state.current_analysis_state = "initial"
if 'login_error_message' not in st.session_state: 
    st.session_state.login_error_message = ""
if 'login_success_message' not in st.session_state: 
    st.session_state.login_success_message = ""
if 'user_id' not in st.session_state: 
    st.session_state.user_id = None

if 'login_redirect_needed' not in st.session_state:
    st.session_state.login_redirect_needed = False
if 'analysis_rerun_needed' not in st.session_state:
    st.session_state.analysis_rerun_needed = False
if 'logout_redirect_needed' not in st.session_state:
    st.session_state.logout_redirect_needed = False


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
    
    def do_login():
        st.session_state.login_error_message = "" 
        st.session_state.login_success_message = "" 
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
                st.session_state['user_id'] = response_data.get("user_id")

               
                loaded_meds_data = response_data.get("medications", [])
                if loaded_meds_data:
                    
                    
                    st.session_state.medications = [
                        {
                            "name": med.get("name", ""),
                            "dosage": med.get("dosage", ""),
                            "frequency": med.get("frequency", ""),
                            "active_ingredients": med.get("active_ingredients", []),
                            "status": "resolved"
                        } for med in loaded_meds_data
                    ]
                    st.success(f"Welcome back, {st.session_state.username}! Your saved medications have been loaded.")
                else:
                    st.session_state.medications = [{"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"}]
                    st.info(f"Welcome, {st.session_state.username}! No saved medications found. Start by adding new ones.")
                
                st.session_state.login_redirect_needed = True
            else:
                st.session_state.login_error_message = ("Login failed: Account not found or invalid password. " 
                                                        "If you do not have an account, please click Sign Up to create one.")
        except requests.exceptions.ConnectionError:
            st.session_state.login_error_message = "Could not connect to the backend. Please ensure the FastAPI service is running."
        except Exception as e:
            st.session_state.login_error_message = (
                    "Login failed. Did you create an account? "
                    "If not, please click the 'Create Account' button above to register."
                )


    def do_register():
        st.session_state.login_error_message = ""
        st.session_state.login_success_message = "" 
        if not st.session_state.login_username or not st.session_state.login_password:
            st.session_state.login_error_message = "Please enter both username and password."
            return
        if not st.session_state.data_consent_checkbox:
            st.session_state.login_error_message = "Please agree to the Data Privacy and Consent Policy to proceed."
            return

        try:
            response = requests.post(
                f"{BACKEND_URL}/register",
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
        st.button("Log In", key="login_btn", type="primary", on_click=do_login)
    with col2:
        st.button("Sign Up", key="register_btn", on_click=do_register)


    if st.session_state.login_error_message:
        st.error(st.session_state.login_error_message)
   
    if st.session_state.login_success_message:
        st.success(st.session_state.login_success_message)
    
  
    if st.session_state.login_redirect_needed:
        st.session_state.login_redirect_needed = False 
        st.rerun(scope="app")


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



def main_app_page():
    st.title(f"RxRadar: Welcome, {st.session_state.get('username', 'User')}!")
    st.markdown("Your personalized shield against medication risks.")


    st.header("1. Your Current Medications")
    st.write("Enter your prescription and over-the-counter medications below.")

    if 'medications' not in st.session_state or not st.session_state.medications:
        st.session_state.medications = [{"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"}]
    
    def add_medication_row():
        st.session_state.medications.append({"name": "", "dosage": "", "frequency": "", "active_ingredients": [], "status": "pending"})
        st.session_state.unrecognized_meds_to_correct = []
        st.session_state.meds_to_disambiguate = []
        st.session_state.show_spell_check_section = False
        st.session_state.show_disambiguation_section = False
        st.session_state.current_analysis_state = "initial" 



    def delete_medication_row(index_to_delete):
        if len(st.session_state.medications) > 1: 
            st.session_state.medications.pop(index_to_delete)
            st.session_state.unrecognized_meds_to_correct = []
            st.session_state.meds_to_disambiguate = []
            st.session_state.current_analysis_state = "initial"
            st.session_state.analysis_rerun_needed = True 
        else:
            st.warning("You must have at least one medication row.")


    for i, med in enumerate(st.session_state.medications):
        st.subheader(f"Medication {i+1}")
       
        cols = st.columns([0.4, 0.3, 0.2, 0.1]) 
        
        with cols[0]:
            
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
            
            if len(st.session_state.medications) > 1:
                st.markdown("<div style='height: 2.8em;'></div>", unsafe_allow_html=True) 
                st.button(
                    "X",
                    key=f"delete_med_{i}",
                    on_click=delete_medication_row,
                    args=(i,), 
                    help="Delete this medication row"
                )

    st.button("Add Another Medication", on_click=add_medication_row)

    all_entered_meds = [
        med for med in st.session_state.medications
        if med['name'].strip() and med['dosage'].strip() and med['frequency'].strip()
    ]

    st.markdown("---") 

    st.header("2. Analyze Medications")
    st.write("Click 'Analyze Medications' to check your current list for potential issues.")
    analyze_button_clicked = st.button("Analyze Medications", key="analyze_button_main", type="primary")

    def perform_analysis_and_display_alerts(meds_list_for_analysis):
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



    if analyze_button_clicked or st.session_state.current_analysis_state in ["disambiguating", "spell_checking"]:
       
        if analyze_button_clicked:
            st.session_state.current_analysis_state = "checking_inputs"
           
            st.session_state.unrecognized_meds_to_correct = []
            st.session_state.meds_to_disambiguate = []
           
            for med in st.session_state.medications:
                med['status'] = "pending"
            
                if not med['active_ingredients'] or med['status'] != "resolved":
                    med['active_ingredients'] = [] 

        if st.session_state.current_analysis_state == "checking_inputs":
            if not all_entered_meds:
                st.warning("Please enter at least one complete medication (name, dosage, frequency) to analyze.")
                st.session_state.current_analysis_state = "initial" 
            else:
                needs_disambiguation = False
                needs_spell_check = False

                st.session_state.unrecognized_meds_to_correct = []
                st.session_state.meds_to_disambiguate = []

                for i, med_entry in enumerate(st.session_state.medications):
            
                    if med_entry['status'] == "resolved":
                        continue

                    typed_name_raw = med_entry['name']
                    typed_name_lower = typed_name_raw.strip().lower()

                    if not typed_name_raw.strip(): 
                        continue

                    found_direct_disambiguated_match = False
                    for brand_key, options_list in BRAND_DISAMBIGUATION_MAP.items():
                        for option in options_list:
                            if typed_name_lower == option['display_name'].lower():
                                st.session_state.medications[i]['name'] = option['display_name']
                                st.session_state.medications[i]['active_ingredients'] = option['active_ingredients']
                                st.session_state.medications[i]['status'] = "resolved"
                                found_direct_disambiguated_match = True
                                break 
                        if found_direct_disambiguated_match:
                            break 
                    
                    if found_direct_disambiguated_match:
                        continue 


                    if typed_name_lower in BRAND_DISAMBIGUATION_MAP:
                        options = BRAND_DISAMBIGUATION_MAP[typed_name_lower]
                        if len(options) > 1: 
                            st.session_state.meds_to_disambiguate.append({
                                'index': i,
                                'original_name': typed_name_raw, 
                                'options': options,
                                'selected_disambiguation': typed_name_raw
                            })
                            st.session_state.medications[i]['status'] = "needs_disambiguation"
                            needs_disambiguation = True
                        elif len(options) == 1: 
                            st.session_state.medications[i]['active_ingredients'] = options[0]['active_ingredients']
                            st.session_state.medications[i]['name'] = options[0]['display_name']
                            st.session_state.medications[i]['status'] = "resolved"
                        continue 

                   
                    if typed_name_lower in ALL_KNOWN_NAMES_FOR_SPELLCHECK_LOWER_SET:
                        st.session_state.medications[i]['active_ingredients'] = [typed_name_raw]
                        st.session_state.medications[i]['status'] = "resolved"
                        continue 
                  
                    suggestions = difflib.get_close_matches(typed_name_lower, ALL_KNOWN_NAMES_FOR_SPELLCHECK, n=5, cutoff=0.6)
                    
                    
                    if suggestions:
                        st.session_state.unrecognized_meds_to_correct.append({
                            'index': i,
                            'original_name': typed_name_raw,
                            'suggestions': suggestions, 
                            'selected_correction': typed_name_raw 
                        })
                    else: 
                        st.session_state.unrecognized_meds_to_correct.append({
                            'index': i,
                            'original_name': typed_name_raw,
                            'suggestions': ["Unrecognized medication spelling. Please check and retype this medication."],
                            'selected_correction': typed_name_raw
                        })
                    st.session_state.medications[i]['status'] = "needs_spell_check" 
                    needs_spell_check = True


                if needs_disambiguation:
                    st.session_state.current_analysis_state = "disambiguating"
                elif needs_spell_check:
                    st.session_state.current_analysis_state = "spell_checking"
                else:
                
                    resolved_count = 0
                    total_valid_entered = 0
                    for med in st.session_state.medications:
                        if med['name'].strip() and med['dosage'].strip() and med['frequency'].strip():
                            total_valid_entered += 1
                            if med['status'] == "resolved":
                                resolved_count += 1
                    
                    if total_valid_entered > 0 and resolved_count == total_valid_entered:
                        st.session_state.current_analysis_state = "displaying_results" 
                    elif total_valid_entered == 0:
                        st.session_state.current_analysis_state = "initial"
                    else:
                        
                        st.session_state.current_analysis_state = "initial" 


    if st.session_state.current_analysis_state == "disambiguating":
        st.markdown("---")
        st.subheader("Medication Clarification (Active Ingredients)")
        st.error("Some brand names have multiple versions. Please select the correct formulation/active ingredient(s) for the following:")

        def update_single_disambiguation_in_state(disambiguation_entry_idx):
          
            st.session_state.meds_to_disambiguate[disambiguation_entry_idx]['selected_disambiguation'] = \
                st.session_state[f"disambiguation_select_{disambiguation_entry_idx}"]

        for disambiguation_entry_idx, entry in enumerate(st.session_state.meds_to_disambiguate):
            med_index = entry['index']
            original_input_name = entry['original_name']
            
            options = [original_input_name] + [opt['display_name'] for opt in entry['options']]
            
            current_selected = entry.get('selected_disambiguation', original_input_name)
            try:
                default_index = options.index(current_selected)
            except ValueError:
                default_index = 0 

            st.write(f"**Clarify Medication {med_index + 1}:** `{original_input_name}`")
            
            st.selectbox(
                f"Select the correct formulation for '{original_input_name}':",
                options=options,
                index=default_index,
                key=f"disambiguation_select_{disambiguation_entry_idx}", 
                on_change=update_single_disambiguation_in_state,
                args=(disambiguation_entry_idx,) 
            )
            st.markdown("---") 

      
        def confirm_disambiguations():
            for entry in st.session_state.meds_to_disambiguate:
                med_idx = entry['index']
                selected_name_display = entry['selected_disambiguation']
                original_input_name = entry['original_name']

                if selected_name_display != original_input_name:
                   
                    selected_full_option = next((opt for opt in entry['options'] if opt['display_name'] == selected_name_display), None)
                    if selected_full_option:
                        st.session_state.medications[med_idx]['name'] = selected_full_option['display_name']
                        st.session_state.medications[med_idx]['active_ingredients'] = selected_full_option['active_ingredients']
                        st.session_state.medications[med_idx]['status'] = "resolved"
                    else:
                       
                        st.session_state.medications[med_idx]['status'] = "pending"
                        st.session_state.medications[med_idx]['active_ingredients'] = []
                else:
                    st.session_state.medications[med_idx]['status'] = "pending"
                    st.session_state.medications[med_idx]['active_ingredients'] = []
            
            st.session_state.meds_to_disambiguate = [] 
            st.session_state.current_analysis_state = "checking_inputs" 
            st.session_state.analysis_rerun_needed = True 

        st.button("Confirm Active Ingredient(s)", on_click=confirm_disambiguations, type="primary")


    if st.session_state.current_analysis_state == "spell_checking":
        st.markdown("---")
        st.subheader("Medication(s) Need Review (Check Spelling)")
        st.error("Please correct the following medication name(s) before analysis can proceed.")

        def update_single_correction_in_state(unrecognized_entry_idx):
            st.session_state.unrecognized_meds_to_correct[unrecognized_entry_idx]['selected_correction'] = \
                st.session_state[f"correction_select_{unrecognized_entry_idx}"]

        for unrecognized_entry_idx, entry in enumerate(st.session_state.unrecognized_meds_to_correct):
            med_index = entry['index']
            original_input_name = entry['original_name']
            
            if entry['suggestions'] == ["Unrecognized medication spelling. Please check and retype this medication."]:
                options = entry['suggestions'] 
            else:
                options = [original_input_name] + sorted(entry['suggestions']) 

            current_selected = entry.get('selected_correction', original_input_name)
            try:
                default_index = options.index(current_selected)
            except ValueError:
                default_index = 0 

            st.write(f"**Original Input for Medication {med_index + 1}:** `{original_input_name}`")
            
            st.selectbox(
                f"Select correction for '{original_input_name}':",
                options=options,
                index=default_index,
                key=f"correction_select_{unrecognized_entry_idx}", 
                on_change=update_single_correction_in_state,
                args=(unrecognized_entry_idx,) 
            )
            st.markdown("---") 
        
        
        def confirm_spell_checks():
            for entry in st.session_state.unrecognized_meds_to_correct:
                med_idx = entry['index']
                selected_name = entry['selected_correction']
                typed_name_lower = selected_name.strip().lower()

                if selected_name == "Unrecognized medication spelling. Please check and retype this medication.":
                    st.session_state.medications[med_idx]['name'] = entry['original_name'] 
                    st.session_state.medications[med_idx]['active_ingredients'] = [] 
                    st.session_state.medications[med_idx]['status'] = "pending"
                    continue 

                st.session_state.medications[med_idx]['name'] = selected_name
                st.session_state.medications[med_idx]['active_ingredients'] = [] 
                st.session_state.medications[med_idx]['status'] = "pending" 

                resolved_this_med = False

                for brand_key, options_list in BRAND_DISAMBIGUATION_MAP.items():
                    for option in options_list:
                        if typed_name_lower == option['display_name'].lower():
                            st.session_state.medications[med_idx]['name'] = option['display_name'] 
                            st.session_state.medications[med_idx]['active_ingredients'] = option['active_ingredients']
                            st.session_state.medications[med_idx]['status'] = "resolved"
                            resolved_this_med = True
                            break
                    if resolved_this_med:
                        break

                if resolved_this_med:
                    continue 


                if typed_name_lower in BRAND_DISAMBIGUATION_MAP:
                    options = BRAND_DISAMBIGUATION_MAP[typed_name_lower]
                    if len(options) > 1: 
                        
                        st.session_state.meds_to_disambiguate.append({
                            'index': med_idx,
                            'original_name': selected_name,
                            'options': options,
                            'selected_disambiguation': selected_name
                        })
                        st.session_state.medications[med_idx]['status'] = "needs_disambiguation"
                    elif len(options) == 1: 
                        st.session_state.medications[med_idx]['active_ingredients'] = options[0]['active_ingredients']
                        st.session_state.medications[med_idx]['name'] = options[0]['display_name'] 
                        st.session_state.medications[med_idx]['status'] = "resolved"
                        resolved_this_med = True
                
                if resolved_this_med:
                    continue 

                if typed_name_lower in ALL_KNOWN_NAMES_FOR_SPELLCHECK_LOWER_SET:
                    st.session_state.medications[med_idx]['active_ingredients'] = [selected_name]
                    st.session_state.medications[med_idx]['status'] = "resolved"
                    resolved_this_med = True
                
                if resolved_this_med:
                    continue 

                if not resolved_this_med:
                    st.session_state.medications[med_idx]['active_ingredients'] = ["UNKNOWN"]
                    st.session_state.medications[med_idx]['status'] = "pending" 

            st.session_state.unrecognized_meds_to_correct = [] 

            if st.session_state.meds_to_disambiguate:
                st.session_state.current_analysis_state = "disambiguating"
            else:
                st.session_state.current_analysis_state = "checking_inputs" 
            st.session_state.analysis_rerun_needed = True 

        st.button("Confirm Medication Name(s)", on_click=confirm_spell_checks, type="primary")


    if st.session_state.current_analysis_state == "displaying_results":
        st.markdown("---")
        st.subheader("Potential Concerns & Alerts") 
        perform_analysis_and_display_alerts(all_entered_meds)
    elif st.session_state.current_analysis_state == "initial":
        st.info("Click 'Analyze Medications' to begin. Alerts will appear here.")


    st.markdown("---")
    if st.button("Logout", key="logout_btn"):
       
        meds_to_save = [
            {
                "name": med['name'],
                "dosage": med['dosage'],
                "frequency": med['frequency'],
                "active_ingredients": med['active_ingredients']
            }
            for med in st.session_state.medications if med['name'].strip()
        ]

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
        
        st.session_state['logged_in'] = False
        st.session_state.pop('username', None)
        st.session_state.pop('user_id', None) 
        st.session_state.pop('medications', None) 
        st.session_state.logout_redirect_needed = True 

 
    if st.session_state.analysis_rerun_needed:
        st.session_state.analysis_rerun_needed = False 
        st.rerun(scope="app")
    
    if st.session_state.logout_redirect_needed:
        st.session_state.logout_redirect_needed = False
        st.rerun(scope="app")


if st.session_state.login_redirect_needed:
    st.session_state.login_redirect_needed = False 
    st.rerun(scope="app") 

elif st.session_state.logout_redirect_needed:
    st.session_state.logout_redirect_needed = False 
    st.rerun(scope="app") 

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
        Created By: 
       <a href="https://www.linkedin.com/in/kelsey-ryan/" target="_blank">Kelsey Ryan</a>,
        <a href="https://www.linkedin.com/in/pauline-emerald-ranjan/" target="_blank">Pauline Ranjan</a>,
        <a href="https://www.linkedin.com/in/k-chow/" target="_blank">Kevin Chow</a>,
        <a href="https://www.linkedin.com/in/bikram-khaira/" target="_blank">Bikram Khaira</a>
        <br>     
        <span style="font-style: italic;">Disclaimer: RxRadar does not provide medical advice. Consult a healthcare professional for all medication decisions.</span>
    </div>
""", unsafe_allow_html=True)
