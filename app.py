import streamlit as st
import pandas as pd
import json
from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# --- PAGE SETUP ---
st.set_page_config(page_title="The Receipt Graveyard Auditor (INR)", page_icon="🧾", layout="wide")
st.title("🧾 The Receipt Graveyard: AI Expense Auditor (🇮🇳 INR Edition)")
st.caption("Upload messy Indian & international receipts, catch bad GST/math & duplicates, and auto-enforce company policy in ₹ INR.")

# --- 1. SAFE DATA STRUCTURES (INR BASE) ---
class LineItem(BaseModel):
    description: str = Field(description="Name of the item")
    amount: float = Field(description="Price of the item")
    category: str = Field(description="Must be one of: Food, Alcohol, Lodging, Transport, Office Supplies, Other")

class ExtractedReceipt(BaseModel):
    merchant_name: str = Field(description="Store, restaurant, or vendor name (e.g., Zomato, Uber India, Taj Hotel)")
    transaction_date: str = Field(description="YYYY-MM-DD format. Convert DD/MM/YYYY to YYYY-MM-DD. If missing, return UNKNOWN")
    currency: str = Field(description="3-letter code e.g. INR, USD, EUR, GBP, AED")
    subtotal: float = Field(description="Subtotal before GST/tax and tip/service charge. If not shown, put 0.0")
    tax: float = Field(description="Total GST (CGST + SGST) or tax amount. If not shown, put 0.0")
    tip: float = Field(description="Tip or Service Charge amount. If not shown, put 0.0")
    total_printed: float = Field(description="Final total printed on the receipt in original currency")
    total_inr: float = Field(description="Total converted to Indian Rupees (INR). If already INR, keep same. Use ~84 INR for 1 USD, ~90 INR for 1 EUR.")
    is_itemized: bool = Field(description="True if individual items are listed, False if only final card/UPI slip total is shown")
    handwritten_modifications_detected: bool = Field(description="True if numbers look altered or overwritten by hand")
    line_items: List[LineItem]

class AuditDecision(BaseModel):
    status: str = Field(description="Must be one of: APPROVED, PARTIAL_APPROVAL, FLAGGED_FOR_REVIEW, REJECTED")
    reimbursable_amount_inr: float = Field(description="Final INR (₹) amount approved for reimbursement")
    violations: List[str] = Field(description="List of policy, GST, or math violations found")
    fraud_risk_score: int = Field(description="Score from 1 (safe) to 100 (high fraud/policy risk)")
    reasoning_summary: str = Field(description="Clear 1-2 sentence explanation for the finance team in INR (₹)")

# --- 2. SESSION MEMORY ---
if "audit_history" not in st.session_state:
    st.session_state.audit_history = []

# --- 3. SIDEBAR: API KEY, MODEL CHOICE & EDITABLE POLICY ---
with st.sidebar:
    st.header("🔑 1. Setup")
    raw_api_key = st.text_input("Paste Gemini API Key", type="password", help="Get a free key from aistudio.google.com")
    api_key = raw_api_key.strip() if raw_api_key else ""
    
    model_choice = st.selectbox(
        "AI Model",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
        help="If one model gives a quota error, switch to another!"
    )
    
    demo_mode = st.checkbox("🛡️ Enable Demo Fallback Mode (Use if API key has quota/billing issues)")
    
    st.header("📜 2. Company Policy (₹ INR)")
    default_policy = """1. DAILY MEAL CAPS (INR):
- Home Office Meals: Max ₹500/day.
- Business Travel - Tier 1 Metro (Mumbai, Bengaluru, Delhi NCR, Hyderabad): Max ₹2,500/day.
- Business Travel - Tier 2 Cities (Pune, Jaipur, Ahmedabad, etc.): Max ₹1,500/day.
2. FORBIDDEN ITEMS:
- Alcohol, hookah, mini-bar, tobacco, and traffic challans/fines are strictly NON-REIMBURSABLE. Deduct them from the total and issue a PARTIAL_APPROVAL.
3. RECEIPT & GST RULES:
- Bills over ₹500 MUST be itemized tax invoices (plain UPI screenshots or Paytm/POS card slips alone are REJECTED).
- Tips / Service Charge cannot exceed 10% of the subtotal.
4. CLIENT ENTERTAINMENT:
- Requires Client Name & Attendee Count if the bill exceeds ₹3,000."""
    
    policy_text = st.text_area("Edit Policy Rules (Paste Hackathon Rules Here):", value=default_policy, height=260)
    
    if st.button("🗑️ Reset Monthly History"):
        st.session_state.audit_history = []
        st.rerun()

# --- 4. MAIN SUBMISSION FORM ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📤 Submit Employee Receipt(s)")
    employee_name = st.selectbox("Employee Name", ["Aarav Sharma (Sales)", "Priya Nair (Engineering)", "Rohan Verma (VP Product)"])
    trip_context = st.selectbox("Context / Location", [
        "Home Office (Local)",
        "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)",
        "Business Trip - Tier 2 City (Pune / Jaipur / Kochi)"
    ])
    client_info = st.text_input("Client Name & Attendee Count (Optional)", placeholder="e.g., Infosys Team - 4 Attendees")
    uploaded_files = st.file_uploader("Upload Receipt Images (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    run_audit = st.button("🚀 Audit Receipts Now", type="primary", use_container_width=True)

# --- 5. AI PROCESSING ENGINE ---
if run_audit:
    if not api_key and not demo_mode:
        st.error("⚠️ Please paste your Gemini API Key in the left sidebar first (or check 'Enable Demo Fallback Mode')!")
    elif not uploaded_files:
        st.warning("⚠️ Please upload at least one receipt image!")
    else:
        for uploaded_file in uploaded_files:
            with st.spinner(f"Scanning & auditing {uploaded_file.name}..."):
                image_bytes = uploaded_file.read()
                mime_type = uploaded_file.type or "image/jpeg"
                
                try:
                    if demo_mode:
                        # Instant realistic Indian receipt simulation if API key is blocked/out of quota
                        receipt = ExtractedReceipt(
                            merchant_name="Toit Brewpub, Indiranagar",
                            transaction_date="2026-10-15",
                            currency="INR",
                            subtotal=1850.00,
                            tax=165.00,
                            tip=185.00,
                            total_printed=2500.00,
                            total_inr=2500.00,
                            is_itemized=True,
                            handwritten_modifications_detected=True,
                            line_items=[
                                LineItem(description="Wood Fired Pizza & Pasta", amount=1200.00, category="Food"),
                                LineItem(description="Tintin Witbier Craft Beer (x2)", amount=650.00, category="Alcohol")
                            ]
                        )
                    else:
                        client = genai.Client(api_key=api_key)
                        
                        # STEP A: Vision Extraction
                        extract_prompt = """
                        You are an Indian corporate forensic accountant. Extract all receipt details accurately, even if rotated, faded, or handwritten.
                        Note that Indian dates are usually DD/MM/YYYY — convert them to YYYY-MM-DD.
                        Combine CGST and SGST into the 'tax' field. Put Service Charge into 'tip'.
                        Separate Alcohol line items (beer, wine, liquor, cocktails) from Food.
                        Check if any numbers look altered by hand.
                        If the receipt is in a foreign currency (USD, EUR, AED, etc.), convert 'total_inr' to Indian Rupees (INR).
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
                    
                    # STEP B: Hard Math & Duplicate Checks (in INR)
                    hard_flags = []
                    if receipt.subtotal > 0:
                        calc_total = round(receipt.subtotal + receipt.tax + receipt.tip, 2)
                        if abs(calc_total - receipt.total_printed) > 1.00:
                            hard_flags.append(f"MATH_MISMATCH: Printed Total ({receipt.total_printed}) != Subtotal+GST+Tip ({calc_total})")
                    
                    if receipt.handwritten_modifications_detected:
                        hard_flags.append("SUSPICIOUS_INK: Handwritten alterations detected on bill.")
                    
                    daily_spend_so_far = 0.0
                    for past in st.session_state.audit_history:
                        if past["employee"] == employee_name and past["date"] == receipt.transaction_date:
                            daily_spend_so_far += past["reimbursed_inr"]
                            if abs(past["total_inr"] - receipt.total_inr) < 5.00:
                                hard_flags.append(f"DUPLICATE_DETECTED: Matches earlier bill from {past['merchant']} (₹{past['total_inr']})")
                    
                    # STEP C: Policy Audit Decision
                    if demo_mode:
                        decision = AuditDecision(
                            status="PARTIAL_APPROVAL",
                            reimbursable_amount_inr=1550.00,
                            violations=[
                                "NON_REIMBURSABLE_ALCOHOL: ₹650.00 deducted for Craft Beer",
                                "MATH_MISMATCH: Printed total ₹2,500 does not match ₹1,850 + ₹165 GST + ₹185 Tip (₹2,200)"
                            ],
                            fraud_risk_score=78,
                            reasoning_summary="Deducted ₹650 for alcohol (Craft Beer) per company policy and rejected ₹300 unverified handwritten addition to the final bill total."
                        )
                    else:
                        audit_prompt = f"""
                        Evaluate this receipt against the Company Policy in Indian Rupees (₹ INR).
                        POLICY: {policy_text}
                        CONTEXT: Employee={employee_name}, Location={trip_context}, ClientInfo='{client_info}'
                        Accumulated approved spend for this employee on {receipt.transaction_date} BEFORE this receipt: ₹{daily_spend_so_far}
                        EXTRACTED RECEIPT: {receipt.model_dump_json()}
                        SYSTEM FLAGS: {hard_flags}
                        
                        Status MUST be one of: APPROVED, PARTIAL_APPROVAL, FLAGGED_FOR_REVIEW, REJECTED.
                        If Alcohol or forbidden items exist, deduct them from reimbursable_amount_inr and mark PARTIAL_APPROVAL.
                        If daily limit in INR is exceeded when combined with accumulated spend, cap reimbursement or reject.
                        If DUPLICATE_DETECTED or MATH_MISMATCH exists, mark REJECTED or FLAGGED_FOR_REVIEW.
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
                        "filename": uploaded_file.name,
                        "employee": employee_name,
                        "date": receipt.transaction_date,
                        "merchant": receipt.merchant_name,
                        "orig_currency": receipt.currency,
                        "total_inr": round(receipt.total_inr, 2),
                        "reimbursed_inr": round(decision.reimbursable_amount_inr, 2),
                        "status": clean_status,
                        "risk_score": decision.fraud_risk_score,
                        "violations": ", ".join(decision.violations + hard_flags),
                        "reasoning": decision.reasoning_summary,
                        "raw_receipt": receipt.model_dump(),
                        "image_bytes": image_bytes
                    })

                except Exception as e:
                    st.error(f"🚨 **Exact API Error Details:** `{str(e)}`")
                    st.info("💡 **Quick Fix:** 1) Try switching the **AI Model** dropdown in the sidebar to `gemini-2.0-flash`. 2) Or check **'Enable Demo Fallback Mode'** in the sidebar to test the dashboard immediately!")

# --- 6. LIVE DASHBOARD DISPLAY ---
with col2:
    st.subheader("📊 Live Audit Feed (₹ INR)")
    if not st.session_state.audit_history:
        st.info("No receipts audited yet. Upload an image on the left to start!")
    else:
        for item in reversed(st.session_state.audit_history):
            color_map = {"APPROVED": "🟢", "PARTIAL_APPROVAL": "🟡", "FLAGGED_FOR_REVIEW": "🟠", "REJECTED": "🔴"}
            color = color_map.get(item["status"], "🟠")
            with st.expander(f"{color} {item['status']} | {item['merchant']} (₹{item['total_inr']:,.2f}) — {item['employee']}", expanded=True):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(item["image_bytes"], caption=item["filename"], use_container_width=True)
                with c2:
                    st.markdown(f"**Date:** `{item['date']}` | **Orig Currency:** `{item['orig_currency']}` | **Fraud Risk Score:** `{item['risk_score']}/100`")
                    st.markdown(f"**Claimed:** `₹{item['total_inr']:,.2f}` ➡️ **Reimbursable:** `₹{item['reimbursed_inr']:,.2f}`")
                    st.write(f"**AI Auditor Verdict:** {item['reasoning']}")
                    if item["violations"]:
                        st.error(f"**Flags/Violations:** {item['violations']}")
                    with st.popover("View Extracted Line Items & GST (JSON)"):
                        st.json(item["raw_receipt"])

# --- 7. MONTHLY SUMMARY TABLE ---
if st.session_state.audit_history:
    st.divider()
    st.subheader("📅 Monthly Expense Ledger (Accumulated ₹ INR Tracking)")
    df = pd.DataFrame(st.session_state.audit_history).drop(columns=["raw_receipt", "image_bytes"])
    st.dataframe(df, use_container_width=True)
