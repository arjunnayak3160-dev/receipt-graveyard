import streamlit as st
import pandas as pd
import json
from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# --- PAGE SETUP ---
st.set_page_config(page_title="The Receipt Graveyard", page_icon="🧾", layout="wide")

# --- 1. SAFE DATA STRUCTURES (INR BASE) ---
class LineItem(BaseModel):
    description: str = Field(description="Name of the item")
    amount: float = Field(description="Price of the item")
    category: str = Field(description="Must be one of: Food, Alcohol, Lodging, Transport, Office Supplies, Other")

class ExtractedReceipt(BaseModel):
    merchant_name: str = Field(description="Store, restaurant, or vendor name")
    transaction_date: str = Field(description="YYYY-MM-DD format. Convert DD/MM/YYYY to YYYY-MM-DD. If missing on bill, return UNKNOWN")
    currency: str = Field(description="3-letter code e.g. INR, USD, EUR, GBP, AED")
    subtotal: float = Field(description="Subtotal before GST/tax and tip/service charge. If not shown, put 0.0")
    tax: float = Field(description="Total GST (CGST + SGST) or tax amount. If not shown, put 0.0")
    tip: float = Field(description="Tip or Service Charge amount. If not shown, put 0.0")
    total_printed: float = Field(description="Final total printed on the receipt in original currency. If missing, put 0.0")
    total_inr: float = Field(description="Total converted to Indian Rupees (INR). If already INR, keep same. Use ~84 INR for 1 USD, ~90 INR for 1 EUR.")
    is_itemized: bool = Field(description="True if individual items are listed, False if only final card/UPI slip total is shown")
    handwritten_modifications_detected: bool = Field(description="True if numbers look altered or overwritten by hand")
    line_items: List[LineItem]

class AuditDecision(BaseModel):
    status: str = Field(description="Must be one of: APPROVED, PARTIAL_APPROVAL, FLAGGED_FOR_REVIEW, REJECTED")
    reimbursable_amount_inr: float = Field(description="Final INR (₹) amount approved for reimbursement")
    requires_manager_signoff: bool = Field(description="True if bill exceeds the manager approval threshold or shows suspicious patterns")
    violations: List[str] = Field(description="List of policy, GST, math, or time-pattern violations found")
    fraud_risk_score: int = Field(description="Score from 1 (safe) to 100 (high fraud/policy risk)")
    employee_message: str = Field(description="Polite 1-sentence note to the employee explaining their reimbursement amount")
    finance_reasoning: str = Field(description="Strict forensic explanation for the finance team in INR (₹)")

# --- 2. SESSION STATE MEMORY (SHARED DATABASE ACROSS ROLES) ---
if "audit_history" not in st.session_state:
    st.session_state.audit_history = []

if "policy_text" not in st.session_state:
    st.session_state.policy_text = """1. CONTEXT & CITY DAILY LIMITS (INR):
- Home Office Meals: Max ₹500/day.
- Business Travel - Tier 1 Metro (Mumbai, Bengaluru, Delhi NCR): Max ₹2,500/day.
- Business Travel - Tier 2 Cities (Pune, Jaipur, Kochi): Max ₹1,500/day.
- Office Supplies: Max ₹5,000/month per employee.
2. NON-REIMBURSABLE ITEMS:
- Alcohol, hookah, mini-bar, tobacco, and fines are NEVER paid. Deduct them and issue PARTIAL_APPROVAL.
3. APPROVAL THRESHOLDS & STRUCTURING:
- Any single expense over ₹2,000 requires Manager Sign-Off (FLAGGED_FOR_REVIEW).
- Repeated expenses between ₹1,800 and ₹1,999 to dodge the ₹2,000 threshold are flagged as STRUCTURING.
4. REQUIRED DETAILS & MISSING INFO:
- Client meals over ₹1,500 require Client Name & Attendee Count.
- Receipts over ₹500 MUST be itemized and have a valid date/total."""

# --- 3. SIDEBAR: ROLE SWITCHER & SYSTEM SETUP ---
with st.sidebar:
    st.title("🧾 Receipt Graveyard")
    user_role = st.radio(
        "🔀 Switch Active Portal:",
        ["👤 Employee Portal", "🕵️‍♂️ Finance Reviewer Portal"],
        help="Switch between the Employee submitting bills and the Finance Auditor reviewing them."
    )
    st.divider()
    
    st.subheader("⚙️ AI Engine Setup")
    raw_api_key = st.text_input("Gemini API Key", type="password", help="Get a free key from aistudio.google.com")
    api_key = raw_api_key.strip() if raw_api_key else ""
    
    model_choice = st.selectbox(
        "AI Model",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    )
    demo_mode = st.checkbox("🛡️ Enable Demo Fallback Mode", help="Use if API key hits quota limits during live demo")

# ==============================================================================
# PORTAL 1: EMPLOYEE PORTAL (CANNOT EDIT POLICY OR SEE FRAUD SCORES)
# ==============================================================================
if user_role == "👤 Employee Portal":
    st.title("👤 Employee Expense Submission Portal")
    st.caption("Snap & upload your work receipts to get reimbursed fast. Policy checks run automatically.")
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.subheader("📤 Submit New Claim")
        employee_name = st.selectbox("Select Your Name", ["Aarav Sharma (Sales)", "Priya Nair (Engineering)", "Rohan Verma (VP Product)"])
        trip_context = st.selectbox("Where did this expense happen?", [
            "Home Office (Local)",
            "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)",
            "Business Trip - Tier 2 City (Pune / Jaipur / Kochi)"
        ])
        client_info = st.text_input("Client Name & Attendee Count (If Client Meal)", placeholder="e.g., Infosys Team - 4 Attendees")
        uploaded_files = st.file_uploader("Upload Receipt Image(s) (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        
        with st.expander("📖 View Company Expense Policy (Read-Only)"):
            st.markdown(f"```text\n{st.session_state.policy_text}\n```")
            st.caption("🔒 Only the Finance Team can modify company policy rules.")
            
        submit_btn = st.button("🚀 Submit for Reimbursement", type="primary", use_container_width=True)

    # PROCESS RECEIPTS WHEN EMPLOYEE SUBMITS
    if submit_btn:
        if not api_key and not demo_mode:
            st.error("⚠️ Please enter the Gemini API Key in the left sidebar (or turn on Demo Fallback Mode)!")
        elif not uploaded_files:
            st.warning("⚠️ Please attach at least one receipt image!")
        else:
            for uploaded_file in uploaded_files:
                with st.spinner(f"Processing your receipt ({uploaded_file.name})..."):
                    image_bytes = uploaded_file.read()
                    mime_type = uploaded_file.type or "image/jpeg"
                    
                    try:
                        if demo_mode:
                            receipt = ExtractedReceipt(
                                merchant_name="Toit Brewpub, Indiranagar",
                                transaction_date="2026-10-15",
                                currency="INR",
                                subtotal=2250.00,
                                tax=112.50,
                                tip=225.00,
                                total_printed=2587.50,
                                total_inr=2587.50,
                                is_itemized=True,
                                handwritten_modifications_detected=False,
                                line_items=[
                                    LineItem(description="Wood Fired Margherita & Chicken", amount=1000.00, category="Food"),
                                    LineItem(description="Tintin Witbier & Jameson Whiskey", amount=1250.00, category="Alcohol")
                                ]
                            )
                        else:
                            client = genai.Client(api_key=api_key)
                            extract_prompt = """
                            You are an Indian corporate forensic accountant. Extract all receipt details accurately, even if rotated, faded, cropped, or handwritten.
                            Convert DD/MM/YYYY dates to YYYY-MM-DD. If date is missing, output UNKNOWN.
                            Combine CGST and SGST into 'tax'. Put Service Charge into 'tip'.
                            Separate Alcohol line items from Food. Check if numbers look altered by hand.
                            Convert foreign currencies (USD, EUR, AED, etc.) into Indian Rupees (INR) in 'total_inr'.
                            """
                            ext_resp = client.models.generate_content(
                                model=model_choice,
                                contents=[
                                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                                    extract_prompt
                                ],
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=ExtractedReceipt,
                                    temperature=0.1
                                )
                            )
                            receipt = ExtractedReceipt.model_validate_json(ext_resp.text)
                        
                        # Deterministic Hard Checks
                        hard_flags = []
                        if receipt.transaction_date == "UNKNOWN":
                            hard_flags.append("MISSING_DATE: Receipt is missing a valid transaction date.")
                        if receipt.total_printed <= 0:
                            hard_flags.append("MISSING_TOTAL: Final total is missing or unreadable.")
                        if receipt.subtotal > 0:
                            calc_total = round(receipt.subtotal + receipt.tax + receipt.tip, 2)
                            if abs(calc_total - receipt.total_printed) > 1.00:
                                hard_flags.append(f"MATH_MISMATCH: Printed Total (₹{receipt.total_printed}) != Subtotal+GST+Tip (₹{calc_total})")
                        if receipt.handwritten_modifications_detected:
                            hard_flags.append("SUSPICIOUS_INK: Handwritten alterations detected on bill.")
                        
                        daily_spend_so_far = 0.0
                        monthly_spend_so_far = 0.0
                        just_under_limit_count = 0
                        
                        for past in st.session_state.audit_history:
                            if past["employee"] == employee_name:
                                monthly_spend_so_far += past["reimbursed_inr"]
                                if 1800.0 <= past["total_inr"] < 2000.0:
                                    just_under_limit_count += 1
                                if past["date"] == receipt.transaction_date:
                                    daily_spend_so_far += past["reimbursed_inr"]
                                    if abs(past["total_inr"] - receipt.total_inr) < 5.00:
                                        hard_flags.append(f"DUPLICATE_DETECTED: Matches earlier bill from {past['merchant']} (₹{past['total_inr']})")
                        
                        if 1800.0 <= receipt.total_inr < 2000.0 and just_under_limit_count >= 1:
                            hard_flags.append(f"PATTERN_ALERT (STRUCTURING): {just_under_limit_count + 1} bills submitted just under ₹2,000 threshold.")
                        
                        if demo_mode:
                            decision = AuditDecision(
                                status="PARTIAL_APPROVAL",
                                reimbursable_amount_inr=1175.00,
                                requires_manager_signoff=True,
                                violations=[
                                    "NON_REIMBURSABLE_ALCOHOL: ₹1,250.00 deducted for Beer & Whiskey",
                                    "MANAGER_SIGNOFF_REQUIRED: Original bill exceeds ₹2,000 threshold"
                                ],
                                fraud_risk_score=65,
                                employee_message="Your food items (₹1,175 incl. tax/tip) were approved, but ₹1,250 for alcohol was deducted per company policy.",
                                finance_reasoning="Deducted ₹1,250 for 2x Witbier and 1x Whiskey. Flagged for manager review as gross bill exceeded ₹2,000."
                            )
                        else:
                            audit_prompt = f"""
                            Evaluate this receipt against the Company Policy in Indian Rupees (₹ INR).
                            POLICY: {st.session_state.policy_text}
                            CONTEXT: Employee={employee_name}, Location={trip_context}, ClientInfo='{client_info}'
                            TIME & ACCUMULATION DATA:
                            - Approved spend on {receipt.transaction_date} BEFORE this bill: ₹{daily_spend_so_far}
                            - Cumulative monthly spend BEFORE this bill: ₹{monthly_spend_so_far}
                            EXTRACTED RECEIPT: {receipt.model_dump_json()}
                            AUTOMATED SYSTEM FLAGS: {hard_flags}
                            
                            Status MUST be one of: APPROVED, PARTIAL_APPROVAL, FLAGGED_FOR_REVIEW, REJECTED.
                            - Deduct non-reimbursable items (like Alcohol) from reimbursable_amount_inr and mark PARTIAL_APPROVAL.
                            - If daily or monthly limit in INR is exceeded when combined with prior spend, cap reimbursement or reject.
                            - If DUPLICATE_DETECTED or MATH_MISMATCH exists, mark REJECTED or FLAGGED_FOR_REVIEW.
                            """
                            aud_resp = client.models.generate_content(
                                model=model_choice,
                                contents=audit_prompt,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=AuditDecision,
                                    temperature=0.0
                                )
                            )
                            decision = AuditDecision.model_validate_json(aud_resp.text)
                        
                        valid_statuses = ["APPROVED", "PARTIAL_APPROVAL", "FLAGGED_FOR_REVIEW", "REJECTED"]
                        clean_status = decision.status if decision.status in valid_statuses else "FLAGGED_FOR_REVIEW"
                        
                        st.session_state.audit_history.append({
                            "id": len(st.session_state.audit_history) + 1,
                            "filename": uploaded_file.name,
                            "employee": employee_name,
                            "context": trip_context,
                            "date": receipt.transaction_date,
                            "merchant": receipt.merchant_name,
                            "orig_currency": receipt.currency,
                            "total_inr": round(receipt.total_inr, 2),
                            "reimbursed_inr": round(decision.reimbursable_amount_inr, 2),
                            "mgr_signoff": "Yes ⚠️" if decision.requires_manager_signoff else "No",
                            "status": clean_status,
                            "risk_score": decision.fraud_risk_score,
                            "violations": ", ".join(decision.violations + hard_flags),
                            "employee_message": decision.employee_message,
                            "finance_reasoning": decision.finance_reasoning,
                            "raw_receipt": receipt.model_dump(),
                            "image_bytes": image_bytes
                        })
                        st.success(f"✅ Submitted `{uploaded_file.name}`!")
                    except Exception as e:
                        st.error(f"🚨 **Error:** `{str(e)}` — Try enabling Demo Fallback Mode in the sidebar!")

    # EMPLOYEE PERSONAL TRACKER (ONLY SHOWS THE SELECTED EMPLOYEE'S CLAIMS, NO FRAUD SCORES)
    with col2:
        st.subheader(f"📋 My Reimbursement Status ({employee_name.split(' ')[0]})")
        my_claims = [c for c in st.session_state.audit_history if c["employee"] == employee_name]
        
        if not my_claims:
            st.info("You haven't submitted any receipts yet this month.")
        else:
            total_claimed = sum(c["total_inr"] for c in my_claims)
            total_approved = sum(c["reimbursed_inr"] for c in my_claims if c["status"] in ["APPROVED", "PARTIAL_APPROVAL"])
            m1, m2 = st.columns(2)
            m1.metric("Total Claimed This Month", f"₹{total_claimed:,.2f}")
            m2.metric("Approved for Payout", f"₹{total_approved:,.2f}")
            
            for item in reversed(my_claims):
                badge = {"APPROVED": "🟢 Approved", "PARTIAL_APPROVAL": "🟡 Partially Approved", "FLAGGED_FOR_REVIEW": "🟠 Pending Finance Review", "REJECTED": "🔴 Not Eligible"}[item["status"]]
                with st.container(border=True):
                    st.markdown(f"**{badge}** — **{item['merchant']}** (`{item['date']}`)")
                    st.markdown(f"Claimed: `₹{item['total_inr']:,.2f}` ➡️ **Payout: `₹{item['reimbursed_inr']:,.2f}`**")
                    st.caption(f"💬 **Note:** {item['employee_message']}")

# ==============================================================================
# PORTAL 2: FINANCE REVIEWER PORTAL (EDIT POLICY, FRAUD ALERTS, MANUAL OVERRIDE)
# ==============================================================================
elif user_role == "🕵️‍♂️ Finance Reviewer Portal":
    st.title("🕵️‍♂️ Finance Reviewer & Policy Control Center")
    
    # Simple PIN check for the hackathon demo
    pin = st.sidebar.text_input("🔒 Finance Admin PIN (Default: 1234)", value="1234", type="password")
    if pin != "1234":
        st.error("🔒 Access Denied. Please enter the Finance Admin PIN (`1234`) in the sidebar.")
        st.stop()
        
    tab1, tab2, tab3 = st.tabs(["🚨 Audit Queue & Fraud Alerts", "📜 Edit Company Policy (Admin Only)", "📊 Monthly Ledger & CSV Export"])
    
    # TAB 1: AUDIT QUEUE WITH MANUAL OVERRIDES
    with tab1:
        if not st.session_state.audit_history:
            st.info("No employee receipts in the queue yet. Switch to the Employee Portal to upload some!")
        else:
            # Top KPIs for Finance
            total_bills = len(st.session_state.audit_history)
            flagged_bills = sum(1 for x in st.session_state.audit_history if x["status"] in ["FLAGGED_FOR_REVIEW", "REJECTED"] or x["risk_score"] >= 60)
            saved_inr = sum(x["total_inr"] - x["reimbursed_inr"] for x in st.session_state.audit_history)
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Receipts Audited", total_bills)
            k2.metric("Flagged / High-Risk Bills", flagged_bills)
            k3.metric("₹ INR Saved by AI Policy Checks", f"₹{saved_inr:,.2f}")
            st.divider()
            
            for idx, item in enumerate(reversed(st.session_state.audit_history)):
                real_idx = len(st.session_state.audit_history) - 1 - idx
                color_map = {"APPROVED": "🟢", "PARTIAL_APPROVAL": "🟡", "FLAGGED_FOR_REVIEW": "🟠", "REJECTED": "🔴"}
                color = color_map.get(item["status"], "🟠")
                
                with st.expander(f"{color} [{item['status']}] {item['employee']} — {item['merchant']} (₹{item['total_inr']:,.2f}) | Fraud Risk: {item['risk_score']}/100", expanded=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.image(item["image_bytes"], caption=item["filename"], use_container_width=True)
                    with c2:
                        st.markdown(f"**Context:** `{item['context']}` | **Date:** `{item['date']}` | **Mgr Sign-Off:** `{item['mgr_signoff']}`")
                        st.markdown(f"**Claimed:** `₹{item['total_inr']:,.2f}` ➡️ **AI Approved Payout:** `₹{item['reimbursed_inr']:,.2f}`")
                        st.write(f"**🕵️‍♂️ Forensic Audit Note:** {item['finance_reasoning']}")
                        if item["violations"]:
                            st.error(f"**Triggered Rule Violations:** {item['violations']}")
                        
                        # FINANCE MANUAL OVERRIDE BUTTONS
                        b1, b2, b3 = st.columns(3)
                        if b1.button("✅ Force Approve Full", key=f"app_{item['id']}"):
                            st.session_state.audit_history[real_idx]["status"] = "APPROVED"
                            st.session_state.audit_history[real_idx]["reimbursed_inr"] = item["total_inr"]
                            st.rerun()
                        if b2.button("❌ Force Reject (₹0)", key=f"rej_{item['id']}"):
                            st.session_state.audit_history[real_idx]["status"] = "REJECTED"
                            st.session_state.audit_history[real_idx]["reimbursed_inr"] = 0.0
                            st.rerun()
                        with b3.popover("🔍 Inspect Raw JSON"):
                            st.json(item["raw_receipt"])

    # TAB 2: EDITABLE POLICY ENGINE (LOCKED TO FINANCE ONLY)
    with tab2:
        st.subheader("📜 Master Company Expense Policy (₹ INR)")
        st.caption("Changes saved here immediately govern all future employee submissions.")
        new_policy = st.text_area("Edit Active Policy Rules:", value=st.session_state.policy_text, height=320)
        col_a, col_b = st.columns([1, 1])
        if col_a.button("💾 Save Updated Policy Rules", type="primary"):
            st.session_state.policy_text = new_policy
            st.success("✅ Company Expense Policy updated! All new employee submissions will be audited against these rules.")
        if col_b.button("🗑️ Clear All Monthly Receipts"):
            st.session_state.audit_history = []
            st.rerun()

    # TAB 3: MONTHLY LEDGER & CSV DOWNLOAD FOR JUDGES
    with tab3:
        st.subheader("📅 Full Monthly Expense Ledger & Pattern Analysis")
        if not st.session_state.audit_history:
            st.info("No data to export yet.")
        else:
            df = pd.DataFrame(st.session_state.audit_history).drop(columns=["raw_receipt", "image_bytes"])
            st.dataframe(df, use_container_width=True)
            
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Final Audit Report (CSV)",
                data=csv_data,
                file_name="monthly_expense_audit_inr.csv",
                mime="text/csv",
                type="primary"
            )
