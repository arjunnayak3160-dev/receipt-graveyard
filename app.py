import streamlit as st
import pandas as pd
import re
from datetime import datetime
from PIL import Image
import io
import json

# Try loading the free offline OCR engine
try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False
import requests
from streamlit_lottie import st_lottie

# Helper to load Lottie animations from public JSON URLs safely
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

# --- PAGE SETUP & PROFESSIONAL APPLE/LINEAR CSS THEME ---
st.set_page_config(page_title="The Receipt Graveyard | Enterprise OS", page_icon="■", layout="wide")

st.markdown("""
<style>
    /* Global Futura Font & Dark Glass Theme */
    .stApp {
        background-color: #080b11;
        background-image: radial-gradient(circle at 10% 10%, rgba(30, 41, 59, 0.5) 0%, transparent 40%),
                          radial-gradient(circle at 90% 90%, rgba(15, 23, 42, 0.6) 0%, transparent 40%);
        color: #e2e8f0;
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: #ffffff !important;
    }
    
    h1 { font-size: 2.2rem !important; }
    h2 { font-size: 1.8rem !important; }
    h3 { font-size: 1.35rem !important; }
    h4 { font-size: 1.1rem !important; }

    p, span, label, div {
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
    }

    /* Snug Frosted Glass Containers */
    div.stExpander, div[data-testid="stVerticalBlock"] > div.element-container {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.75rem;
    }

    /* Snug Metric Cards */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 12px 16px;
        border-radius: 10px;
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 1.5rem !important;
    }

    /* Sidebar Glassmorphism */
    section[data-testid="stSidebar"] {
        background-color: rgba(8, 11, 17, 0.95);
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255, 255, 255, 0.04);
    }

    /* Professional Action Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.02em;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1d4ed8, #1e40af);
        border-color: rgba(255, 255, 255, 0.25);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
    }

    /* Inputs & Selectboxes */
    input, select, textarea {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        color: #ffffff !important;
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
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


# --- 2. OFFLINE OCR & PARSER ---
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

    date_found = "2026-10-15"
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
        "line_items": [{"description": "Itemized Bill", "amount": subtotal if subtotal > 0 else total_printed, "category": "Food"}]
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


def run_deterministic_audit(receipt: dict, employee_profile: dict, context: str, client_info: str, policy: dict, history: list) -> dict:
    violations = []
    risk_score = 10
    employee_name = employee_profile.get("name", "Unknown Employee")
    total_inr = round(receipt["total_printed"], 2)
    reimbursable_inr = total_inr

    if total_inr <= 0:
        return {
            "status": "FLAGGED_FOR_REVIEW", "total_inr": 0.0, "reimbursed_inr": 0.0, "requires_mgr": True,
            "violations": ["UNREADABLE_TOTAL"], "risk_score": 60,
            "employee_message": "Could not detect valid total. Sent to Finance.",
            "finance_reasoning": "OCR failed to verify positive total."
        }

    calc_total = round(receipt["subtotal"] + receipt["tax"] + receipt["tip"], 2)
    if receipt["subtotal"] > 0 and abs(calc_total - receipt["total_printed"]) > 1.0:
        violations.append(f"MATH_MISMATCH: Printed (₹{receipt['total_printed']}) != Sum (₹{calc_total})")
        risk_score += 65
        reimbursable_inr = 0.0

    for past in history:
        if past["employee"] == employee_name and past["date"] == receipt["transaction_date"]:
            if abs(past["total_inr"] - total_inr) < 5.0:
                violations.append(f"DUPLICATE_DETECTED: Matches earlier ₹{past['total_inr']} claim.")
                risk_score = 95
                reimbursable_inr = 0.0

    big_ticket = policy.get("big_ticket_threshold", 15000.0)
    has_company_gstin = employee_profile.get("gst_number", "").strip() != ""
    if total_inr >= big_ticket and not has_company_gstin:
        violations.append(f"BIG_TICKET_GST_MISSING: Purchase >= ₹{big_ticket:,.0f} requires company GSTIN.")
        risk_score += 35

    if "Home Office" in context:
        daily_cap = policy["home_cap"]
    elif "Tier 1" in context:
        daily_cap = policy["tier1_cap"]
    else:
        daily_cap = policy["tier2_cap"]

    prior_daily_spend = sum(x["reimbursed_inr"] for x in history if x["employee"] == employee_name and x["date"] == receipt["transaction_date"])
    if reimbursable_inr > 0 and (prior_daily_spend + reimbursable_inr) > daily_cap:
        allowed_remaining = max(0.0, round(daily_cap - prior_daily_spend, 2))
        violations.append(f"DAILY_CAP_EXCEEDED: Capped at ₹{allowed_remaining} per day.")
        reimbursable_inr = allowed_remaining
        risk_score += 20

    if total_inr > policy["client_threshold"] and not client_info.strip():
        violations.append(f"MISSING_CLIENT_DETAILS: Bills over ₹{policy['client_threshold']} require attendee info.")
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
        "employee_message": f"Processed under policy {policy['version']}. Status: {status}",
        "finance_reasoning": f"Triggers: {'; '.join(violations) if violations else 'None'}"
    }


# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("### RECEIPT GRAVEYARD")
    st.caption(f"Policy Version: **{active_policy['version']}**")
    
    user_role = st.radio(
        "Navigation",
        ["Policy Framework", "Employee Portal", "Finance Reviewer Portal", "Change History"],
        label_visibility="collapsed"
    )
    st.divider()

    if st.button("Load Demo Dataset", use_container_width=True):
        demo_bills = [
            ("toit_brewpub.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", {
                "merchant_name": "Toit Brewpub, Indiranagar", "transaction_date": "2026-10-15", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 2250.0, "tax": 112.50, "tip": 225.0, "total_printed": 2587.50, "is_itemized": True, "handwritten_tampering": False
            }),
            ("mumbai_taxi.png", "Priya Nair (Engineering)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "", {
                "merchant_name": "Shree Sai Tours & Taxi", "transaction_date": "2026-10-16", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 650.0, "tax": 100.0, "tip": 50.0, "total_printed": 1800.0, "is_itemized": True, "handwritten_tampering": True
            })
        ]
        sample_profile = {"name": "Aarav Sharma (Sales)", "id": "EMP-1042", "gst_number": "29AABCU9603R1ZN", "bank_account": "HDFC Salary A/c"}
        for fname, emp, ctx, cli, custom in demo_bills:
            res = run_deterministic_audit(custom, sample_profile, ctx, cli, active_policy, st.session_state.ledger)
            st.session_state.ledger.append({
                "id": len(st.session_state.ledger) + 1, "filename": fname, "employee": emp, "context": ctx,
                "date": custom["transaction_date"], "merchant": custom["merchant_name"], "orig_currency": custom["currency"],
                "total_inr": res["total_inr"], "reimbursed_inr": res["reimbursed_inr"], "policy_version": active_policy["version"],
                "mgr_signoff": "Yes" if res["requires_mgr"] else "No", "status": res["status"], "risk_score": res["risk_score"],
                "violations": ", ".join(res["violations"]), "employee_message": res["employee_message"],
                "finance_reasoning": res["finance_reasoning"], "raw_receipt": custom, "image_bytes": None
            })
        st.rerun()

    if st.button("Reset Session Memory", use_container_width=True):
        st.session_state.ledger = []
        st.rerun()

# ==============================================================================
# PORTAL 0: POLICY FRAMEWORK VIEW
# ==============================================================================
if user_role == "Policy Framework":
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
    st.markdown("Manage employee profile identity and submit structured work receipts for rapid reimbursement.")

    col1, col2 = st.columns([1, 1.2], gap="medium")

    with col1:
        st.markdown("### Employee Identification Profile")
        employee_name = st.selectbox("Select Employee Name", ["Aarav Sharma (Sales)", "Priya Nair (Engineering)", "Rohan Verma (VP Product)"])
        emp_id = st.text_input("Employee ID Number", value="EMP-1042" if "Aarav" in employee_name else "EMP-2089")
        emp_gst = st.text_input("Corporate / Personal GST Number", value="29AABCU9603R1ZN", placeholder="e.g. 29AAAAA0000A1Z5")
        emp_bank = st.selectbox(
            "Expense Reimbursement Account",
            [
                "HDFC Salary A/c (•••• 4092) - Primary Payroll",
                "ICICI Corporate Expense Card (•••• 8812)",
                "Axis Bank Direct Reimbursement A/c"
            ]
        )

        st.markdown("---")
        st.markdown("### New Expense Claim")
        trip_context = st.selectbox("Location Context", [
            "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)",
            "Home Office (Local)",
            "Business Trip - Tier 2 City (Pune / Jaipur / Kochi)"
        ])
        client_info = st.text_input("Client Name & Attendees", placeholder="e.g., Infosys - 3 Attendees")
        uploaded_files = st.file_uploader("Upload Receipt (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        with st.expander("Manual Override Simulator"):
            use_custom = st.checkbox("Override OCR values")
            c_merch = st.text_input("Merchant", "Your Restaurant")
            c_date = st.text_input("Date (YYYY-MM-DD)", "2026-10-17")
            c_sub = st.number_input("Subtotal (₹)", value=674.0)
            c_tax = st.number_input("Tax / GST (₹)", value=16.85)
            c_tot = st.number_input("Total (₹)", value=690.85)

        submit_btn = st.button("Submit Claim for Audit", use_container_width=True)

    if submit_btn:
        if not uploaded_files and not use_custom:
            st.warning("Please upload a receipt image first.")
        else:
            animation_placeholder = st.empty()
            status_text = st.empty()

            if lottie_scanning:
                with animation_placeholder:
                    st_lottie(lottie_scanning, height=120, key="scanning")
            
            status_text.markdown("<p style='text-align: center; color: #60a5fa;'>Analyzing OCR text, verifying tax logic, and validating policy...</p>", unsafe_allow_html=True)

            employee_profile = {
                "name": employee_name,
                "id": emp_id,
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
                        "merchant_name": c_merch, "transaction_date": c_date, "currency": "INR", "fx_rate_to_inr": 1.0,
                        "subtotal": c_sub, "tax": c_tax, "tip": 0.0, "total_printed": c_tot,
                        "is_itemized": True, "handwritten_tampering": False
                    }

                rec = parse_receipt_from_image_bytes(img_bytes, fname, custom_dict)
                res = run_deterministic_audit(rec, employee_profile, trip_context, client_info, active_policy, st.session_state.ledger)

                st.session_state.ledger.append({
                    "id": len(st.session_state.ledger) + 1, "filename": fname, "employee": employee_name,
                    "employee_id": emp_id, "gst_number": emp_gst, "bank_account": emp_bank,
                    "context": trip_context, "date": rec["transaction_date"], "merchant": rec["merchant_name"],
                    "orig_currency": rec["currency"], "total_inr": res["total_inr"], "reimbursed_inr": res["reimbursed_inr"],
                    "policy_version": active_policy["version"], "mgr_signoff": "Yes" if res["requires_mgr"] else "No",
                    "status": res["status"], "risk_score": res["risk_score"], "violations": ", ".join(res["violations"]),
                    "employee_message": res["employee_message"], "finance_reasoning": res["finance_reasoning"],
                    "raw_receipt": rec, "image_bytes": img_bytes
                })

            animation_placeholder.empty()
            status_text.empty()

            if lottie_success:
                st_lottie(lottie_success, height=80, key="success_anim")
            
            st.success("Receipt successfully scanned, audited, and added to ledger.")

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
                with st.expander(f"[{item['status']}] {item['employee']} ({item.get('employee_id', 'N/A')}) — {item['merchant']} (₹{item['total_inr']:,.2f})"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if item["image_bytes"]:
                            st.image(item["image_bytes"], use_container_width=True)
                    with c2:
                        st.markdown(f"**Payout A/c:** `{item.get('bank_account', 'Salary A/c')}`")
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
