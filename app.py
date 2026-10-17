import streamlit as st
import pandas as pd
import re
from datetime import datetime
from PIL import Image
import io
import json

try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False
import requests
from streamlit_lottie import st_lottie

def load_lottie_url(url: str):
    try:
        r = requests.get(url, timeout=3)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

lottie_scanning = load_lottie_url("https://assets5.lottiefiles.com/packages/lf20_v1yqrgec.json")
lottie_success = load_lottie_url("https://assets10.lottiefiles.com/packages/lf20_oxefatps.json")

# --- PAGE SETUP & REFINED PROFESSIONAL CSS ---
st.set_page_config(page_title="The Receipt Graveyard | Enterprise Audit OS", page_icon="■", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp {
        background-color: #080b11;
        background-image: radial-gradient(circle at 10% 10%, rgba(30, 41, 59, 0.4) 0%, transparent 40%),
                          radial-gradient(circle at 90% 90%, rgba(15, 23, 42, 0.5) 0%, transparent 40%);
        color: #f8fafc;
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: #f8fafc !important;
    }
    
    h1 { font-size: 2.4rem !important; margin-bottom: 0.5rem !important; }
    h2 { font-size: 1.8rem !important; }
    h3 { font-size: 1.25rem !important; }

    p, span, label, div {
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        color: #cbd5e1;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .feature-card {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .feature-card:hover {
        transform: translateY(-2px);
        border-color: rgba(37, 99, 235, 0.4);
    }

    div.stExpander, div[data-testid="stVerticalBlock"] > div.element-container {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
    }

    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 12px 16px;
        border-radius: 8px;
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
    }
    div[data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-weight: 800 !important;
        font-size: 1.4rem !important;
    }

    section[data-testid="stSidebar"] {
        background-color: rgba(8, 11, 17, 0.98);
        border-right: 1px solid rgba(255, 255, 255, 0.04);
        padding-top: 1rem;
    }

    .stButton > button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.02em;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1d4ed8, #1e40af);
        border-color: rgba(255, 255, 255, 0.25);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
    }

    input, select, textarea {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        color: #f8fafc !important;
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.6rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. SESSION MEMORY & OPTION C POLICY VERSIONING ---
if "ledger" not in st.session_state:
    st.session_state.ledger = []

if "policy_versions" not in st.session_state:
    st.session_state.policy_versions = [
        {
            "version": "v1.1",
            "effective_date": "2026-10-01",
            "updated_by": "System Default (CFO Office)",
            "timestamp": "2026-10-01 09:00:00",
            "reason": "Initial Q4 Corporate Expense Policy release",
            "document_text": "Standard Baseline Policy v1.1 loaded with default parameters.",
            "filing_window_days": 30,
            "big_ticket_threshold": 15000.0,
            "home_cap": 500.0,
            "tier1_cap": 25000.0,
            "tier2_cap": 1500.0,
            "mgr_threshold": 2000.0,
            "client_threshold": 1500.0,
            "max_tip_pct": 10.0,
            "travel_city_limit": 5000.0,
            "travel_category_cap": 25000.0,
            "client_meal_cap": 3500.0,
            "comm_tech_cap": 4000.0,
            "fuel_slab_cc": 1500,
            "meal_card_limit": 200.0,
            "meal_card_max_per_day": 2,
            "banned_categories": ["Alcohol", "Tobacco", "Mini-Bar", "Fines"]
        }
    ]

active_policy = st.session_state.policy_versions[-1]

FX_RATES = {
    "INR": 1.0,
    "USD": 84.50,
    "EUR": 91.20,
    "GBP": 109.40,
    "SGD": 63.20
}

# --- 2. ADVANCED OFFLINE OCR & DEEP MATH PARSER ---
def parse_receipt_from_image_bytes(image_bytes: bytes, filename: str, custom_override: dict = None) -> dict:
    if custom_override:
        return custom_override

    raw_text = ""
    lines = []
    if OCR_AVAILABLE and image_bytes:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            result, _ = ocr_engine(img)
            if result:
                lines = [line[1].strip() for line in result if line[1].strip()]
                raw_text = "\n".join(lines)
        except Exception:
            raw_text = ""

    text_upper = raw_text.upper()
    merchant_name = "Your Restaurant" if "YOUR RESTAURANT" in text_upper else "Uploaded Vendor"
    for l in lines[:4]:
        if len(l) > 3 and not any(k in l.upper() for k in ["RECEIPT", "INVOICE", "PAYMENT", "DATE", "GSTIN"]):
            merchant_name = l.title()
            break

    date_found = datetime.now().strftime("%Y-%m-%d")
    m_dmy = re.search(r"(\d{2})[/-](\d{2})[/-](20\d{2})", raw_text)
    if m_dmy:
        date_found = f"{m_dmy.group(3)}-{m_dmy.group(2)}-{m_dmy.group(1)}"

    def extract_amount_near(keywords, text_block):
        for kw in keywords:
            pattern = rf"{kw}[^\d\n]*?([\d,]+\.\d{{2}}|\d{{3,6}})"
            m = re.search(pattern, text_block, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    pass
        return 0.0

    subtotal = extract_amount_near(["SUBTOTAL", "SUB TOTAL", "BASE FARE"], raw_text)
    cgst = extract_amount_near(["CGST"], raw_text)
    sgst = extract_amount_near(["SGST"], raw_text)
    tax = cgst + sgst if (cgst + sgst) > 0 else extract_amount_near(["GST", "TAX", "TOLL"], raw_text)
    tip = extract_amount_near(["SERVICE CHARGE", "TIP", "WAITING"], raw_text)
    total_printed = extract_amount_near(["GRAND TOTAL", "TOTAL PAID", "AMOUNT PAID", "TOTAL AMOUNT", "TOTAL"], raw_text)

    all_floats = [float(x.replace(",", "")) for x in re.findall(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b", raw_text)]
    if subtotal == 0.0 and len(all_floats) >= 2:
        subtotal = all_floats[-4] if len(all_floats) >= 4 else all_floats[0]
    if total_printed == 0.0 and all_floats:
        total_printed = max(all_floats)
    if total_printed == 0.0 and subtotal > 0:
        total_printed = round(subtotal + tax, 2)

    alcohol_keywords = ["BEER", "WINE", "WHISKEY", "LIQUOR", "ALCOHOL", "COCKTAIL"]
    line_items = []
    detected_alcohol_amt = 0.0
    for l in lines:
        if any(ak in l.upper() for ak in alcohol_keywords):
            detected_alcohol_amt += 500.0
            line_items.append({"description": l, "amount": 500.0, "category": "Alcohol"})

    if not line_items:
        line_items.append({"description": "General Expense Items", "amount": total_printed, "category": "General"})

    return {
        "merchant_name": merchant_name,
        "transaction_date": date_found,
        "currency": "INR",
        "fx_rate_to_inr": 1.0,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "tip": round(tip, 2),
        "total_printed": round(total_printed, 2),
        "is_itemized": True,
        "handwritten_tampering": False,
        "line_items": line_items,
        "detected_alcohol": detected_alcohol_amt
    }


def parse_policy_document_text(doc_text: str, current_policy: dict) -> dict:
    new_pol = dict(current_policy)
    new_pol["document_text"] = doc_text
    match_window = re.search(r"(\d+)\s*(?:days|day)\s*(?:filing|window|submission|limit)?", doc_text, re.IGNORECASE)
    if match_window:
        new_pol["filing_window_days"] = int(match_window.group(1))
    match_big = re.search(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:big-ticket|threshold|gst)?", doc_text, re.IGNORECASE)
    if match_big:
        try:
            val = float(match_big.group(1).replace(",", ""))
            if val > 1000:
                new_pol["big_ticket_threshold"] = val
        except ValueError:
            pass
    return new_pol


def run_deterministic_audit(receipt: dict, employee_profile: dict, context: str, client_info: str, currency_code: str, policy: dict, history: list) -> dict:
    violations = []
    risk_score = 10
    employee_name = employee_profile.get("name", "Unknown Employee")
    
    fx_rate = FX_RATES.get(currency_code, 1.0)
    raw_amount = receipt["total_printed"]
    total_inr = round(raw_amount * fx_rate, 2)
    reimbursable_inr = total_inr

    if total_inr <= 0:
        return {
            "status": "FLAGGED_FOR_REVIEW", "total_inr": 0.0, "reimbursed_inr": 0.0, "requires_mgr": True,
            "violations": ["UNREADABLE_TOTAL"], "risk_score": 60,
            "employee_message": "Could not detect valid total. Sent to Finance.",
            "finance_reasoning": "OCR failed to verify positive total."
        }

    calc_total = round(receipt["subtotal"] + receipt["tax"] + receipt["tip"], 2)
    if receipt["subtotal"] > 0 and abs(calc_total - raw_amount) > 1.0:
        violations.append(f"MATH_MISMATCH: Printed Total ({currency_code} {raw_amount}) != Subtotal+Tax+Tip ({currency_code} {calc_total})")
        risk_score += 65
        reimbursable_inr = 0.0

    for past in history:
        if past["employee"] == employee_name and past["date"] == receipt["transaction_date"]:
            if abs(past["total_inr"] - total_inr) < 5.0:
                violations.append(f"DUPLICATE_DETECTED: Matches earlier ₹{past['total_inr']} claim on same date.")
                risk_score = 95
                reimbursable_inr = 0.0

    big_ticket = policy.get("big_ticket_threshold", 15000.0)
    has_company_gstin = employee_profile.get("gst_number", "").strip() != ""
    if total_inr >= big_ticket and not has_company_gstin:
        violations.append(f"BIG_TICKET_GST_MISSING: Purchase >= ₹{big_ticket:,.0f} requires company GSTIN verification.")
        risk_score += 35

    banned_amount_inr = receipt.get("detected_alcohol", 0.0) * fx_rate
    if banned_amount_inr > 0 and reimbursable_inr > 0:
        reimbursable_inr = max(0.0, reimbursable_inr - banned_amount_inr)
        violations.append(f"BANNED_CATEGORY_DEDUCTION: Automatically deducted ₹{banned_amount_inr:,.2f} for restricted items.")
        risk_score += 25

    if "Home Office" in context:
        daily_cap = policy["home_cap"]
    elif "Tier 1" in context:
        daily_cap = policy["tier1_cap"]
    else:
        daily_cap = policy["tier2_cap"]

    prior_daily_spend = sum(x["reimbursed_inr"] for x in history if x["employee"] == employee_name and x["date"] == receipt["transaction_date"])
    if reimbursable_inr > 0 and (prior_daily_spend + reimbursable_inr) > daily_cap:
        allowed_remaining = max(0.0, round(daily_cap - prior_daily_spend, 2))
        violations.append(f"DAILY_CAP_EXCEEDED: Prior spend + claim exceeds daily cap of ₹{daily_cap:,.0f}. Capped at ₹{allowed_remaining:,.2f}.")
        reimbursable_inr = allowed_remaining
        risk_score += 20

    if total_inr > policy["client_threshold"] and not client_info.strip():
        violations.append(f"MISSING_CLIENT_DETAILS: Claims over ₹{policy['client_threshold']} require client name and attendee count.")
        risk_score += 20

    requires_mgr = total_inr > policy["mgr_threshold"] or risk_score >= 60

    if reimbursable_inr == 0.0:
        status = "REJECTED"
    elif violations:
        status = "FLAGGED_FOR_REVIEW" if risk_score >= 60 else "PARTIAL_APPROVAL"
    else:
        status = "APPROVED"

    return {
        "status": status,
        "total_inr": total_inr,
        "reimbursed_inr": reimbursable_inr,
        "requires_mgr": requires_mgr,
        "violations": violations,
        "risk_score": min(100, risk_score),
        "employee_message": f"Processed under policy {policy['version']}. Status: {status} | Forex Rate: 1 {currency_code} = ₹{fx_rate}",
        "finance_reasoning": f"Triggers: {'; '.join(violations) if violations else 'None'}"
    }


# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("### THE RECEIPT GRAVEYARD")
    st.caption(f"Policy Version: **{active_policy['version']}**")
    st.divider()
    
    user_role = st.radio(
        "Navigation",
        ["Welcome", "Policy Framework", "Employee Portal", "Finance Reviewer Portal", "Change History"],
        label_visibility="collapsed"
    )
    st.divider()

    if st.button("Load Demo Dataset", use_container_width=True):
        demo_bills = [
            ("toit_brewpub.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", {
                "merchant_name": "Toit Brewpub, Indiranagar", "transaction_date": datetime.now().strftime("%Y-%m-%d"), "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 2250.0, "tax": 112.50, "tip": 225.0, "total_printed": 2587.50, "is_itemized": True, "handwritten_tampering": False, "detected_alcohol": 0.0
            }),
            ("mumbai_taxi.png", "Priya Nair (Engineering)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "", {
                "merchant_name": "Shree Sai Tours & Taxi", "transaction_date": datetime.now().strftime("%Y-%m-%d"), "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 650.0, "tax": 100.0, "tip": 50.0, "total_printed": 1800.0, "is_itemized": True, "handwritten_tampering": True, "detected_alcohol": 0.0
            })
        ]
        sample_profile = {"name": "Aarav Sharma (Sales)", "id": "EMP-1042", "designation": "Senior Account Executive", "organization": "Enterprise Sales Division", "gst_number": "29AABCU9603R1ZN", "bank_account": "HDFC Salary A/c"}
        for fname, emp, ctx, cli, custom in demo_bills:
            res = run_deterministic_audit(custom, sample_profile, ctx, cli, "INR", active_policy, st.session_state.ledger)
            st.session_state.ledger.append({
                "id": len(st.session_state.ledger) + 1, "filename": fname, "employee": emp, "designation": sample_profile["designation"],
                "organization": sample_profile["organization"], "employee_id": sample_profile["id"], "gst_number": sample_profile["gst_number"],
                "bank_account": sample_profile["bank_account"], "context": ctx, "date": custom["transaction_date"], "merchant": custom["merchant_name"],
                "orig_currency": "INR", "total_inr": res["total_inr"], "reimbursed_inr": res["reimbursed_inr"], "policy_version": active_policy["version"],
                "mgr_signoff": "Yes" if res["requires_mgr"] else "No", "status": res["status"], "risk_score": res["risk_score"],
                "violations": ", ".join(res["violations"]), "employee_message": res["employee_message"], "finance_reasoning": res["finance_reasoning"],
                "raw_receipt": custom, "image_bytes": None
            })
        st.rerun()

    if st.button("Reset Session Memory", use_container_width=True):
        st.session_state.ledger = []
        st.rerun()

# ==============================================================================
# PORTAL -1: LANDING PAGE (WELCOME)
# ==============================================================================
if user_role == "Welcome":
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #f8fafc;'>Autonomous Corporate Expense Governance & Fraud Audit</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size: 1.15rem; max-width: 750px; margin: 0 auto 2.5rem auto; color: #94a3b8;'>"
        "Eliminate the friction of manual receipt auditing. The Receipt Graveyard combines offline OCR, deterministic tax verification, "
        "and multi-tier policy enforcement to instantly turn messy employee spend into compliant payroll decisions."
        "</p>", 
        unsafe_allow_html=True
    )

    col_c1, col_c2, col_c3 = st.columns([1, 1, 1])
    with col_c2:
        if st.button("Launch Application Portal", use_container_width=True):
            st.toast("Navigating to Employee Portal...", icon="■")

    st.markdown("<br><br>", unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3, gap="large")
    with f1:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color: #60a5fa; margin-bottom: 0.5rem;">[ 01 ]</h3>
            <h4 style="margin-bottom: 0.75rem;">Deterministic OCR Engine</h4>
            <p style="font-size: 0.9rem; line-height: 1.5; color: #94a3b8;">
                Extracts raw line items, dates, and currency totals instantly using secure offline processing without exposing sensitive financial data.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with f2:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color: #60a5fa; margin-bottom: 0.5rem;">[ 02 ]</h3>
            <h4 style="margin-bottom: 0.75rem;">Multi-Tier Policy Rules</h4>
            <p style="font-size: 0.9rem; line-height: 1.5; color: #94a3b8;">
                Dynamically enforces daily city caps, category restrictions, big-ticket GST requirements, and automated duplicate channel detection.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with f3:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color: #60a5fa; margin-bottom: 0.5rem;">[ 03 ]</h3>
            <h4 style="margin-bottom: 0.75rem;">Immutable Audit Ledger</h4>
            <p style="font-size: 0.9rem; line-height: 1.5; color: #94a3b8;">
                Provides finance reviewers with version-controlled policy safeguards, complete transparency history, and one-click CSV payroll exports.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
    <hr style="border-color: rgba(255,255,255,0.06); margin-bottom: 2rem;">
    <div style="display: flex; justify-content: space-between; align-items: center; color: #64748b; font-size: 0.85rem; padding-bottom: 2rem;">
        <div>&copy; 2026 The Receipt Graveyard Inc. All rights reserved.</div>
        <div>Enterprise Financial Operations Platform</div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# PORTAL 0: POLICY FRAMEWORK VIEW
# ==============================================================================
elif user_role == "Policy Framework":
    st.title("Corporate Financial Policy Framework")
    st.markdown("Active governance rules, automated thresholds, and compliance parameters.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Filing Window", f"{active_policy['filing_window_days']} Days")
    col2.metric("Big-Ticket Threshold", f"₹{active_policy['big_ticket_threshold']:,.0f}")
    col3.metric("Meal Card Cap", f"₹{active_policy['meal_card_limit']} / meal")

    st.markdown("---")
    st.markdown(f"**Active Policy Document:**\n> *{active_policy.get('document_text', 'Standard default parameters loaded.')}*")

# ==============================================================================
# PORTAL 1: EMPLOYEE PORTAL
# ==============================================================================
elif user_role == "Employee Portal":
    st.markdown("# Employee Expense Submission")
    st.markdown("Submit comprehensive expense claims with professional organizational metadata and out-of-pocket currency conversion.")

    col1, col2 = st.columns([1, 1.2], gap="medium")

    with col1:
        st.markdown("### Professional Identity & Organization")
        employee_name = st.selectbox("Select Employee Name", ["Aarav Sharma (Sales)", "Priya Nair (Engineering)", "Rohan Verma (VP Product)"])
        emp_id = st.text_input("Employee ID Number", value="EMP-1042" if "Aarav" in employee_name else "EMP-2089")
        designation = st.text_input("Job Designation", value="Senior Account Executive")
        organization = st.text_input("Organization / Department", value="Enterprise Sales Division")
        emp_gst = st.text_input("Corporate / Personal GST Number", value="29AABCU9603R1ZN")
        emp_bank = st.selectbox(
            "Expense Reimbursement Account",
            [
                "HDFC Salary A/c (•••• 4092) - Primary Payroll",
                "ICICI Corporate Expense Card (•••• 8812)",
                "Axis Bank Direct Reimbursement A/c"
            ]
        )

        st.markdown("---")
        st.markdown("### Expense Claim Details")
        col_cur, col_dt = st.columns(2)
        with col_cur:
            currency_code = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP", "SGD"])
        with col_dt:
            expense_time = st.text_input("Receipt Date & Time", value=datetime.now().strftime("%Y-%m-%d %H:%M"))

        trip_context = st.selectbox("Location Context", [
            "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)",
            "Home Office (Local)",
            "Business Trip - Tier 2 City (Pune / Jaipur / Kochi)"
        ])
        col_collab, col_cli = st.columns(2)
        with col_collab:
            colleagues = st.text_input("Colleagues Involved", placeholder="e.g. Rahul Verma")
        with col_cli:
            client_info = st.text_input("Client & Attendee Count", placeholder="e.g. Infosys - 3")

        uploaded_files = st.file_uploader("Upload Receipt Image (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        with st.expander("Manual Override Simulator"):
            use_custom = st.checkbox("Override OCR values")
            c_merch = st.text_input("Merchant", "Your Restaurant")
            c_sub = st.number_input("Subtotal", value=674.0)
            c_tax = st.number_input("Tax / GST", value=16.85)
            c_tot = st.number_input("Total Bill Amount", value=690.85)

        submit_btn = st.button("Submit Claim for Audit", use_container_width=True)

    if submit_btn:
        if not uploaded_files and not use_custom:
            st.warning("Please upload a receipt image first.")
        else:
            animation_placeholder = st.empty()
            status_text = st.empty()

            if lottie_scanning:
                with animation_placeholder:
                    st_lottie(lottie_scanning, height=100, key="scanning")
            
            status_text.markdown("<p style='text-align: center; color: #60a5fa;'>Executing deterministic OCR, tax verification & forex rules...</p>", unsafe_allow_html=True)

            employee_profile = {
                "name": employee_name,
                "id": emp_id,
                "designation": designation,
                "organization": organization,
                "gst_number": emp_gst,
                "bank_account": emp_bank
            }

            files_to_process = uploaded_files if uploaded_files else [None]
            for uf in files_to_process:
                fname = uf.name if uf else "manual_bill.png"
                img_bytes = uf.read() if uf else None
                
                custom_dict = None
                if use_custom:
                    custom_dict = {
                        "merchant_name": c_merch, "transaction_date": expense_time.split(" ")[0], "currency": currency_code,
                        "fx_rate_to_inr": FX_RATES[currency_code], "subtotal": c_sub, "tax": c_tax, "tip": 0.0,
                        "total_printed": c_tot, "is_itemized": True, "handwritten_tampering": False, "detected_alcohol": 0.0
                    }

                rec = parse_receipt_from_image_bytes(img_bytes, fname, custom_dict)
                res = run_deterministic_audit(rec, employee_profile, trip_context, client_info, currency_code, active_policy, st.session_state.ledger)

                st.session_state.ledger.append({
                    "id": len(st.session_state.ledger) + 1, "filename": fname, "employee": employee_name,
                    "designation": designation, "organization": organization, "employee_id": emp_id,
                    "gst_number": emp_gst, "bank_account": emp_bank, "colleagues": colleagues,
                    "context": trip_context, "date": expense_time, "merchant": rec["merchant_name"],
                    "orig_currency": currency_code, "total_inr": res["total_inr"], "reimbursed_inr": res["reimbursed_inr"],
                    "policy_version": active_policy["version"], "mgr_signoff": "Yes" if res["requires_mgr"] else "No",
                    "status": res["status"], "risk_score": res["risk_score"], "violations": ", ".join(res["violations"]),
                    "employee_message": res["employee_message"], "finance_reasoning": res["finance_reasoning"],
                    "raw_receipt": rec, "image_bytes": img_bytes
                })

            animation_placeholder.empty()
            status_text.empty()

            if lottie_success:
                st_lottie(lottie_success, height=70, key="success_anim")
            
            st.success("Claim successfully processed, audited, and entered into ledger.")

    with col2:
        st.markdown(f"### Reimbursement Tracker ({employee_name.split(' ')[0]})")
        my_claims = [c for c in st.session_state.ledger if c["employee"] == employee_name]
        if not my_claims:
            st.info("No claims submitted yet.")
        else:
            for item in reversed(my_claims):
                badge = {"APPROVED": "APPROVED", "PARTIAL_APPROVAL": "PARTIAL", "FLAGGED_FOR_REVIEW": "UNDER REVIEW", "REJECTED": "REJECTED"}.get(item["status"], "PENDING")
                st.markdown(f"**{badge} — {item['merchant']}** (`{item['date']}`)")
                st.markdown(f"Claimed: `₹{item['total_inr']:,.2f}` ➡️ Payout A/c: `{item.get('bank_account', 'Salary A/c')[:20]}`")
                st.caption(f"{item['employee_message']}")
                st.divider()

# ==============================================================================
# PORTAL 2: FINANCE REVIEWER PORTAL
# ==============================================================================
elif user_role == "Finance Reviewer Portal":
    st.title("Finance Governance Center")
    
    pin = st.sidebar.text_input("Admin PIN (1234)", value="1234", type="password")
    if pin != "1234":
        st.error("Access Denied. Enter PIN 1234.")
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(["Audit Queue", "Policy Control", "Monthly Ledger", "Backup & Restore"])

    with tab1:
        if not st.session_state.ledger:
            st.info("Queue is empty.")
        else:
            for idx, item in enumerate(reversed(st.session_state.ledger)):
                with st.expander(f"[{item['status']}] {item['employee']} ({item.get('designation', 'Staff')}) — {item['merchant']} (₹{item['total_inr']:,.2f})"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if item["image_bytes"]:
                            st.image(item["image_bytes"], use_container_width=True)
                    with c2:
                        st.markdown(f"**Organization:** `{item.get('organization', 'N/A')}` | **A/c:** `{item.get('bank_account', 'Salary A/c')}`")
                        st.markdown(f"**Approved Payout:** `₹{item['reimbursed_inr']:,.2f}` | **Risk Score:** `{item['risk_score']}/100`")
                        st.write(f"**Forensic Note:** {item['finance_reasoning']}")
                        if item["violations"]:
                            st.error(f"**Violations:** {item['violations']}")

    with tab2:
        st.markdown("### Safeguarded Policy Versioning & Ingestion")
        with st.form("policy_document_form"):
            author_name = st.text_input("Reviewer Name", "Vikram Mehta")
            change_reason = st.text_input("Justification", "Updated via document parsing")
            
            sample_policy_doc = """
            CORPORATE EXPENSE GOVERNANCE GUIDELINE v2.4
            - Filing Window: Claims must be filed within 45 days of expense generation.
            - Big-Ticket Threshold: Purchases exceeding ₹20,000 must carry valid corporate GSTIN.
            - Tier-1 Metro Cap: Daily hotel and meal allowance capped at ₹30,000.
            - Digital Meal Cards: Restricted to ₹250 per transaction limit.
            """
            
            doc_input = st.text_area("Full Policy Document Text / Guidelines:", value=active_policy.get("document_text", sample_policy_doc), height=140)
            
            col_d1, col_d2 = st.columns(2)
            load_dummy_btn = col_d1.form_submit_button("Load Standard Dummy Policies")
            commit_doc_btn = col_d2.form_submit_button("Parse & Commit New Policy Version", type="primary")

            if load_dummy_btn:
                doc_input = sample_policy_doc
                st.success("Loaded dummy guidelines text. Click Commit to apply.")

            if commit_doc_btn:
                parsed_dict = parse_policy_document_text(doc_input, active_policy)
                next_ver = f"v1.{len(st.session_state.policy_versions)}"
                parsed_dict.update({
                    "version": next_ver,
                    "updated_by": author_name,
                    "reason": change_reason,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                st.session_state.policy_versions.append(parsed_dict)
                st.success(f"Successfully parsed document and published Policy Version **{next_ver}**.")
                st.rerun()

    with tab3:
        if st.session_state.ledger:
            df = pd.DataFrame(st.session_state.ledger).drop(columns=["raw_receipt", "image_bytes"], errors="ignore")
            st.dataframe(df, use_container_width=True)
            st.download_button("Download CSV Ledger", df.to_csv(index=False).encode("utf-8"), "ledger.csv", "mime/csv")

    with tab4:
        st.subheader("System State Backup & Restore")
        backup_data = {
            "policy_versions_history": st.session_state.policy_versions,
            "audit_ledger": [{k: v for k, v in item.items() if k != "image_bytes"} for item in st.session_state.ledger]
        }
        st.download_button("Download JSON Backup", json.dumps(backup_data, indent=4, default=str), "backup.json", "application/json")

# ==============================================================================
# PORTAL 3: CHANGE HISTORY
# ==============================================================================
elif user_role == "Change History":
    st.title("Policy Change History")
    st.markdown("Immutable audit ledger recording all modifications made by policy owners.")

    for record in st.session_state.policy_versions:
        with st.container():
            st.markdown(
                f"""
                **Timestamp:** `{record.get('timestamp', 'N/A')}` | **Version:** `{record['version']}`  
                * **Updated By:** {record.get('updated_by', 'System')}  
                * **Reason:** {record.get('reason', 'Initial release')}  
                * **Extracted Parameters:** Filing Window = {record.get('filing_window_days', 30)}d, Big-Ticket = ₹{record.get('big_ticket_threshold', 15000):,.0f}, Tier-1 Cap = ₹{record.get('tier1_cap', 25000):,.0f}  
                ---
                """
            )
