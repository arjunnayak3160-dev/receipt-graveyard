import streamlit as st
import pandas as pd
import re
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="The Receipt Graveyard (Zero-API Engine)", page_icon="🧾", layout="wide")

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

# --- 2. DETERMINISTIC ZERO-API RECEIPT PARSER & RULE ENGINE ---
def extract_receipt_locally(filename: str, custom_override: dict = None) -> dict:
    """Simulates local OCR extraction deterministically based on file profile or manual test input."""
    if custom_override:
        return custom_override

    fname = filename.lower()
    if "taxi" in fname or "2" in fname:
        return {
            "merchant_name": "Shree Sai Tours & Taxi (Mumbai)",
            "transaction_date": "2026-10-16",
            "currency": "INR",
            "fx_rate_to_inr": 1.0,
            "subtotal": 650.0,
            "tax": 100.0,
            "tip": 50.0,
            "total_printed": 1800.0,  # Intentional ₹1,000 math discrepancy
            "is_itemized": True,
            "handwritten_tampering": True,
            "line_items": [
                {"description": "Airport Base Fare", "amount": 650.0, "category": "Transport"},
                {"description": "Sea Link Toll", "amount": 100.0, "category": "Transport"},
                {"description": "Driver Waiting Tip", "amount": 50.0, "category": "Transport"}
            ]
        }
    elif "upi" in fname or "3" in fname or "dup" in fname:
        return {
            "merchant_name": "Toit Brewpub Bengaluru (UPI Screenshot)",
            "transaction_date": "2026-10-15",
            "currency": "INR",
            "fx_rate_to_inr": 1.0,
            "subtotal": 2587.50,
            "tax": 0.0,
            "tip": 0.0,
            "total_printed": 2587.50,
            "is_itemized": False,  # Unitemized UPI screenshot
            "handwritten_tampering": False,
            "line_items": [
                {"description": "UPI Payment Ref #628819204412", "amount": 2587.50, "category": "Food"}
            ]
        }
    elif "usd" in fname or "foreign" in fname:
        return {
            "merchant_name": "Starbucks Coffee (Airport Transit)",
            "transaction_date": "2026-10-17",
            "currency": "USD",
            "fx_rate_to_inr": 84.0,
            "subtotal": 18.0,
            "tax": 2.0,
            "tip": 0.0,
            "total_printed": 20.0,  # \$20 USD = ₹1,680 INR
            "is_itemized": True,
            "handwritten_tampering": False,
            "line_items": [
                {"description": "Sandwich & Coffee", "amount": 20.0, "category": "Food"}
            ]
        }
    else:
        # Default: Bengaluru Brewpub Bill with Food + Alcohol + CGST/SGST + Service Charge
        return {
            "merchant_name": "Toit Brewpub, Indiranagar",
            "transaction_date": "2026-10-15",
            "currency": "INR",
            "fx_rate_to_inr": 1.0,
            "subtotal": 2250.0,
            "tax": 112.50,
            "tip": 225.0,
            "total_printed": 2587.50,
            "is_itemized": True,
            "handwritten_tampering": False,
            "line_items": [
                {"description": "1x Wood Fired Margherita", "amount": 550.0, "category": "Food"},
                {"description": "1x Peri Peri Chicken", "amount": 450.0, "category": "Food"},
                {"description": "2x Tintin Witbier (Craft Beer)", "amount": 700.0, "category": "Alcohol"},
                {"description": "1x Jameson Whiskey (60ml)", "amount": 550.0, "category": "Alcohol"}
            ]
        }


def run_deterministic_audit(receipt: dict, employee: str, context: str, client_info: str, policy: dict, history: list) -> dict:
    """100% Pure Python Rule Engine: Evaluates math, banned items, city caps, duplicates, and time structuring."""
    violations = []
    risk_score = 10
    fx = receipt.get("fx_rate_to_inr", 1.0)
    total_inr = round(receipt["total_printed"] * fx, 2)
    reimbursable_inr = total_inr

    # 1. Missing Date or Total Check
    if receipt["transaction_date"] == "UNKNOWN" or not receipt["transaction_date"]:
        violations.append("MISSING_DATE: Receipt has no valid date.")
        risk_score += 35

    # 2. Hard Math Verification (Subtotal + GST + Tip == Total Printed)
    calc_total = round(receipt["subtotal"] + receipt["tax"] + receipt["tip"], 2)
    if receipt["subtotal"] > 0 and abs(calc_total - receipt["total_printed"]) > 1.0:
        violations.append(
            f"MATH_MISMATCH: Printed Total ({receipt['total_printed']}) != Subtotal+GST+Tip ({calc_total})"
        )
        risk_score += 55
        reimbursable_inr = 0.0

    # 3. Handwritten Tampering Check
    if receipt.get("handwritten_tampering"):
        violations.append("SUSPICIOUS_INK: Handwritten digit modification detected on receipt.")
        risk_score += 35

    # 4. Cross-Channel Duplicate Detection (Same Employee + Same Date + Similar Amount)
    for past in history:
        if past["employee"] == employee and past["date"] == receipt["transaction_date"]:
            if abs(past["total_inr"] - total_inr) < 5.0:
                violations.append(
                    f"DUPLICATE_DETECTED: Matches earlier ₹{past['total_inr']} claim at '{past['merchant']}' on {past['date']}."
                )
                risk_score = 95
                reimbursable_inr = 0.0

    # 5. Unitemized UPI / Card Slip Rule (Bills over ₹500 must be itemized)
    if total_inr > 500.0 and not receipt.get("is_itemized", True):
        violations.append("NON_ITEMIZED_RECEIPT: Bill exceeds ₹500 but lacks an itemized GST tax invoice (plain UPI/POS slip).")
        risk_score += 30
        reimbursable_inr = 0.0

    # 6. Forbidden Line Items Deduction (Alcohol, Tobacco, Mini-Bar, Fines)
    banned_total_inr = 0.0
    for item in receipt.get("line_items", []):
        if item["category"] in policy["banned_categories"]:
            banned_total_inr += item["amount"] * fx

    if banned_total_inr > 0 and reimbursable_inr > 0:
        # Deduct banned items + their proportional tax/tip
        ratio_allowed = max(0.0, (receipt["subtotal"] * fx - banned_total_inr) / (receipt["subtotal"] * fx)) if receipt["subtotal"] > 0 else 0.0
        reimbursable_inr = round(total_inr * ratio_allowed, 2)
        deducted = round(total_inr - reimbursable_inr, 2)
        violations.append(f"NON_REIMBURSABLE_ITEMS: Deducted ₹{deducted:,.2f} for {policy['banned_categories']} & proportional tax/tip.")
        risk_score += 25

    # 7. Tip / Service Charge Cap Check
    if receipt["subtotal"] > 0:
        tip_pct = (receipt["tip"] / receipt["subtotal"]) * 100.0
        if tip_pct > policy["max_tip_pct"]:
            excess_tip_inr = round((receipt["tip"] - (receipt["subtotal"] * (policy["max_tip_pct"] / 100.0))) * fx, 2)
            if reimbursable_inr > 0:
                reimbursable_inr = max(0.0, round(reimbursable_inr - excess_tip_inr, 2))
            violations.append(f"EXCESS_TIP: Tip ({tip_pct:.1f}%) exceeds {policy['max_tip_pct']}% policy cap. Deducted ₹{excess_tip_inr}.")
            risk_score += 15

    # 8. Context & City Daily Limit Accumulation (The Time Twist)
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
            f"DAILY_CAP_EXCEEDED: Prior spend today (₹{prior_daily_spend}) + Claim (₹{reimbursable_inr}) exceeds {context} cap of ₹{daily_cap}/day. Capped at ₹{allowed_remaining}."
        )
        reimbursable_inr = allowed_remaining
        risk_score += 20

    # 9. Client Details Requirement
    if total_inr > policy["client_threshold"] and not client_info.strip():
        violations.append(f"MISSING_CLIENT_DETAILS: Bills over ₹{policy['client_threshold']} require Client Name & Attendee Count.")
        risk_score += 20

    # 10. Structuring Pattern Detection (Repeated bills just under Manager Threshold)
    mgr_thresh = policy["mgr_threshold"]
    just_under_bills = sum(
        1 for x in history
        if x["employee"] == employee and (mgr_thresh * 0.9) <= x["total_inr"] < mgr_thresh
    )
    if (mgr_thresh * 0.9) <= total_inr < mgr_thresh and just_under_bills >= 1:
        violations.append(
            f"STRUCTURING_PATTERN_ALERT: Employee submitted {just_under_bills + 1} bills between ₹{mgr_thresh*0.9:.0f}–₹{mgr_thresh-1:.0f} to bypass the ₹{mgr_thresh:.0f} manager sign-off limit."
        )
        risk_score += 40

    requires_mgr = total_inr > mgr_thresh or risk_score >= 60

    # Final Status Determination
    if reimbursable_inr == 0.0:
        status = "REJECTED"
    elif any("MISSING_CLIENT_DETAILS" in v or "STRUCTURING_PATTERN" in v for v in violations):
        status = "FLAGGED_FOR_REVIEW"
    elif reimbursable_inr < total_inr:
        status = "PARTIAL_APPROVAL"
    else:
        status = "APPROVED"

    risk_score = min(100, risk_score)

    # Generate clear explanations for both Employee and Finance portals
    if status == "APPROVED":
        emp_msg = f"Approved in full (₹{reimbursable_inr:,.2f}) under Policy {policy['version']}."
        fin_msg = f"Passed all math, duplicate, and {context} cap checks (₹{daily_cap}/day)."
    elif status == "PARTIAL_APPROVAL":
        emp_msg = f"Partially approved for ₹{reimbursable_inr:,.2f} (deducted ₹{total_inr - reimbursable_inr:,.2f} for non-reimbursable items or daily cap limits)."
        fin_msg = f"Auto-deducted ₹{total_inr - reimbursable_inr:,.2f}. Triggers: {'; '.join(violations)}"
    elif status == "FLAGGED_FOR_REVIEW":
        emp_msg = f"Pending Finance/Manager review (Provisional amount: ₹{reimbursable_inr:,.2f}). Please provide missing details if requested."
        fin_msg = f"Flagged for human review. Triggers: {'; '.join(violations)}"
    else:
        emp_msg = "Not eligible for reimbursement due to policy, duplicate, or receipt verification issues."
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


# --- 3. SIDEBAR: PORTAL SWITCHER & 1-CLICK SAMPLE MONTH LOADER ---
with st.sidebar:
    st.title("🧾 Receipt Graveyard")
    st.success("⚡ **100% Local Rule Engine** (Zero External APIs)")
    st.caption(f"🛡️ Active Policy: **{active_policy['version']}** (Eff: {active_policy['effective_date']})")

    user_role = st.radio(
        "🔀 Switch Active Portal:",
        ["👤 Employee Portal", "🕵️‍♂️ Finance Reviewer Portal"]
    )
    st.divider()

    st.subheader("🚀 Hackathon Demo Shortcuts")
    if st.button("📥 Load Full Month Dataset (6 Bills)", use_container_width=True, help="Instantly populates a full month of messy receipts, duplicates, alcohol bills, and structuring patterns!"):
        sample_cases = [
            ("bill1_brewpub.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", None),
            ("upi3_duplicate.png", "Aarav Sharma (Sales)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Infosys - 3 Attendees", None),
            ("taxi2_tampered.png", "Priya Nair (Engineering)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "", None),
            ("structuring_1.png", "Rohan Verma (VP Product)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "TCS Team", {
                "merchant_name": "Social Offline, Koramangala", "transaction_date": "2026-10-18", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 1800.0, "tax": 150.0, "tip": 0.0, "total_printed": 1950.0, "is_itemized": True, "handwritten_tampering": False,
                "line_items": [{"description": "Team Lunch Platters", "amount": 1800.0, "category": "Food"}]
            }),
            ("structuring_2.png", "Rohan Verma (VP Product)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "Wipro Team", {
                "merchant_name": "Truffles, Indiranagar", "transaction_date": "2026-10-19", "currency": "INR", "fx_rate_to_inr": 1.0,
                "subtotal": 1820.0, "tax": 160.0, "tip": 0.0, "total_printed": 1980.0, "is_itemized": True, "handwritten_tampering": False,
                "line_items": [{"description": "Burgers & Shakes", "amount": 1820.0, "category": "Food"}]
            }),
            ("usd_airport.png", "Priya Nair (Engineering)", "Business Trip - Tier 1 Metro (Mumbai / Bengaluru / Delhi NCR)", "", None),
        ]
        for fname, emp, ctx, cli, custom in sample_cases:
            rec = extract_receipt_locally(fname, custom)
            res = run_deterministic_audit(rec, emp, ctx, cli, active_policy, st.session_state.ledger)
            st.session_state.ledger.append({
                "id": len(st.session_state.ledger) + 1,
                "filename": fname,
                "employee": emp,
                "context": ctx,
                "date": rec["transaction_date"],
                "merchant": rec["merchant_name"],
                "orig_currency": rec["currency"],
                "total_inr": res["total_inr"],
                "reimbursed_inr": res["reimbursed_inr"],
                "policy_version": active_policy["version"],
                "mgr_signoff": "Yes ⚠️" if res["requires_mgr"] else "No",
                "status": res["status"],
                "risk_score": res["risk_score"],
                "violations": ", ".join(res["violations"]),
                "employee_message": res["employee_message"],
                "finance_reasoning": res["finance_reasoning"],
                "raw_receipt": rec,
                "image_bytes": None
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
    st.caption(f"Submitting under **Company Policy {active_policy['version']}** (Effective: {active_policy['effective_date']})")

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

        # Optional Custom Receipt Builder so you can test ANY scenario live in front of judges
        with st.expander("🧪 Custom Receipt Simulator (Test Any Numbers Live)"):
            use_custom = st.checkbox("Override uploaded file with custom receipt values below")
            c_merch = st.text_input("Merchant Name", "Third Wave Coffee, Bengaluru")
            c_date = st.text_input("Receipt Date (YYYY-MM-DD)", "2026-10-20")
            c_sub = st.number_input("Subtotal (₹)", value=1000.0)
            c_tax = st.number_input("GST / Tax (₹)", value=50.0)
            c_tip = st.number_input("Tip / Service Charge (₹)", value=50.0)
            c_tot = st.number_input("Printed Total on Bill (₹)", value=1100.0)
            c_alc = st.number_input("Of which Alcohol / Forbidden Amount (₹)", value=0.0)
            c_itemized = st.checkbox("Is Itemized Tax Invoice?", value=True)

        with st.expander(f"📖 View Active Company Policy ({active_policy['version']}) — Read-Only"):
            st.markdown(f"""
            * **Home Office Daily Meal Cap:** `₹{active_policy['home_cap']:,.0f}`
            * **Tier-1 Metro Daily Cap:** `₹{active_policy['tier1_cap']:,.0f}`
            * **Tier-2 City Daily Cap:** `₹{active_policy['tier2_cap']:,.0f}`
            * **Manager Sign-Off Threshold:** `₹{active_policy['mgr_threshold']:,.0f}`
            * **Client Info Required Above:** `₹{active_policy['client_threshold']:,.0f}`
            * **Max Tip / Service Charge:** `{active_policy['max_tip_pct']}%`
            * **Non-Reimbursable Categories:** `{', '.join(active_policy['banned_categories'])}`
            """)
            st.caption("🔒 Only Finance Reviewers can update policy rules.")

        submit_btn = st.button("🚀 Submit for Reimbursement", type="primary", use_container_width=True)

    if submit_btn:
        if not uploaded_files and not use_custom:
            st.warning("⚠️ Please upload a receipt image (or check 'Override with custom receipt values' inside the simulator)!")
        else:
            files_to_process = uploaded_files if uploaded_files else [None]
            for uf in files_to_process:
                fname = uf.name if uf else "custom_simulated_bill.png"
                img_bytes = uf.read() if uf else None

                custom_dict = None
                if use_custom:
                    items = [{"description": "Standard Expense Items", "amount": max(0.0, c_sub - c_alc), "category": "Food"}]
                    if c_alc > 0:
                        items.append({"description": "Alcohol / Beverages", "amount": c_alc, "category": "Alcohol"})
                    custom_dict = {
                        "merchant_name": c_merch,
                        "transaction_date": c_date,
                        "currency": "INR",
                        "fx_rate_to_inr": 1.0,
                        "subtotal": c_sub,
                        "tax": c_tax,
                        "tip": c_tip,
                        "total_printed": c_tot,
                        "is_itemized": c_itemized,
                        "handwritten_tampering": abs((c_sub + c_tax + c_tip) - c_tot) > 1.0,
                        "line_items": items
                    }

                rec = extract_receipt_locally(fname, custom_dict)
                res = run_deterministic_audit(rec, employee_name, trip_context, client_info, active_policy, st.session_state.ledger)

                st.session_state.ledger.append({
                    "id": len(st.session_state.ledger) + 1,
                    "filename": fname,
                    "employee": employee_name,
                    "context": trip_context,
                    "date": rec["transaction_date"],
                    "merchant": rec["merchant_name"],
                    "orig_currency": rec["currency"],
                    "total_inr": res["total_inr"],
                    "reimbursed_inr": res["reimbursed_inr"],
                    "policy_version": active_policy["version"],
                    "mgr_signoff": "Yes ⚠️" if res["requires_mgr"] else "No",
                    "status": res["status"],
                    "risk_score": res["risk_score"],
                    "violations": ", ".join(res["violations"]),
                    "employee_message": res["employee_message"],
                    "finance_reasoning": res["finance_reasoning"],
                    "raw_receipt": rec,
                    "image_bytes": img_bytes
                })
                st.success(f"✅ Processed `{fname}` instantly under Policy `{active_policy['version']}`!")

    with col2:
        st.subheader(f"📋 My Reimbursement Status ({employee_name.split(' ')[0]})")
        my_claims = [c for c in st.session_state.ledger if c["employee"] == employee_name]

        if not my_claims:
            st.info("No receipts submitted yet. Upload a receipt on the left or click **'Load Full Month Dataset'** in the sidebar!")
        else:
            total_claimed = sum(c["total_inr"] for c in my_claims)
            total_approved = sum(c["reimbursed_inr"] for c in my_claims if c["status"] in ["APPROVED", "PARTIAL_APPROVAL"])
            m1, m2 = st.columns(2)
            m1.metric("Total Claimed This Month", f"₹{total_claimed:,.2f}")
            m2.metric("Approved for Payout", f"₹{total_approved:,.2f}")
            st.divider()

            for item in reversed(my_claims):
                badge = {
                    "APPROVED": "🟢 Approved",
                    "PARTIAL_APPROVAL": "🟡 Partially Approved",
                    "FLAGGED_FOR_REVIEW": "🟠 Pending Finance Review",
                    "REJECTED": "🔴 Not Eligible"
                }.get(item["status"], "🟠 Pending")
                st.markdown(f"#### {badge} — {item['merchant']} (`{item['date']}`)")
                st.markdown(f"**Claimed:** `₹{item['total_inr']:,.2f}` ➡️ **Payout:** `₹{item['reimbursed_inr']:,.2f}` *(Policy `{item['policy_version']}`)*")
                st.info(f"💬 **Note:** {item['employee_message']}")
                st.divider()

# ==============================================================================
# PORTAL 2: FINANCE REVIEWER PORTAL (OPTION C SAFEGUARDS)
# ==============================================================================
elif user_role == "🕵️‍♂️ Finance Reviewer Portal":
    st.title("🕵️‍♂️ Finance Reviewer & Governance Center")

    pin = st.sidebar.text_input("🔒 Finance Admin PIN (Default: 1234)", value="1234", type="password")
    if pin != "1234":
        st.error("🔒 Access Denied. Please enter Finance Admin PIN (`1234`).")
        st.stop()

    tab1, tab2, tab3 = st.tabs([
        "🚨 Audit Queue & Fraud Alerts",
        "🛡️ Policy Governance & Audit Log (Option C)",
        "📊 Monthly Ledger & CSV Export"
    ])

    with tab1:
        if not st.session_state.ledger:
            st.info("Queue is empty! Click **'📥 Load Full Month Dataset (6 Bills)'** in the left sidebar to test immediately.")
        else:
            total_bills = len(st.session_state.ledger)
            flagged_bills = sum(1 for x in st.session_state.ledger if x["status"] in ["FLAGGED_FOR_REVIEW", "REJECTED"] or x["risk_score"] >= 60)
            saved_inr = sum(x["total_inr"] - x["reimbursed_inr"] for x in st.session_state.ledger)

            k1, k2, k3 = st.columns(3)
            k1.metric("Total Receipts Audited", total_bills)
            k2.metric("Flagged / High-Risk Bills", flagged_bills)
            k3.metric("₹ INR Saved by Policy Engine", f"₹{saved_inr:,.2f}")
            st.divider()

            for idx, item in enumerate(reversed(st.session_state.ledger)):
                real_idx = len(st.session_state.ledger) - 1 - idx
                color = {"APPROVED": "🟢", "PARTIAL_APPROVAL": "🟡", "FLAGGED_FOR_REVIEW": "🟠", "REJECTED": "🔴"}.get(item["status"], "🟠")

                with st.expander(f"{color} [{item['status']}] {item['employee']} — {item['merchant']} (₹{item['total_inr']:,.2f}) | Policy {item['policy_version']} | Fraud Risk: {item['risk_score']}/100", expanded=True):
                    c1, c2 = st.columns([1, 2.2])
                    with c1:
                        if item["image_bytes"]:
                            st.image(item["image_bytes"], caption=item["filename"], use_container_width=True)
                        else:
                            st.markdown("**📄 Extracted Receipt Data:**")
                            st.json(item["raw_receipt"])
                    with c2:
                        st.markdown(f"**Context:** `{item['context']}` | **Date:** `{item['date']}` | **Mgr Sign-Off:** `{item['mgr_signoff']}`")
                        st.markdown(f"**Claimed:** `₹{item['total_inr']:,.2f}` ➡️ **Engine Approved Payout:** `₹{item['reimbursed_inr']:,.2f}`")
                        st.write(f"**🕵️‍♂️ Forensic Audit Verdict:** {item['finance_reasoning']}")
                        if item["violations"]:
                            st.error(f"**Triggered Rule Violations:** {item['violations']}")

                        b1, b2 = st.columns(2)
                        if b1.button("✅ Force Approve Full (Logged)", key=f"app_{item['id']}_{idx}"):
                            st.session_state.ledger[real_idx]["status"] = "APPROVED"
                            st.session_state.ledger[real_idx]["reimbursed_inr"] = item["total_inr"]
                            st.session_state.ledger[real_idx]["finance_reasoning"] += " [MANUAL OVERRIDE: Approved by Finance]"
                            st.rerun()
                        if b2.button("❌ Force Reject ₹0 (Logged)", key=f"rej_{item['id']}_{idx}"):
                            st.session_state.ledger[real_idx]["status"] = "REJECTED"
                            st.session_state.ledger[real_idx]["reimbursed_inr"] = 0.0
                            st.session_state.ledger[real_idx]["finance_reasoning"] += " [MANUAL OVERRIDE: Rejected by Finance]"
                            st.rerun()

    with tab2:
        st.subheader("🛡️ Safeguarded Policy Engine (Option C: Version Controlled)")
        p_col1, p_col2 = st.columns([1.2, 1])

        with p_col1:
            st.markdown(f"#### 📝 Publish New Policy Version (Active: `{active_policy['version']}`)")
            author_name = st.text_input("Reviewer Name / ID (Required)", placeholder="e.g., Vikram Mehta (VP Finance)")
            eff_date = st.date_input("Effective From Date")
            change_reason = st.text_input("Audit Justification (Required)", placeholder="e.g., Raised Tier-1 Metro cap to ₹3,000 for Q4")

            col_p1, col_p2 = st.columns(2)
            new_home = col_p1.number_input("Home Office Daily Cap (₹)", value=float(active_policy["home_cap"]))
            new_t1 = col_p2.number_input("Tier-1 Metro Daily Cap (₹)", value=float(active_policy["tier1_cap"]))
            new_t2 = col_p1.number_input("Tier-2 City Daily Cap (₹)", value=float(active_policy["tier2_cap"]))
            new_mgr = col_p2.number_input("Manager Sign-Off Threshold (₹)", value=float(active_policy["mgr_threshold"]))
            new_cli = col_p1.number_input("Client Info Required Above (₹)", value=float(active_policy["client_threshold"]))
            new_tip = col_p2.number_input("Max Tip / Service Charge (%)", value=float(active_policy["max_tip_pct"]))

            if st.button("🔒 Commit New Policy Version to Audit Log", type="primary"):
                if not author_name.strip() or not change_reason.strip():
                    st.error("⚠️ Safeguard Triggered: Reviewer Name and Audit Justification are mandatory!")
                else:
                    next_ver = f"v1.{len(st.session_state.policy_versions)}"
                    st.session_state.policy_versions.append({
                        "version": next_ver,
                        "effective_date": str(eff_date),
                        "updated_by": author_name.strip(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "reason": change_reason.strip(),
                        "home_cap": new_home,
                        "tier1_cap": new_t1,
                        "tier2_cap": new_t2,
                        "mgr_threshold": new_mgr,
                        "client_threshold": new_cli,
                        "max_tip_pct": new_tip,
                        "banned_categories": ["Alcohol", "Tobacco", "Mini-Bar", "Fines"]
                    })
                    st.success(f"✅ Published Policy **{next_ver}**! All future claims will be evaluated against these new caps.")
                    st.rerun()

        with p_col2:
            st.markdown("#### 📜 Immutable Policy Version History")
            for ver in reversed(st.session_state.policy_versions):
                with st.expander(f"📌 {ver['version']} — Eff: {ver['effective_date']} (By {ver['updated_by']})", expanded=(ver["version"] == active_policy["version"])):
                    st.markdown(f"**Timestamp:** `{ver['timestamp']}`")
                    st.markdown(f"**Justification:** *{ver['reason']}*")
                    st.json({
                        "Home_Cap_INR": ver["home_cap"],
                        "Tier1_Cap_INR": ver["tier1_cap"],
                        "Tier2_Cap_INR": ver["tier2_cap"],
                        "Mgr_Threshold_INR": ver["mgr_threshold"],
                        "Max_Tip_Pct": ver["max_tip_pct"]
                    })

    with tab3:
        st.subheader("📅 Full Monthly Expense Ledger & Pattern Analysis")
        if not st.session_state.ledger:
            st.info("No data to export yet.")
        else:
            df = pd.DataFrame(st.session_state.ledger).drop(columns=["raw_receipt", "image_bytes"], errors="ignore")
            st.dataframe(df, use_container_width=True)

            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Final Audit Report (CSV)",
                data=csv_data,
                file_name="monthly_expense_audit_inr.csv",
                mime="text/csv",
                type="primary"
            )
