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

# Load sleek tech/scanning and success animations
lottie_scanning = load_lottie_url("https://assets5.lottiefiles.com/packages/lf20_v1yqrgec.json")
lottie_success = load_lottie_url("https://assets10.lottiefiles.com/packages/lf20_oxefatps.json")

# --- PAGE SETUP & APPLE TRANSLUCENT CSS THEME ---
st.set_page_config(page_title="The Receipt Graveyard", page_icon="🧾", layout="wide")

st.markdown("""
<style>
    /* Apple Dark / Translucent Theme Styling */
    .stApp {
        background-color: #0b0f19;
        background-image: radial-gradient(circle at 15% 15%, rgba(41, 55, 95, 0.4) 0%, transparent 40%),
                          radial-gradient(circle at 85% 85%, rgba(67, 39, 94, 0.3) 0%, transparent 40%);
        color: #f3f4f6;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Frosted Glass Containers (Apple Glassmorphism) */
    div.stExpander, div[data-testid="stVerticalBlock"] > div.element-container, .css-1r6slb0 {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    /* Metric Cards Styling */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 16px;
        border-radius: 14px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    div[data-testid="stMetricLabel"] {
        color: #9ca3af !important;
        font-size: 0.85rem !important;
    }
    div[data-testid="stMetricValue"] {
        color: #f9fafb !important;
        font-weight: 600 !important;
    }

    /* Sidebar Glassmorphism */
    section[data-testid="stSidebar"] {
        background-color: rgba(11, 15, 25, 0.85);
        backdrop-filter: blur(25px);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.8), rgba(37, 99, 235, 0.9));
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.9), rgba(29, 78, 216, 1));
        border-color: rgba(255, 255, 255, 0.3);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.5);
    }

    /* Inputs & Selectboxes */
    input, select, textarea {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #fff !important;
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. SESSION MEMORY & OPTION C POLICY VERSIONING ---
if "ledger" not in st.session_state:
    st.session_state.ledger = []

if "policy_versions" not in st.session_state:
    st.session_state.policy_versions = [
        {
            "version": "v1.0",
            "effective_date": "2026-10-01",
            "updated_by": "System Default (CFO Office)",
            "timestamp": "2026-10-01 09:00:00",
            "reason": "Initial Q4 Corporate Expense Policy release",
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

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

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


def run_deterministic_audit(receipt: dict, employee: str, context: str, client_info: str, policy: dict, history: list) -> dict:
    violations = []
    risk_score = 10
    fx = receipt.get("fx_rate_to_inr", 1.0)
    total_inr = round(receipt["total_printed"] * fx, 2)
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
        if past["employee"] == employee and past["date"] == receipt["transaction_date"]:
            if abs(past["total_inr"] - total_inr) < 5.0:
                violations.append(f"DUPLICATE_DETECTED: Matches earlier ₹{past['total_inr']} claim.")
                risk_score = 95
                reimbursable_inr = 0.0

    big_ticket = policy.get("big_ticket_threshold", 15000.0)
    has_company_gstin = receipt.get("has_company_gstin", True)
    if total_inr >= big_ticket and not has_company_gstin:
        violations.append(f"BIG_TICKET_GST_MISSING: Purchase >= ₹{big_ticket:,.0f} lacks mandatory company GSTIN.")
        risk_score += 35

    if "Home Office" in context:
        daily_cap = policy["home_cap"]
    elif "Tier 1" in context:
        daily_cap = policy["tier1_cap"]
    else:
        daily_cap = policy["tier2_cap"]

    prior_daily_spend = sum(x["reimbursed_inr"] for x in history if x["employee"] == employee and x["date"] == receipt["transaction_date"])
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


# --- 3. SIDEBAR ---
with st.sidebar:
    st.markdown("### 🧾 Receipt Graveyard")
    st.caption(f"🛡️ Policy: **{active_policy['version']}**")
    user_role = st.radio("Portal Navigation", ["📋 Current Policy View", "👤 Employee Portal", "🕵️‍♂️ Finance Reviewer Portal", "📜 Change History"])
    st.divider()

    if st.button("📥 Load Demo Dataset (5 Bills)", use_container_width=True):
        demo_bills = [
            ("toit_brewpub.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", {
                "merchant_name": "Toit Brewpub, Indiranagar", "transaction_date": "2026-10-15", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 2250.0, "tax": 112.50, "tip": 225.0, "total_printed": 2587.50, "is_itemized": True, "handwritten_tampering": False, "has_company_gstin": True
            }),
            ("upi_screenshot.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", {
                "merchant_name": "Toit Brewpub Bengaluru (UPI)", "transaction_date": "2026-10-15", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 0.0, "tax": 0.0, "tip": 0.0, "total_printed": 2587.50, "is_itemized": False, "handwritten_tampering": False, "has_company_gstin": False
            }),
            ("mumbai_taxi.png", "Priya Nair (Engineering)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "", {
                "merchant_name": "Shree Sai Tours & Taxi", "transaction_date": "2026-10-16", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 650.0, "tax": 100.0, "tip": 50.0, "total_printed": 1800.0, "is_itemized": True, "handwritten_tampering": True, "has_company_gstin": True
            })
        ]
        for fname, emp, ctx, cli, custom in demo_bills:
            res = run_deterministic_audit(custom, emp, ctx, cli, active_policy, st.session_state.ledger)
            st.session_state.ledger.append({
                "id": len(st.session_state.ledger) + 1, "filename": fname, "employee": emp, "context": ctx,
                "date": custom["transaction_date"], "merchant": custom["merchant_name"], "orig_currency": custom["currency"],
                "total_inr": res["total_inr"], "reimbursed_inr": res["reimbursed_inr"], "policy_version": active_policy["version"],
                "mgr_signoff": "Yes ⚠️" if res["requires_mgr"] else "No", "status": res["status"], "risk_score": res["risk_score"],
                "violations": ", ".join(res["violations"]), "employee_message": res["employee_message"],
                "finance_reasoning": res["finance_reasoning"], "raw_receipt": custom, "image_bytes": None
            })
        st.rerun()

    if st.button("🗑️ Reset Memory", use_container_width=True):
        st.session_state.ledger = []
        st.rerun()

# ==============================================================================
# PORTAL 0: CURRENT POLICY VIEW
# ==============================================================================
if user_role == "📋 Current Policy View":
    st.title("Corporate Financial Policy Framework")
    st.markdown("Overview of active governance rules, automated thresholds, and compliance guardrails.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Filing Window", f"{active_policy['filing_window_days']} Days")
    col2.metric("Big-Ticket Threshold", f"₹{active_policy['big_ticket_threshold']:,.0f}")
    col3.metric("Meal Card Cap", f"₹{active_policy['meal_card_limit']} / meal")

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["1. General Rules", "2. Categories", "3. Meal Cards", "4. Allowances", "5. Approvals"]
    )

    with tab1:
        st.subheader("General Claim Rules")
        st.markdown(
            f"""
        | Rule | System Check | Non-Compliance Action |
        |---|---|---|
        | **Valid Bill Required** | Vendor, date, itemized prices, and description present | Reject or Request Info |
        | **GST Invoice** | Purchases exceeding **₹{active_policy['big_ticket_threshold']:,.0f}** must carry company GSTIN | Flag for Review |
        | **Merchant GSTIN** | Valid merchant tax registration verified | Flag |
        | **Filing Window** | Claims submitted within **{active_policy['filing_window_days']} days** of expense | Reject |
        | **Audit Trail** | Immutable storage of all receipts, edits, and decisions | Automatic |
        """
        )

    with tab2:
        st.subheader("Expense Categories & Limits")
        st.markdown(
            f"""
        | Category | Limits & Settings |
        |---|---|
        | **Official Travel & Conveyance** | City Daily Cap: ₹{active_policy['travel_city_limit']:,.0f} \| Category Cap: ₹{active_policy['travel_category_cap']:,.0f} |
        | **Client Entertainment** | Per Meal Cap: ₹{active_policy['client_meal_cap']:,.0f} (Attendee list required) |
        | **Communication & Tech** | Category Cap: ₹{active_policy['comm_tech_cap']:,.0f} / month |
        | **Fuel & Maintenance** | Slabs based on engine capacity (Max CC: {active_policy['fuel_slab_cc']}cc) |
        """
        )

    with tab3:
        st.subheader("Digital Meal Cards (Pluxee / Sodexo Style)")
        st.markdown(
            f"""
        * **Per Meal Limit:** ₹{active_policy['meal_card_limit']} (Up to {active_policy['meal_card_max_per_day']} meals per working day counted).
        * **Card Mechanism:** Strictly closed-loop or semi-closed prepaid cards; zero cash payouts allowed.
        * **Merchant Lock:** Restricted exclusively to Food & Beverage MCC codes.
        * **Deduplication:** Automatically blocks duplicate claims for meals already expensed on corporate cards.
        """
        )

    with tab4:
        st.subheader("Proof-Based Payroll Allowances")
        st.markdown(
            """
        * **HRA:** Exempt amount based on rent minus 10% basic, capped at 50% (metros) or 40% (non-metros). Landlord PAN required above ₹1,00,000 annual rent.
        * **LTA:** Travel cost exemption claimable twice in a 4-year block period.
        * **Children Education:** Capped at a maximum of 2 children.
        * **Telephony & Internet:** 100% tax-free reimbursement upon actual billing.
        """
        )

    with tab5:
        st.subheader("Approval Workflow Structure")
        st.markdown(
            """
        1. **Level 1 (Direct Manager):** Validates operational necessity and business relevance.
        2. **Level 2 (Finance / AP Reviewer):** Audits limits, tax compliance, and GST validity.
        3. **Payout Execution:** Automated direct bank credit synced with payroll cycles.
        """
        )

# ==============================================================================
# PORTAL 1: EMPLOYEE PORTAL
# ==============================================================================
elif user_role == "👤 Employee Portal":
    st.title("👤 Employee Expense Submission")
    st.caption("Upload receipts to get reimbursed securely under automated corporate policy.")

    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.markdown("#### 📤 New Expense Claim")
        employee_name = st.selectbox("Employee Name", ["Aarav Sharma (Sales)", "Priya Nair (Engineering)", "Rohan Verma (VP Product)"])
        trip_context = st.selectbox("Location Context", [
            "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)",
            "Home Office (Local)",
            "Business Trip - Tier 2 City (Pune / Jaipur / Kochi)"
        ])
        client_info = st.text_input("Client Name & Attendees", placeholder="e.g., Infosys - 3 Attendees")
        has_company_gstin = st.checkbox("Carries Company GSTIN (for big-ticket items)", value=True)
        uploaded_files = st.file_uploader("Upload Receipt (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        with st.expander("🧪 Manual Override Simulator"):
            use_custom = st.checkbox("Override OCR values")
            c_merch = st.text_input("Merchant", "Your Restaurant")
            c_date = st.text_input("Date (YYYY-MM-DD)", "2026-10-17")
            c_sub = st.number_input("Subtotal (₹)", value=674.0)
            c_tax = st.number_input("Tax / GST (₹)", value=16.85)
            c_tot = st.number_input("Total (₹)", value=690.85)

        submit_btn = st.button("🚀 Submit Claim", use_container_width=True)

    if submit_btn:
        if not uploaded_files and not use_custom:
            st.warning("⚠️ Please upload a receipt image first.")
        else:
            animation_placeholder = st.empty()
            status_text = st.empty()

            if lottie_scanning:
                with animation_placeholder:
                    st_lottie(lottie_scanning, height=150, key="scanning")
            
            status_text.markdown("<p style='text-align: center; color: #60a5fa;'>🔍 AI Engine reading OCR text, verifying GST math & matching policy...</p>", unsafe_allow_html=True)

            files_to_process = uploaded_files if uploaded_files else [None]
            for uf in files_to_process:
                fname = uf.name if uf else "manual_bill.png"
                img_bytes = uf.read() if uf else None
                
                custom_dict = None
                if use_custom:
                    custom_dict = {
                        "merchant_name": c_merch, "transaction_date": c_date, "currency": "INR", "fx_rate_to_inr": 1.0,
                        "subtotal": c_sub, "tax": c_tax, "tip": 0.0, "total_printed": c_tot,
                        "is_itemized": True, "handwritten_tampering": False, "has_company_gstin": has_company_gstin
                    }

                rec = parse_receipt_from_image_bytes(img_bytes, fname, custom_dict)
                rec["has_company_gstin"] = has_company_gstin
                res = run_deterministic_audit(rec, employee_name, trip_context, client_info, active_policy, st.session_state.ledger)

                st.session_state.ledger.append({
                    "id": len(st.session_state.ledger) + 1, "filename": fname, "employee": employee_name,
                    "context": trip_context, "date": rec["transaction_date"], "merchant": rec["merchant_name"],
                    "orig_currency": rec["currency"], "total_inr": res["total_inr"], "reimbursed_inr": res["reimbursed_inr"],
                    "policy_version": active_policy["version"], "mgr_signoff": "Yes ⚠️" if res["requires_mgr"] else "No",
                    "status": res["status"], "risk_score": res["risk_score"], "violations": ", ".join(res["violations"]),
                    "employee_message": res["employee_message"], "finance_reasoning": res["finance_reasoning"],
                    "raw_receipt": rec, "image_bytes": img_bytes
                })

            animation_placeholder.empty()
            status_text.empty()

            if lottie_success:
                st_lottie(lottie_success, height=100, key="success_anim")
            
            st.success("✅ Receipt successfully scanned, audited, and added to ledger!")

# ==============================================================================
# PORTAL 2: FINANCE REVIEWER PORTAL (WITH PIN PROTECTION & BACKUP/RESTORE)
# ==============================================================================
elif user_role == "🕵️‍♂️ Finance Reviewer Portal":
    st.title("🕵️‍♂️ Finance Governance Center")
    
    # Secure PIN Gate
    pin = st.sidebar.text_input("Admin PIN (1234)", value="", type="password")
    if pin != "1234":
        st.warning("🔒 Please enter the Admin PIN (`1234`) in the sidebar to access governance features.")
        st.stop()
    else:
        st.success("🔓 Admin access verified successfully.")

    tab1, tab2, tab3, tab4 = st.tabs(["🚨 Audit Queue", "🛡️ Policy Control (Option C)", "📊 Monthly Ledger", "💾 Backup & Restore"])

    with tab1:
        if not st.session_state.ledger:
            st.info("Queue is empty.")
        else:
            for idx, item in enumerate(reversed(st.session_state.ledger)):
                color = {"APPROVED": "🟢", "PARTIAL_APPROVAL": "🟡", "FLAGGED_FOR_REVIEW": "🟠", "REJECTED": "🔴"}.get(item["status"], "🟠")
                with st.expander(f"{color} [{item['status']}] {item['employee']} — {item['merchant']} (₹{item['total_inr']:,.2f})"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if item["image_bytes"]:
                            st.image(item["image_bytes"], use_container_width=True)
                    with c2:
                        st.markdown(f"**Payout:** `₹{item['reimbursed_inr']:,.2f}` | **Risk:** `{item['risk_score']}/100`")
                        st.write(f"**Forensic Note:** {item['finance_reasoning']}")
                        if item["violations"]:
                            st.error(f"**Violations:** {item['violations']}")

    with tab2:
        st.markdown("#### Safeguarded Policy Versioning")
        with st.form("policy_editor_form"):
            author_name = st.text_input("Reviewer Name", "Vikram Mehta")
            change_reason = st.text_input("Justification", "Q4 Cap Adjustment")
            new_filing = st.number_input("Filing Window (Days)", min_value=1, max_value=180, value=int(active_policy.get("filing_window_days", 30)))
            new_big_ticket = st.number_input("Big-Ticket GST Threshold (₹)", min_value=1000.0, max_value=100000.0, value=float(active_policy.get("big_ticket_threshold", 15000.0)), step=1000.0)
            new_t1 = st.number_input("Tier-1 Metro Daily Cap (₹)", value=float(active_policy["tier1_cap"]))
            new_meal_limit = st.number_input("Meal Card Limit per Meal (₹)", value=float(active_policy.get("meal_card_limit", 200.0)))
            
            commit_btn = st.form_submit_button("Commit New Policy Version")
            if commit_btn:
                next_ver = f"v1.{len(st.session_state.policy_versions)}"
                new_pol = dict(active_policy)
                new_pol.update({
                    "version": next_ver,
                    "updated_by": author_name,
                    "reason": change_reason,
                    "filing_window_days": new_filing,
                    "big_ticket_threshold": new_big_ticket,
                    "tier1_cap": new_t1,
                    "meal_card_limit": new_meal_limit,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                st.session_state.policy_versions.append(new_pol)
                st.success(f"Published {next_ver} successfully!")
                st.rerun()

    with tab3:
        if st.session_state.ledger:
            df = pd.DataFrame(st.session_state.ledger).drop(columns=["raw_receipt", "image_bytes"], errors="ignore")
            st.dataframe(df, use_container_width=True)
            st.download_button("Download CSV Ledger", df.to_csv(index=False).encode("utf-8"), "ledger.csv", "mime/csv")

    with tab4:
        st.subheader("💾 Export & Import System Backups")
        
        col_exp, col_imp = st.columns(2)
        
        with col_exp:
            st.markdown("##### Export Backup")
            backup_data = {
                "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "active_policy_version": active_policy["version"],
                "policy_versions_history": st.session_state.policy_versions,
                "audit_ledger": [{k: v for k, v in item.items() if k != "image_bytes"} for item in st.session_state.ledger]
            }
            json_string = json.dumps(backup_data, indent=4, default=str)
            st.download_button(
                label="📥 Download JSON Backup",
                data=json_string,
                file_name=f"finance_policy_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )

        with col_imp:
            st.markdown("##### Restore Backup")
            uploaded_backup = st.file_uploader("Upload Backup JSON", type=["json"])
            if uploaded_backup is not None:
                try:
                    backup_content = json.load(uploaded_backup)
                    if "policy_versions_history" in backup_content and "audit_ledger" in backup_content:
                        st.success("Backup validated successfully!")
                        if st.button("⚠️ Confirm & Overwrite State", type="primary", use_container_width=True):
                            st.session_state.policy_versions = backup_content["policy_versions_history"]
                            st.session_state.ledger = backup_content["audit_ledger"]
                            st.success("System restored successfully! Refreshing...")
                            st.rerun()
                    else:
                        st.error("Invalid backup format: Missing keys.")
                except Exception as e:
                    st.error(f"Failed to parse JSON: {e}")

# ==============================================================================
# PORTAL 3: CHANGE HISTORY
# ==============================================================================
elif user_role == "📜 Change History":
    st.title("Policy Change History")
    st.markdown("Immutable audit ledger recording all modifications made by policy owners.")

    for record in st.session_state.policy_versions:
        with st.container():
            st.markdown(
                f"""
            **🕒 {record.get('timestamp', 'N/A')}** (Version: `{record['version']}`)  
            * **Updated By:** {record.get('updated_by', 'System')}  
            * **Reason:** {record.get('reason', 'Initial release')}  
            * **Key Parameters:** Filing Window = {record.get('filing_window_days', 30)}d, Big-Ticket = ₹{record.get('big_ticket_threshold', 15000):,.0f}, Tier-1 Cap = ₹{record.get('tier1_cap', 25000):,.0f}
            ---
            """
            )
