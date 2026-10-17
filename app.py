import streamlit as st
import pandas as pd
import re
from datetime import datetime
from PIL import Image
import io

# Try loading the free offline OCR engine
try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# --- PAGE SETUP ---
st.set_page_config(page_title="The Receipt Graveyard (Offline OCR + Rule Engine)", page_icon="🧾", layout="wide")

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
            "home_cap": 500.0,
            "tier1_cap": 2500.0,
            "tier2_cap": 1500.0,
            "mgr_threshold": 2000.0,
            "client_threshold": 1500.0,
            "max_tip_pct": 10.0,
            "banned_categories": ["Alcohol", "Tobacco", "Mini-Bar", "Fines"]
        }
    ]

active_policy = st.session_state.policy_versions[-1]


# --- 2. REAL OFFLINE OCR PARSER (NO API KEY NEEDED) ---
def parse_receipt_from_image_bytes(image_bytes: bytes, filename: str, custom_override: dict = None) -> dict:
    """Reads actual text from the uploaded receipt image using offline RapidOCR and parses numbers/items."""
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

    # 1. Detect Merchant Name
    merchant_name = "Your Restaurant" if "YOUR RESTAURANT" in text_upper else "Uploaded Receipt Vendor"
    for l in lines[:4]:
        if len(l) > 3 and not any(k in l.upper() for k in ["RECEIPT", "INVOICE", "PAYMENT", "DATE", "GSTIN"]):
            merchant_name = l.title()
            break

    # 2. Detect Date
    date_found = "2026-10-15"
    m_dmy = re.search(r"(\d{2})[/-](\d{2})[/-](20\d{2})", raw_text)
    m_text_date = re.search(r"(\d{2})\s+([A-Za-z]{3})\s+(20\d{2})", raw_text)
    if m_dmy:
        date_found = f"{m_dmy.group(3)}-{m_dmy.group(2)}-{m_dmy.group(1)}"
    elif m_text_date:
        # e.g., 17 Jun 2026
        from datetime import datetime
        try:
            dt = datetime.strptime(f"{m_text_date.group(1)} {m_text_date.group(2)} {m_text_date.group(3)}", "%d %b %Y")
            date_found = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # 3. Extract Numbers (Subtotal, Tax, Total)
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
    
    # Look for TOTAL specifically (accounting for clean restaurant bill labels)
    total_printed = extract_amount_near(["GRAND TOTAL", "TOTAL PAID", "AMOUNT PAID", "TOTAL AMOUNT", "TOTAL"], raw_text)

    # Fallback: grab all monetary floats on the page
    all_floats = [float(x.replace(",", "")) for x in re.findall(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b", raw_text)]
    if subtotal == 0.0 and len(all_floats) >= 2:
        subtotal = all_floats[-4] if len(all_floats) >= 4 else all_floats[0]
    if total_printed == 0.0 and all_floats:
        total_printed = max(all_floats)

    # If subtotal exists but tax/total wasn't explicitly caught, estimate standard GST (e.g. 5% total tax)
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
        "ocr_raw_text": raw_text,
        "line_items": [{"description": "Itemized Restaurant Bill", "amount": subtotal if subtotal > 0 else total_printed, "category": "Food"}]
    }
    # 4. Extract Numbers (Subtotal, Tax/GST, Tip/Service Charge, Grand Total)
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

    subtotal = extract_amount_near(["SUBTOTAL", "BASE FARE", "SUB TOTAL"], raw_text)
    cgst = extract_amount_near(["CGST"], raw_text)
    sgst = extract_amount_near(["SGST"], raw_text)
    tax = cgst + sgst if (cgst + sgst) > 0 else extract_amount_near(["GST", "TAX", "TOLL"], raw_text)
    tip = extract_amount_near(["SERVICE CHARGE", "TIP", "WAITING"], raw_text)
    total_printed = extract_amount_near(["GRAND TOTAL", "TOTAL PAID", "AMOUNT PAID", "TOTAL"], raw_text)

    # Fallback: grab largest decimal number on the receipt if "TOTAL" label wasn't matched
    all_Floats = [float(x.replace(",", "")) for x in re.findall(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b", raw_text)]
    if total_printed == 0.0 and all_Floats:
        total_printed = max(all_Floats)

    # 5. Detect Alcohol / Forbidden Items from OCR text
    alcohol_keywords = ["BEER", "WITBIER", "WHISKEY", "JAMESON", "WINE", "VODKA", "GIN", "RUM", "COCKTAIL", "LIQUOR", "ALCOHOL", "IPA", "DRAUGHT"]
    line_items = []
    alcohol_amt = 0.0

    for idx, l in enumerate(lines):
        l_up = l.upper()
        if any(ak in l_up for ak in alcohol_keywords):
            # Look for price on same line or next line in OCR output
            SearchWindow = l + " " + (lines[idx + 1] if idx + 1 < len(lines) else "")
            prices = [float(x.replace(",", "")) for x in re.findall(r"\b\d{2,5}\.\d{2}\b", SearchWindow)]
            amt = prices[0] if prices else 500.0
            alcohol_amt += amt
            line_items.append({"description": l, "amount": amt, "category": "Alcohol"})

    food_amt = max(0.0, (subtotal if subtotal > 0 else total_printed) - alcohol_amt)
    if food_amt > 0:
        line_items.insert(0, {"description": "Food / Standard Bill Items", "amount": round(food_amt, 2), "category": "Food"})

    is_upi_or_slip = ("UPI" in text_upper or "UTR" in text_upper or "PAYMENT SUCCESSFUL" in text_upper) and subtotal == 0.0
    handwritten = (subtotal > 0 and abs((subtotal + tax + tip) - total_printed) > 1.0)

    return {
        "merchant_name": merchant_name,
        "transaction_date": date_found,
        "currency": currency,
        "fx_rate_to_inr": fx,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "tip": round(tip, 2),
        "total_printed": round(total_printed, 2),
        "is_itemized": not is_upi_or_slip,
        "handwritten_tampering": handwritten,
        "ocr_raw_text": raw_text if raw_text else "No OCR text found — use Custom Simulator to override values.",
        "line_items": line_items if line_items else [{"description": "Receipt Total", "amount": total_printed, "category": "Food"}]
    }


def run_deterministic_audit(receipt: dict, employee: str, context: str, client_info: str, policy: dict, history: list) -> dict:
    """100% Pure Python Rule Engine: Evaluates math, banned items, city caps, duplicates, and time structuring."""
    violations = []
    risk_score = 10
    fx = receipt.get("fx_rate_to_inr", 1.0)
    total_inr = round(receipt["total_printed"] * fx, 2)
    reimbursable_inr = total_inr

    if total_inr <= 0:
        violations.append("UNREADABLE_TOTAL: Could not detect a valid total amount on receipt.")
        return {
            "status": "FLAGGED_FOR_REVIEW", "total_inr": 0.0, "reimbursed_inr": 0.0, "requires_mgr": True,
            "violations": violations, "risk_score": 60,
            "employee_message": "We couldn't read the final total on this image. Sent to Finance for manual review.",
            "finance_reasoning": "OCR could not verify a positive total amount."
        }

    # 1. Hard Math Verification (Subtotal + GST + Tip == Total Printed)
    calc_total = round(receipt["subtotal"] + receipt["tax"] + receipt["tip"], 2)
    if receipt["subtotal"] > 0 and abs(calc_total - receipt["total_printed"]) > 1.0:
        violations.append(
            f"MATH_MISMATCH: Printed Total (₹{receipt['total_printed']}) != Subtotal+GST+Tip (₹{calc_total})"
        )
        risk_score += 65
        reimbursable_inr = 0.0

    # 2. Handwritten Tampering Check
    if receipt.get("handwritten_tampering"):
        violations.append("SUSPICIOUS_DISCREPANCY: Itemized components do not add up to the claimed total.")
        risk_score += 25

    # 3. Cross-Channel Duplicate Detection (Same Employee + Same Date + Similar Amount)
    for past in history:
        if past["employee"] == employee and past["date"] == receipt["transaction_date"]:
            if abs(past["total_inr"] - total_inr) < 5.0:
                violations.append(
                    f"DUPLICATE_DETECTED: Matches earlier ₹{past['total_inr']} claim at '{past['merchant']}' on {past['date']}."
                )
                risk_score = 95
                reimbursable_inr = 0.0

    # 4. Unitemized UPI / Card Slip Rule
    if total_inr > 500.0 and not receipt.get("is_itemized", True):
        violations.append("NON_ITEMIZED_RECEIPT: Plain UPI screenshot/slip over ₹500 without itemized GST invoice.")
        risk_score += 35
        reimbursable_inr = 0.0

    # 5. Forbidden Line Items Deduction (Alcohol, Tobacco, Mini-Bar, Fines)
    banned_total_inr = sum(
        item["amount"] * fx for item in receipt.get("line_items", [])
        if item["category"] in policy["banned_categories"]
    )
    if banned_total_inr > 0 and reimbursable_inr > 0:
        base_sub = (receipt["subtotal"] * fx) if receipt["subtotal"] > 0 else total_inr
        ratio_allowed = max(0.0, (base_sub - banned_total_inr) / base_sub) if base_sub > 0 else 0.0
        reimbursable_inr = round(total_inr * ratio_allowed, 2)
        deducted = round(total_inr - reimbursable_inr, 2)
        violations.append(f"NON_REIMBURSABLE_ALCOHOL: Deducted ₹{deducted:,.2f} (Alcohol + proportional GST/Service Charge).")
        risk_score += 30

    # 6. Context & City Daily Limit Accumulation
    if "Home Office" in context:
        daily_cap = policy["home_cap"]
    elif "Tier 1" in context:
        daily_cap = policy["tier1_cap"]
    else:
        daily_cap = policy["tier2_cap"]

    prior_daily_spend = sum(
        x["reimbursed_inr"] for x in history
        if x["employee"] == employee and x["date"] == receipt["transaction_date"]
    )
    if reimbursable_inr > 0 and (prior_daily_spend + reimbursable_inr) > daily_cap:
        allowed_remaining = max(0.0, round(daily_cap - prior_daily_spend, 2))
        violations.append(
            f"DAILY_CAP_EXCEEDED: Prior spend today (₹{prior_daily_spend}) + Claim (₹{reimbursable_inr}) exceeds {context} limit of ₹{daily_cap}/day. Capped at ₹{allowed_remaining}."
        )
        reimbursable_inr = allowed_remaining
        risk_score += 20

    # 7. Client Details Requirement
    if total_inr > policy["client_threshold"] and not client_info.strip():
        violations.append(f"MISSING_CLIENT_DETAILS: Bills over ₹{policy['client_threshold']} require Client Name & Attendee Count.")
        risk_score += 20

    # 8. Structuring Pattern Detection
    mgr_thresh = policy["mgr_threshold"]
    just_under_bills = sum(
        1 for x in history
        if x["employee"] == employee and (mgr_thresh * 0.9) <= x["total_inr"] < mgr_thresh
    )
    if (mgr_thresh * 0.9) <= total_inr < mgr_thresh and just_under_bills >= 1:
        violations.append(
            f"STRUCTURING_PATTERN_ALERT: {just_under_bills + 1} bills submitted between ₹{mgr_thresh*0.9:.0f}–₹{mgr_thresh-1:.0f} just below the ₹{mgr_thresh:.0f} sign-off limit."
        )
        risk_score += 40

    requires_mgr = total_inr > mgr_thresh or risk_score >= 60

    if reimbursable_inr == 0.0:
        status = "REJECTED"
    elif any("MISSING_CLIENT_DETAILS" in v or "STRUCTURING_PATTERN" in v for v in violations):
        status = "FLAGGED_FOR_REVIEW"
    elif reimbursable_inr < total_inr:
        status = "PARTIAL_APPROVAL"
    else:
        status = "APPROVED"

    risk_score = min(100, risk_score)

    if status == "APPROVED":
        emp_msg = f"Approved in full (₹{reimbursable_inr:,.2f}) under Policy {policy['version']}."
        fin_msg = f"Passed all math, duplicate, and {context} cap checks (₹{daily_cap}/day)."
    elif status == "PARTIAL_APPROVAL":
        emp_msg = f"Partially approved for ₹{reimbursable_inr:,.2f} (deducted ₹{total_inr - reimbursable_inr:,.2f} per policy)."
        fin_msg = f"Auto-deducted ₹{total_inr - reimbursable_inr:,.2f}. Triggers: {'; '.join(violations)}"
    elif status == "FLAGGED_FOR_REVIEW":
        emp_msg = f"Pending Finance/Manager review (Provisional: ₹{reimbursable_inr:,.2f})."
        fin_msg = f"Flagged for review. Triggers: {'; '.join(violations)}"
    else:
        emp_msg = "Rejected due to policy, duplicate, or math verification failure."
        fin_msg = f"Rejected (₹0 payout). Forensic triggers: {'; '.join(violations)}"

    return {
        "status": status,
        "total_inr": total_inr,
        "reimbursed_inr": reimbursable_inr,
        "requires_mgr": requires_mgr,
        "violations": violations,
        "risk_score": risk_score,
        "employee_message": emp_msg,
        "finance_reasoning": fin_msg
    }


# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🧾 Receipt Graveyard")
    st.success(f"🔍 **Offline OCR Engine:** {'Active ✅' if OCR_AVAILABLE else 'Simulator Mode'}")
    st.caption(f"🛡️ Active Policy: **{active_policy['version']}** (Eff: {active_policy['effective_date']})")

    user_role = st.radio("🔀 Switch Active Portal:", ["👤 Employee Portal", "🕵️‍♂️ Finance Reviewer Portal"])
    st.divider()

    st.subheader("🚀 Hackathon Demo Shortcuts")
    if st.button("📥 Load Full Month Dataset (5 Bills)", use_container_width=True):
        demo_bills = [
            ("toit_brewpub.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", {
                "merchant_name": "Toit Brewpub, Indiranagar", "transaction_date": "2026-10-15", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 2250.0, "tax": 112.50, "tip": 225.0, "total_printed": 2587.50, "is_itemized": True, "handwritten_tampering": False,
                "line_items": [{"description": "Pizza & Chicken", "amount": 1000.0, "category": "Food"}, {"description": "Witbier & Jameson Whiskey", "amount": 1250.0, "category": "Alcohol"}]
            }),
            ("upi_screenshot.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", {
                "merchant_name": "Toit Brewpub Bengaluru (UPI)", "transaction_date": "2026-10-15", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 0.0, "tax": 0.0, "tip": 0.0, "total_printed": 2587.50, "is_itemized": False, "handwritten_tampering": False,
                "line_items": [{"description": "Unitemized UPI Transfer", "amount": 2587.50, "category": "Food"}]
            }),
            ("mumbai_taxi.png", "Priya Nair (Engineering)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "", {
                "merchant_name": "Shree Sai Tours & Taxi", "transaction_date": "2026-10-16", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 650.0, "tax": 100.0, "tip": 50.0, "total_printed": 1800.0, "is_itemized": True, "handwritten_tampering": True,
                "line_items": [{"description": "Airport Taxi + Toll + Tip", "amount": 800.0, "category": "Transport"}]
            }),
            ("lunch_day1.png", "Rohan Verma (VP Product)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "TCS Team", {
                "merchant_name": "Social Offline, Koramangala", "transaction_date": "2026-10-18", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 1800.0, "tax": 150.0, "tip": 0.0, "total_printed": 1950.0, "is_itemized": True, "handwritten_tampering": False,
                "line_items": [{"description": "Team Lunch Platters", "amount": 1950.0, "category": "Food"}]
            }),
            ("lunch_day2.png", "Rohan Verma (VP Product)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Wipro Team", {
                "merchant_name": "Truffles, Indiranagar", "transaction_date": "2026-10-19", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 1820.0, "tax": 160.0, "tip": 0.0, "total_printed": 1980.0, "is_itemized": True, "handwritten_tampering": False,
                "line_items": [{"description": "Burgers & Coffee", "amount": 1980.0, "category": "Food"}]
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

    if st.button("🗑️ Reset All Data", use_container_width=True):
        st.session_state.ledger = []
        st.rerun()

# ==============================================================================
# PORTAL 1: EMPLOYEE PORTAL
# ==============================================================================
if user_role == "👤 Employee Portal":
    st.title("👤 Employee Expense Submission Portal")
    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.subheader("📤 Submit New Claim")
        employee_name = st.selectbox("Select Your Name", ["Aarav Sharma (Sales)", "Priya Nair (Engineering)", "Rohan Verma (VP Product)"])
        trip_context = st.selectbox("Where did this expense happen?", [
            "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)",
            "Home Office (Local)",
            "Business Trip - Tier 2 City (Pune / Jaipur / Kochi)"
        ])
        client_info = st.text_input("Client Name & Attendee Count (Required over ₹1,500)", placeholder="e.g., Infosys Team - 4 Attendees")
        uploaded_files = st.file_uploader("Upload Receipt Image(s) (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        with st.expander("🧪 Manual Override Simulator (Optional)"):
            use_custom = st.checkbox("Override OCR with custom numbers below")
            c_merch = st.text_input("Merchant Name", "Third Wave Coffee")
            c_date = st.text_input("Receipt Date (YYYY-MM-DD)", "2026-10-20")
            c_sub = st.number_input("Subtotal (₹)", value=1000.0)
            c_tax = st.number_input("GST / Tax (₹)", value=50.0)
            c_tip = st.number_input("Tip / Service Charge (₹)", value=50.0)
            c_tot = st.number_input("Printed Total on Bill (₹)", value=1100.0)
            c_alc = st.number_input("Of which Alcohol Amount (₹)", value=0.0)
            c_itemized = st.checkbox("Is Itemized Tax Invoice?", value=True)

        submit_btn = st.button("🚀 Submit for Reimbursement", type="primary", use_container_width=True)

    if submit_btn:
        if not uploaded_files and not use_custom:
            st.warning("⚠️ Please upload a receipt image first!")
        else:
            files_to_process = uploaded_files if uploaded_files else [None]
            for uf in files_to_process:
                with st.spinner("Scanning text from receipt image via offline OCR..."):
                    fname = uf.name if uf else "manual_entry.png"
                    img_bytes = uf.read() if uf else None

                    custom_dict = None
                    if use_custom:
                        items = [{"description": "Standard Items", "amount": max(0.0, c_sub - c_alc), "category": "Food"}]
                        if c_alc > 0:
                            items.append({"description": "Alcohol", "amount": c_alc, "category": "Alcohol"})
                        custom_dict = {
                            "merchant_name": c_merch, "transaction_date": c_date, "currency": "INR", "fx_rate_to_inr": 1.0,
                            "subtotal": c_sub, "tax": c_tax, "tip": c_tip, "total_printed": c_tot,
                            "is_itemized": c_itemized, "handwritten_tampering": abs((c_sub + c_tax + c_tip) - c_tot) > 1.0,
                            "line_items": items
                        }

                    rec = parse_receipt_from_image_bytes(img_bytes, fname, custom_dict)
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
                    st.success(f"✅ Scanned `{rec['merchant_name']}` (₹{res['total_inr']:,.2f})!")

    with col2:
        st.subheader(f"📋 My Reimbursement Status ({employee_name.split(' ')[0]})")
        my_claims = [c for c in st.session_state.ledger if c["employee"] == employee_name]
        if not my_claims:
            st.info("No receipts submitted yet.")
        else:
            for item in reversed(my_claims):
                badge = {"APPROVED": "🟢 Approved", "PARTIAL_APPROVAL": "🟡 Partially Approved", "FLAGGED_FOR_REVIEW": "🟠 Pending Review", "REJECTED": "🔴 Not Eligible"}.get(item["status"], "🟠")
                st.markdown(f"#### {badge} — {item['merchant']} (`{item['date']}`)")
                st.markdown(f"**Claimed:** `₹{item['total_inr']:,.2f}` ➡️ **Payout:** `₹{item['reimbursed_inr']:,.2f}` *(Policy `{item['policy_version']}`)*")
                st.info(f"💬 **Note:** {item['employee_message']}")
                st.divider()

# ==============================================================================
# PORTAL 2: FINANCE REVIEWER PORTAL
# ==============================================================================
elif user_role == "🕵️‍♂️ Finance Reviewer Portal":
    st.title("🕵️‍♂️ Finance Reviewer & Governance Center")
    pin = st.sidebar.text_input("🔒 Finance Admin PIN (Default: 1234)", value="1234", type="password")
    if pin != "1234":
        st.error("🔒 Access Denied.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["🚨 Audit Queue & Fraud Alerts", "🛡️ Policy Governance (Option C)", "📊 Monthly Ledger & CSV"])

    with tab1:
        if not st.session_state.ledger:
            st.info("No receipts yet.")
        else:
            for idx, item in enumerate(reversed(st.session_state.ledger)):
                real_idx = len(st.session_state.ledger) - 1 - idx
                color = {"APPROVED": "🟢", "PARTIAL_APPROVAL": "🟡", "FLAGGED_FOR_REVIEW": "🟠", "REJECTED": "🔴"}.get(item["status"], "🟠")
                with st.expander(f"{color} [{item['status']}] {item['employee']} — {item['merchant']} (₹{item['total_inr']:,.2f}) | Risk: {item['risk_score']}/100", expanded=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if item["image_bytes"]:
                            st.image(item["image_bytes"], caption=item["filename"], use_container_width=True)
                    with c2:
                        st.markdown(f"**Claimed:** `₹{item['total_inr']:,.2f}` ➡️ **Approved Payout:** `₹{item['reimbursed_inr']:,.2f}`")
                        st.write(f"**🕵️‍♂️ Forensic Verdict:** {item['finance_reasoning']}")
                        if item["violations"]:
                            st.error(f"**Violations:** {item['violations']}")
                        st.json(item["raw_receipt"])

    with tab2:
        st.subheader("🛡️ Safeguarded Policy Engine (Option C)")
        author_name = st.text_input("Reviewer Name (Required)")
        change_reason = st.text_input("Audit Justification (Required)")
        new_t1 = st.number_input("Tier-1 Metro Daily Cap (₹)", value=float(active_policy["tier1_cap"]))
        new_home = st.number_input("Home Office Daily Cap (₹)", value=float(active_policy["home_cap"]))
        if st.button("🔒 Commit New Policy Version"):
            if author_name and change_reason:
                next_ver = f"v1.{len(st.session_state.policy_versions)}"
                new_pol = dict(active_policy)
                new_pol.update({"version": next_ver, "updated_by": author_name, "reason": change_reason, "tier1_cap": new_t1, "home_cap": new_home, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                st.session_state.policy_versions.append(new_pol)
                st.success(f"Published {next_ver}!")
                st.rerun()
            else:
                st.error("Author and Justification required!")
        st.json(st.session_state.policy_versions)

    with tab3:
        if st.session_state.ledger:
            df = pd.DataFrame(st.session_state.ledger).drop(columns=["raw_receipt", "image_bytes"], errors="ignore")
            st.dataframe(df, use_container_width=True)
            st.download_button("📥 Download Audit CSV", df.to_csv(index=False).encode("utf-8"), "audit_inr.csv", "text/csv")
