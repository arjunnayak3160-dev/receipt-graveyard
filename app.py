import streamlit as st
import pandas as pd
import json
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# --- PAGE SETUP ---
st.set_page_config(page_title="The Receipt Graveyard Auditor", page_icon="🧾", layout="wide")
st.title("🧾 The Receipt Graveyard: AI Expense Auditor")
st.caption("Upload messy receipts, catch bad math & duplicates, and auto-enforce company policy.")

# --- 1. DATA STRUCTURES (STRUCTURED AI OUTPUTS) ---
class LineItem(BaseModel):
    description: str
    amount: float
    category: Literal["Food", "Alcohol", "Lodging", "Transport", "Office Supplies", "Other"]

class ExtractedReceipt(BaseModel):
    merchant_name: str
    transaction_date: str = Field(description="YYYY-MM-DD format. If missing, return 'UNKNOWN'")
    currency: str = Field(description="3-letter code e.g. USD, EUR, GBP, INR")
    subtotal: Optional[float]
    tax: Optional[float]
    tip: Optional[float]
    total_printed: float
    total_usd: float = Field(description="Converted to USD using standard exchange rates")
    is_itemized: bool = Field(description="False if it only shows the final total without item details")
    handwritten_modifications_detected: bool
    line_items: List[LineItem]

class AuditDecision(BaseModel):
    status: Literal["APPROVED", "PARTIAL_APPROVAL", "FLAGGED_FOR_REVIEW", "REJECTED"]
    reimbursable_amount_usd: float
    violations: List[str]
    fraud_risk_score: int = Field(description="Score from 1 (safe) to 100 (high fraud/policy risk)")
    reasoning_summary: str

# --- 2. SESSION MEMORY (TRACKS SPENDING OVER THE MONTH) ---
if "audit_history" not in st.session_state:
    st.session_state.audit_history = []

# --- 3. SIDEBAR: API KEY & EDITABLE COMPANY POLICY ---
with st.sidebar:
    st.header("🔑 1. Setup")
    api_key = st.text_input("Paste Gemini API Key", type="password", help="Get a free key from aistudio.google.com")
    
    st.header("📜 2. Company Policy")
    default_policy = """1. MEAL CAPS:
- Home Office Meals: Max \$25/day.
- Business Travel Meals (Tier 1: NYC, SF, London): Max \$100/day.
- Business Travel Meals (Other Cities): Max \$60/day.
2. FORBIDDEN ITEMS:
- Alcohol, mini-bar, tobacco, and fines are strictly NON-REIMBURSABLE. Deduct them from the total and issue a PARTIAL_APPROVAL.
3. RECEIPT RULES:
- Meals over \$25 MUST be itemized (credit card slips alone are REJECTED).
- Tips cannot exceed 20% of the subtotal.
4. CLIENT MEALS:
- Require Client Name & Attendee Count if total exceeds \$75."""
    
    policy_text = st.text_area("Edit Policy Rules (Paste Hackathon Rules Here):", value=default_policy, height=280)
    
    if st.button("🗑️ Reset Monthly History"):
        st.session_state.audit_history = []
        st.rerun()

# --- 4. MAIN SUBMISSION FORM ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 Submit Employee Receipt(s)")
    employee_name = st.selectbox("Employee Name", ["Alice (Sales)", "Bob (Engineering)", "Charlie (Exec)"])
    trip_context = st.selectbox("Context / Location", [
        "Home Office (Local)",
        "Business Trip - Tier 1 City (NYC / SF / London)",
        "Business Trip - Standard City"
    ])
    client_info = st.text_input("Client Name & Attendee Count (Optional)", placeholder="e.g., Acme Corp - 3 Attendees")
    uploaded_files = st.file_uploader("Upload Receipt Images (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    run_audit = st.button("🚀 Audit Receipts Now", type="primary", use_container_width=True)

# --- 5. AI PROCESSING ENGINE ---
if run_audit:
    if not api_key:
        st.error("⚠️ Please paste your Gemini API Key in the left sidebar first!")
    elif not uploaded_files:
        st.warning("⚠️ Please upload at least one receipt image!")
    else:
        client = genai.Client(api_key=api_key)
        
        for uploaded_file in uploaded_files:
            with st.spinner(f"Scanning & auditing {uploaded_file.name}..."):
                image_bytes = uploaded_file.read()
                mime_type = uploaded_file.type
                
                # STEP A: Vision Extraction
                extract_prompt = """
                Extract all receipt details accurately, even if rotated, faded, or handwritten.
                Separate Alcohol line items from Food. Check if numbers look altered by hand.
                """
                ext_resp = client.models.generate_content(
                    model="gemini-2.5-flash",
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
                
                # STEP B: Hard Math & Duplicate Checks
                hard_flags = []
                if receipt.subtotal is not None and receipt.tax is not None:
                    calc_total = round(receipt.subtotal + receipt.tax + (receipt.tip or 0.0), 2)
                    if abs(calc_total - receipt.total_printed) > 0.05:
                        hard_flags.append(f"MATH_MISMATCH: Printed ({receipt.total_printed}) != Sum ({calc_total})")
                
                if receipt.handwritten_modifications_detected:
                    hard_flags.append("SUSPICIOUS_INK: Handwritten alterations detected.")
                
                # Check duplicates & daily accumulated spend for this employee
                daily_spend_so_far = 0.0
                for past in st.session_state.audit_history:
                    if past["employee"] == employee_name and past["date"] == receipt.transaction_date:
                        daily_spend_so_far += past["reimbursed_usd"]
                        if abs(past["total_usd"] - receipt.total_usd) < 1.00:
                            hard_flags.append(f"DUPLICATE_DETECTED: Matches earlier receipt from {past['merchant']} (\${past['total_usd']})")
                
                # STEP C: Policy Audit Decision
                audit_prompt = f"""
                Evaluate this receipt against the Company Policy.
                POLICY: {policy_text}
                CONTEXT: Employee={employee_name}, Location={trip_context}, ClientInfo='{client_info}'
                Accumulated approved spend for this employee on {receipt.transaction_date} BEFORE this receipt: \${daily_spend_so_far}
                EXTRACTED RECEIPT: {receipt.model_dump_json()}
                SYSTEM FLAGS: {hard_flags}
                
                If Alcohol or forbidden items exist, deduct them and mark PARTIAL_APPROVAL.
                If daily limit is exceeded when combined with accumulated spend, cap reimbursement or reject.
                If DUPLICATE_DETECTED or MATH_MISMATCH exists, mark REJECTED or FLAGGED_FOR_REVIEW.
                """
                aud_resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=audit_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=AuditDecision,
                        temperature=0.0
                    )
                )
                decision = AuditDecision.model_validate_json(aud_resp.text)
                
                # Save to monthly history
                st.session_state.audit_history.append({
                    "filename": uploaded_file.name,
                    "employee": employee_name,
                    "date": receipt.transaction_date,
                    "merchant": receipt.merchant_name,
                    "total_usd": round(receipt.total_usd, 2),
                    "reimbursed_usd": round(decision.reimbursable_amount_usd, 2),
                    "status": decision.status,
                    "risk_score": decision.fraud_risk_score,
                    "violations": ", ".join(decision.violations + hard_flags),
                    "reasoning": decision.reasoning_summary,
                    "raw_receipt": receipt.model_dump(),
                    "image_bytes": image_bytes
                })

# --- 6. LIVE DASHBOARD DISPLAY ---
with col2:
    st.subheader("📊 Live Audit Feed")
    if not st.session_state.audit_history:
        st.info("No receipts audited yet. Upload an image on the left to start!")
    else:
        for item in reversed(st.session_state.audit_history):
            color = {"APPROVED": "🟢", "PARTIAL_APPROVAL": "🟡", "FLAGGED_FOR_REVIEW": "🟠", "REJECTED": "🔴"}[item["status"]]
            with st.expander(f"{color} {item['status']} | {item['merchant']} (\${item['total_usd']}) — {item['employee']}", expanded=True):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(item["image_bytes"], caption=item["filename"], use_container_width=True)
                with c2:
                    st.markdown(f"**Date:** `{item['date']}` | **Fraud Risk Score:** `{item['risk_score']}/100`")
                    st.markdown(f"**Claimed:** `${item['total_usd']}` ➡️ **Reimbursable:** `${item['reimbursed_usd']}`")
                    st.write(f"**AI Auditor Verdict:** {item['reasoning']}")
                    if item["violations"]:
                        st.error(f"**Flags/Violations:** {item['violations']}")
                    with st.popover("View Extracted Line Items (JSON)"):
                        st.json(item["raw_receipt"])

# --- 7. MONTHLY SUMMARY TABLE ---
if st.session_state.audit_history:
    st.divider()
    st.subheader("📅 Monthly Expense Ledger (Accumulated Tracking)")
    df = pd.DataFrame(st.session_state.audit_history).drop(columns=["raw_receipt", "image_bytes"])
    st.dataframe(df, use_container_width=True)