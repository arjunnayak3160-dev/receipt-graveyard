import streamlit as st
import pandas as pd
import re
import hashlib
import time
import io
import json
from datetime import datetime, timedelta, date
from PIL import Image

# Try loading the free offline OCR engine
try:
    from rapidocr_onnxruntime import RapidOCR
    ocr_engine = RapidOCR()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

try:
    import requests
    from streamlit_lottie import st_lottie
    LOTTIE_AVAILABLE = True
except Exception:
    LOTTIE_AVAILABLE = False


def load_lottie_url(url: str):
    if not LOTTIE_AVAILABLE:
        return None
    try:
        r = requests.get(url, timeout=3)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


lottie_scanning = load_lottie_url("https://assets5.lottiefiles.com/packages/lf20_v1yqrgec.json")

# --- PAGE SETUP & DEEP NAVY / BLUE / OFF-WHITE GLASSMORPHIC CSS ---
st.set_page_config(
    page_title="The Receipt Graveyard | Enterprise Audit OS",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Global Futura Font & Deep Navy / Electric Blue / Off-White Palette */
    .stApp {
        background-color: #080b11;
        background-image: radial-gradient(circle at 12% 12%, rgba(37, 99, 235, 0.18) 0%, transparent 42%),
                          radial-gradient(circle at 88% 88%, rgba(15, 23, 42, 0.65) 0%, transparent 45%);
        color: #f8fafc;
        font-family: "Futura", "Trebuchet MS", -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: #f8fafc !important;
    }

    h1 { font-size: 2.5rem !important; margin-bottom: 0.5rem !important; }
    h2 { font-size: 1.75rem !important; margin-bottom: 0.4rem !important; }
    h3 { font-size: 1.3rem !important; margin-bottom: 0.35rem !important; }
    h4 { font-size: 1.08rem !important; }

    p, span, label, div {
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        color: #cbd5e1;
    }

    /* Glassmorphic Hero & Role Cards */
    .hero-banner {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.16), rgba(15, 23, 42, 0.85));
        border: 1px solid rgba(59, 130, 246, 0.32);
        border-radius: 16px;
        padding: 2.4rem 2rem;
        text-align: center;
        margin-bottom: 1.8rem;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
    }

    .role-card {
        background: rgba(255, 255, 255, 0.025);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 4px solid #2563eb;
        border-radius: 14px;
        padding: 1.6rem;
        margin-bottom: 0.8rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .role-card.reviewer {
        border-top: 4px solid #60a5fa;
    }
    .role-card:hover {
        transform: translateY(-2px);
        border-color: rgba(59, 130, 246, 0.45);
    }

    .feature-card {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 1.4rem;
        height: 100%;
        margin-bottom: 1rem;
    }

    /* Status Chips */
    .chip {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 99px;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        margin-right: 6px;
    }
    .chip-ok { background: rgba(34, 197, 94, 0.16); color: #86efac; border: 1px solid rgba(34, 197, 94, 0.35); }
    .chip-wn { background: rgba(245, 158, 11, 0.16); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.35); }
    .chip-bd { background: rgba(239, 68, 68, 0.16); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.35); }
    .chip-in { background: rgba(59, 130, 246, 0.18); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.35); }

    /* Containers & Expanders */
    div.stExpander {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        margin-bottom: 0.65rem;
    }

    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        padding: 12px 16px;
        border-radius: 10px;
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-weight: 800 !important;
        font-size: 1.45rem !important;
    }

    section[data-testid="stSidebar"] {
        background-color: rgba(8, 11, 17, 0.98);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }

    /* High-Contrast Buttons */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 8px;
        font-family: "Futura", "Trebuchet MS", Arial, sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        letter-spacing: 0.02em;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #1d4ed8, #1e40af);
        border-color: rgba(255, 255, 255, 0.32);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.45);
    }

    input, select, textarea {
        background-color: rgba(255, 255, 255, 0.035) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #f8fafc !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. CONSTANTS, FOREX MATRIX & SECURITY HELPERS ---
FX_RATES = {
    "INR": 1.0,
    "USD": 83.0,
    "EUR": 90.0,
    "GBP": 105.0,
    "AED": 22.6,
    "SGD": 62.0
}

PURPOSES = [
    "Client meal",
    "Office meal",
    "Travel",
    "Supplies",
    "Phone and internet",
    "Fuel",
    "Other"
]

STATUS_LABELS = {
    "approved": "Approved",
    "partial": "Partially Paid",
    "flagged": "Under Review",
    "info": "Needs Info",
    "rejected": "Rejected"
}

STATUS_CHIPS = {
    "approved": "chip-ok",
    "partial": "chip-wn",
    "flagged": "chip-wn",
    "info": "chip-in",
    "rejected": "chip-bd"
}


def hash_pin(pin: str) -> str:
    return hashlib.sha256(str(pin).strip().encode("utf-8")).hexdigest()


def fmt_inr(val: float) -> str:
    return f"₹{round(val):,}"


def days_ago_str(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def infer_city(place: str) -> str:
    if re.search(r"mumbai|bandra|andheri|nariman", place, re.I):
        return "Mumbai"
    if re.search(r"delhi|gurgaon|noida|ncr|bengaluru|bangalore", place, re.I):
        return "Delhi"
    return "Other"


# --- 2. INITIALIZE STATE, USERS, VERSIONED POLICIES & AUDIT LOG ---
if "users" not in st.session_state:
    st.session_state.users = [
        {
            "id": "E101", "name": "Rahul Shah", "role": "emp",
            "pin_hash": hash_pin("482913"), "demo_pin": "482913",
            "designation": "Senior Account Executive", "organization": "Enterprise Sales",
            "gst_number": "27AABCU9603R1ZN", "bank_account": "HDFC Salary A/c (•••• 4092)"
        },
        {
            "id": "E102", "name": "Neha Kulkarni", "role": "emp",
            "pin_hash": hash_pin("735104"), "demo_pin": "735104",
            "designation": "Lead Systems Engineer", "organization": "Platform Engineering",
            "gst_number": "07AABCU9603R1ZN", "bank_account": "ICICI Corporate Expense Card (•••• 8812)"
        },
        {
            "id": "E103", "name": "Amit Patel", "role": "emp",
            "pin_hash": hash_pin("260817"), "demo_pin": "260817",
            "designation": "Regional Operations Lead", "organization": "Global Operations",
            "gst_number": "29AABCU9603R1ZN", "bank_account": "Axis Direct Reimbursement A/c (•••• 1104)"
        },
        {
            "id": "R001", "name": "Anita Rao", "role": "rev",
            "pin_hash": hash_pin("619274"), "demo_pin": "619274",
            "designation": "VP Finance & Compliance", "organization": "CFO Office",
            "edit": True
        }
    ]

if "policies" not in st.session_state:
    st.session_state.policies = [
        {
            "v": 1,
            "from": "2026-01-01",
            "by": "System (CFO Office)",
            "at": "2026-01-01 09:00",
            "why": "Initial Q1-Q4 Corporate Expense Governance Policy",
            "document_text": (
                "CORPORATE EXPENSE POLICY v1.0: Claims must be submitted within 30 days. "
                "Client meals require full client Name, Designation, and Organisation. "
                "Purchases above ₹15,000 require company GSTIN. Monthly cap per employee is ₹25,000."
            ),
            "caps": {
                "Client meal": 1500.0,
                "Office meal": 500.0,
                "Travel": 8000.0,
                "Supplies": 5000.0,
                "Phone and internet": 2000.0,
                "Fuel": 3000.0,
                "Other": 1000.0
            },
            "daily": {
                "Mumbai": 6000.0,
                "Delhi": 5500.0,
                "Other": 3500.0
            },
            "banned": ["alcohol", "liquor", "beer", "wine", "whisky", "cigarette", "tobacco", "fines"],
            "win": 30,
            "appr": 10000.0,
            "month": 25000.0,
            "big_ticket_gst": 15000.0
        }
    ]

if "policy_history" not in st.session_state:
    st.session_state.policy_history = [
        {
            "v": 1, "at": "2026-01-01", "by": "System",
            "sec": "All rules", "why": "Initial policy", "chg": "Baseline v1 policy created"
        }
    ]

if "audit_log" not in st.session_state:
    st.session_state.audit_log = []

if "auth" not in st.session_state:
    st.session_state.auth = {
        "stage": "land",  # 'land', 'login', 'app'
        "role_pick": None,
        "user": None,
        "last_active": time.time(),
        "fails": {},
        "locks": {}
    }

if "flag_states" not in st.session_state:
    st.session_state.flag_states = {}

if "client_rows_count" not in st.session_state:
    st.session_state.client_rows_count = 1

if "last_submitted_receipt" not in st.session_state:
    st.session_state.last_submitted_receipt = None


def log_event(action: str, details: str, actor: str = None):
    who = actor or (st.session_state.auth["user"]["name"] if st.session_state.auth.get("user") else "System")
    st.session_state.audit_log.insert(0, {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "actor": who,
        "action": action,
        "details": details
    })


def get_policy_for_date(expense_date_str: str) -> dict:
    valid = [p for p in st.session_state.policies if p["from"] <= expense_date_str]
    if valid:
        return sorted(valid, key=lambda x: (x["from"], x["v"]))[-1]
    return st.session_state.policies[0]


def get_current_policy() -> dict:
    return sorted(st.session_state.policies, key=lambda x: x["v"])[-1]


def get_user(uid: str) -> dict:
    for u in st.session_state.users:
        if u["id"] == uid:
            return u
    return {"id": uid, "name": uid, "role": "emp"}


# --- 3. OFFLINE RAPIDOCR & DETERMINISTIC RULE ENGINE ---
def extract_receipt_via_rapidocr(image_bytes: bytes):
    """Runs offline RapidOCR and checks image resolution (<400px is flagged as messy/low-res)."""
    is_small = False
    width, height = 0, 0
    lines = []
    raw_text = ""

    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if width < 400 or height < 400:
            is_small = True
        if OCR_AVAILABLE:
            rgb_img = img.convert("RGB")
            result, _ = ocr_engine(rgb_img)
            if result:
                lines = [line[1].strip() for line in result if line[1].strip()]
                raw_text = "\n".join(lines)
    except Exception:
        pass

    def extract_near(keywords, text_block):
        for kw in keywords:
            pattern = rf"{kw}[^\d\n]*?([\d,]+\.\d{{2}}|\d{{3,6}})"
            m = re.search(pattern, text_block, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    pass
        return 0.0

    subtotal = extract_near(["SUBTOTAL", "SUB TOTAL", "BASE FARE"], raw_text)
    cgst = extract_near(["CGST"], raw_text)
    sgst = extract_near(["SGST"], raw_text)
    tax = (cgst + sgst) if (cgst + sgst) > 0 else extract_near(["GST", "TAX", "VAT"], raw_text)
    tip = extract_near(["SERVICE CHARGE", "TIP"], raw_text)
    total_detected = extract_near(["GRAND TOTAL", "TOTAL PAID", "AMOUNT PAID", "TOTAL AMOUNT", "TOTAL"], raw_text)

    all_floats = [float(x.replace(",", "")) for x in re.findall(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b", raw_text)]
    if total_detected == 0.0 and all_floats:
        total_detected = max(all_floats)

    merchant = ""
    for l in lines[:4]:
        if len(l) > 3 and not any(k in l.upper() for k in ["RECEIPT", "INVOICE", "PAYMENT", "DATE", "GSTIN"]):
            merchant = l.title()
            break

    return {
        "is_small": is_small,
        "width": width,
        "height": height,
        "raw_text": raw_text,
        "detected_lines": "\n".join(lines),
        "merchant": merchant,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "tip": round(tip, 2),
        "total_detected": round(total_detected, 2)
    }


def evaluate_receipt(r: dict, ledger: list) -> dict:
    """Applies deterministic policy rules using the policy version active on the receipt's date."""
    p = get_policy_for_date(r["date"])
    reasons = []
    severities = []
    tags = []

    def add_issue(sev: int, tag: str, msg: str):
        severities.append(sev)
        tags.append(tag)
        reasons.append(msg)

    # 1. Future Date Check
    try:
        exp_dt = datetime.strptime(r["date"], "%Y-%m-%d").date()
        age_days = (date.today() - exp_dt).days
    except Exception:
        age_days = 0

    if age_days < 0:
        add_issue(3, "Rule violation", "Expense date cannot be in the future")

    # 2. Filing Window Check
    if age_days > p["win"]:
        add_issue(2, "Rule violation", f"Submitted after the {p['win']}-day filing window ({age_days} days old)")

    # 3. Unreadable / Messy Image Check
    if r.get("small", False):
        add_issue(1, "Messy", "Receipt image is low-resolution or blurry (<400px); hard to read reliably")

    # 4. Client Meal Attendee Completeness Check
    if r["purpose"] == "Client meal":
        valid_clients = [c for c in r.get("clients", []) if c.get("name") and c.get("role") and c.get("org")]
        if not valid_clients:
            add_issue(1, "Missing info", "Client name, designation and organisation are required for client meals")

    # 5. OCR Math Mismatch Check (if subtotal + tax + tip provided)
    sub = r.get("ocr_subtotal", 0.0)
    tax = r.get("ocr_tax", 0.0)
    tip = r.get("ocr_tip", 0.0)
    if sub > 0 and abs((sub + tax + tip) - r["amt"]) > 1.5:
        add_issue(2, "Math mismatch", f"Printed amount ({r['cur']} {r['amt']}) != Subtotal+Tax+Tip ({r['cur']} {sub+tax+tip:.2f})")

    # 6. Banned Items Check
    items_lower = (r.get("items", "") + " " + r.get("notes", "")).lower()
    found_banned = [w for w in p["banned"] if w in items_lower]
    if found_banned:
        add_issue(2, "Rule violation", f"Contains non-reimbursable item(s): {', '.join(found_banned)}")

    # 7. Category Cap Check
    cap = p["caps"].get(r["purpose"], 1000.0)
    if r["inr"] > cap:
        add_issue(2, "Rule violation", f"Over the {r['purpose']} cap of {fmt_inr(cap)} by {fmt_inr(r['inr'] - cap)}")

    # 8. Daily City Limit Check
    city = r.get("city", infer_city(r["place"]))
    daily_limit = p["daily"].get(city, p["daily"]["Other"])
    prior_day_spend = sum(
        x["inr"] for x in ledger
        if x["uid"] == r["uid"] and x["date"] == r["date"] and x["city"] == city
        and x["status"] != "rejected" and x["id"] != r["id"]
    )
    if prior_day_spend + r["inr"] > daily_limit:
        add_issue(2, "Rule violation", f"Daily limit for {city} ({fmt_inr(daily_limit)}) exceeded")

    # 9. Duplicate Receipt Detection
    dup = next((
        x for x in ledger
        if x["uid"] == r["uid"] and x["amt"] == r["amt"] and x["cur"] == r["cur"]
        and x["date"] == r["date"] and x["place"].strip().lower() == r["place"].strip().lower()
        and x["id"] != r["id"]
    ), None)
    if dup:
        add_issue(2, "Duplicate", f"Possible duplicate of receipt #{dup['id']} ({r['place']} on {r['date']})")

    # 10. 30-Day Rolling Monthly Limit Check
    monthly_spend = sum(
        x["inr"] for x in ledger
        if x["uid"] == r["uid"] and x["status"] != "rejected" and x["id"] != r["id"]
        and abs((datetime.strptime(r["date"], "%Y-%m-%d") - datetime.strptime(x["date"], "%Y-%m-%d")).days) <= 30
    ) + r["inr"]
    if monthly_spend > p["month"]:
        add_issue(2, "Rule violation", f"Monthly limit of {fmt_inr(p['month'])} exceeded ({fmt_inr(monthly_spend)})")

    # 11. Manager Sign-Off Threshold Check
    if r["inr"] > p["appr"]:
        add_issue(2, "Needs approval", f"Above {fmt_inr(p['appr'])}: requires manager sign-off")

    # 12. Big-Ticket GSTIN Check
    emp_user = get_user(r["uid"])
    big_ticket = p.get("big_ticket_gst", 15000.0)
    if r["inr"] >= big_ticket and not emp_user.get("gst_number", "").strip():
        add_issue(2, "Missing GSTIN", f"Purchases >= {fmt_inr(big_ticket)} require valid corporate GSTIN")

    r["reasons"] = reasons
    r["ver"] = p["v"]
    if not severities:
        r["status"] = "approved"
        r["tag"] = "Compliant"
        r["paid"] = r["inr"]
        r["by"] = "System"
    else:
        max_sev = max(severities)
        first_idx = severities.index(max_sev)
        r["tag"] = tags[first_idx]
        if max_sev == 3:
            r["status"] = "rejected"
        elif max_sev == 1 and len(set(severities)) == 1:
            r["status"] = "info"
        else:
            r["status"] = "flagged"
        r["paid"] = 0.0
        r["by"] = "System"
    return r


def parse_unstructured_policy_doc(doc_text: str, base_policy: dict) -> dict:
    """Extracts policy thresholds dynamically from unstructured policy documents."""
    updated = json.loads(json.dumps(base_policy))
    updated["document_text"] = doc_text

    m_win = re.search(r"(\d+)\s*(?:days|day)\s*(?:filing|window|submission)?", doc_text, re.I)
    if m_win:
        updated["win"] = int(m_win.group(1))

    m_mon = re.search(r"monthly\s*(?:limit|cap).*?(?:₹|rs\.?|inr)\s*([\d,]+)", doc_text, re.I)
    if m_mon:
        updated["month"] = float(m_mon.group(1).replace(",", ""))

    m_appr = re.search(r"(?:sign-off|approval|manager).*?(?:₹|rs\.?|inr)\s*([\d,]+)", doc_text, re.I)
    if m_appr:
        updated["appr"] = float(m_appr.group(1).replace(",", ""))

    for purpose in PURPOSES:
        m_cap = re.search(rf"{re.escape(purpose)}\s*(?:cap|limit)?.*?(?:₹|rs\.?|inr)\s*([\d,]+)", doc_text, re.I)
        if m_cap:
            updated["caps"][purpose] = float(m_cap.group(1).replace(",", ""))

    for city in ["Mumbai", "Delhi", "Other"]:
        m_city = re.search(rf"{city}\s*(?:daily|limit|cap)?.*?(?:₹|rs\.?|inr)\s*([\d,]+)", doc_text, re.I)
        if m_city:
            updated["daily"][city] = float(m_city.group(1).replace(",", ""))

    return updated


# --- 4. SEED DEMO LEDGER DATA ---
def seed_demo_data():
    st.session_state.ledger = []
    st.session_state.nid = 1

    def add_seed(uid, purpose, place, days_back, amt, cur, items, clients=None, small=False, with_cols=None):
        r = {
            "id": st.session_state.nid,
            "uid": uid,
            "purpose": purpose,
            "place": place,
            "city": infer_city(place),
            "date": days_ago_str(days_back),
            "time": "13:30",
            "cur": cur,
            "amt": float(amt),
            "inr": round(float(amt) * FX_RATES[cur], 2),
            "clients": clients or [],
            "col": with_cols or [],
            "notes": "",
            "items": items,
            "small": small,
            "file": "sample_receipt.jpg",
            "note": "",
            "image_bytes": None
        }
        st.session_state.nid += 1
        evaluate_receipt(r, st.session_state.ledger)
        st.session_state.ledger.append(r)

    add_seed("E101", "Client meal", "Taj Restaurant, Mumbai", 3, 1400, "INR", "Executive Thali, Mineral Water",
             [{"name": "Sandeep Rao", "role": "Procurement Manager", "org": "Tata Projects"}], False, ["E102"])
    add_seed("E101", "Travel", "Cab, Mumbai", 3, 900, "INR", "Airport cab transfer")
    add_seed("E101", "Client meal", "Hotel Sea Rock, Mumbai", 5, 2200, "INR", "Dinner\nSingle Malt Whisky",
             [{"name": "Sandeep Rao", "role": "Procurement Manager", "org": "Tata Projects"}])
    add_seed("E101", "Client meal", "Taj Restaurant, Mumbai", 3, 1400, "INR", "Executive Thali",
             [{"name": "Sandeep Rao", "role": "Procurement Manager", "org": "Tata Projects"}])
    add_seed("E102", "Supplies", "Staples, Delhi", 4, 4800, "INR", "Printer paper & toner")
    add_seed("E102", "Supplies", "Office Depot, Delhi", 2, 4900, "INR", "LaserJet Cartridge")
    add_seed("E102", "Office meal", "Cafe Delhi, Delhi", 1, 480, "INR", "Working Lunch", None, True)
    add_seed("E102", "Fuel", "HP Petrol Pump, Pune", 2, 1200, "INR", "Petrol refill", None, True)
    add_seed("E103", "Client meal", "Burj Cafe, Dubai", 2, 16, "USD", "Business Lunch, Coffee",
             [{"name": "Omar Khan", "role": "VP Procurement", "org": "Gulf Traders"}])
    add_seed("E103", "Travel", "IndiGo Flight, Delhi", 6, 7900, "INR", "Flight ticket")
    add_seed("E103", "Travel", "Taj Vivanta, Delhi", 4, 7950, "INR", "Hotel stay")


if "ledger" not in st.session_state:
    seed_demo_data()


# --- 5. SESSION TIMEOUT CHECK (15 MINUTES) ---
if st.session_state.auth["user"] is not None:
    if time.time() - st.session_state.auth["last_active"] > 900:
        log_event("Session Timeout", f"Auto-logged out {st.session_state.auth['user']['id']}")
        st.session_state.auth["user"] = None
        st.session_state.auth["stage"] = "land"
        st.warning("Session expired due to inactivity. Please log in again.")
    else:
        st.session_state.auth["last_active"] = time.time()


# --- 6. SIDEBAR STATUS & CONTROLS ---
active_pol = get_current_policy()
with st.sidebar:
    st.markdown("### THE RECEIPT GRAVEYARD")
    st.caption(f"Enterprise Governance OS | **Policy v{active_pol['v']}**")
    st.divider()

    if st.session_state.auth["user"]:
        u = st.session_state.auth["user"]
        role_title = "Employee Portal" if u["role"] == "emp" else "Finance Reviewer Portal"
        st.markdown(f"**Logged in as:** `{u['name']}` (`{u['id']}`)")
        st.caption(f"Role: **{role_title}** | Dept: **{u.get('organization', 'Corporate')}**")
        if st.button("Log Out / Switch Role", use_container_width=True):
            log_event("Logout", f"{u['name']} ({u['id']}) signed out")
            st.session_state.auth["user"] = None
            st.session_state.auth["stage"] = "land"
            st.session_state.last_submitted_receipt = None
            st.rerun()
    else:
        st.caption("Authentication Status: **Unauthenticated (PIN Gate Active)**")
        if st.session_state.auth["stage"] != "land":
            if st.button("Back to Landing Page", use_container_width=True):
                st.session_state.auth["stage"] = "land"
                st.rerun()

    st.divider()
    st.markdown("#### Demo & System Controls")
    if st.button("Reload Demo Dataset (11 Receipts)", use_container_width=True):
        seed_demo_data()
        log_event("Dataset Reset", "Reloaded 11 realistic demo claims")
        st.rerun()

    if st.button("Clear All Claims", use_container_width=True):
        st.session_state.ledger = []
        st.session_state.last_submitted_receipt = None
        st.rerun()

    with st.expander("Demo Login Credentials"):
        st.markdown("""
        **Employees (6-Digit PIN):**
        * `E101` / `482913` (Rahul Shah)
        * `E102` / `735104` (Neha Kulkarni)
        * `E103` / `260817` (Amit Patel)

        **Finance Reviewer (6-Digit PIN):**
        * `R001` / `619274` (Anita Rao)
        """)


# ==============================================================================
# STAGE 1: MINIMALIST LANDING PAGE (EQUAL ROLE CARDS + FEATURE CARDS)
# ==============================================================================
if st.session_state.auth["stage"] == "land":
    st.markdown("""
    <div class="hero-banner">
        <h1>The Receipt Graveyard</h1>
        <p style="font-size: 1.12rem; max-width: 720px; margin: 0.5rem auto 0 auto; color: #cbd5e1;">
            Submit receipts, receive an automated compliance decision in seconds, and let finance reviewers focus exclusively on exceptions that require human judgment.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Equal Role Cards
    col_emp, col_rev = st.columns(2, gap="large")
    with col_emp:
        st.markdown("""
        <div class="role-card">
            <h2>Employee Portal</h2>
            <p style="color: #94a3b8; margin-bottom: 1.2rem;">
                Submit multi-currency receipts, tag colleagues and client attendees, and track claimed or unclaimed payouts in real time.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Continue as Employee", key="btn_land_emp", use_container_width=True):
            st.session_state.auth["role_pick"] = "emp"
            st.session_state.auth["stage"] = "login"
            st.rerun()

    with col_rev:
        st.markdown("""
        <div class="role-card reviewer">
            <h2>Finance Reviewer Portal</h2>
            <p style="color: #94a3b8; margin-bottom: 1.2rem;">
                Audit non-compliant claims with PIN-verified sign-offs, monitor flagged employees, and publish versioned corporate policies.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Continue as Finance Reviewer", key="btn_land_rev", use_container_width=True):
            st.session_state.auth["role_pick"] = "rev"
            st.session_state.auth["stage"] = "login"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 3 Minimalist Feature Cards
    f1, f2, f3 = st.columns(3, gap="medium")
    with f1:
        st.markdown("""
        <div class="feature-card">
            <h4 style="color: #60a5fa;">[ 01 ] Offline RapidOCR & Resolution Gate</h4>
            <p style="font-size: 0.88rem; color: #94a3b8;">
                Parses JPG, JPEG, and PNG receipts locally for privacy while flagging low-resolution (<400px) or blurry images before payout.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with f2:
        st.markdown("""
        <div class="feature-card">
            <h4 style="color: #60a5fa;">[ 02 ] Date-Versioned Policy Engine</h4>
            <p style="font-size: 0.88rem; color: #94a3b8;">
                Evaluates every receipt against the exact policy version active on the expense date—checking city caps, 30-day limits, and banned items.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with f3:
        st.markdown("""
        <div class="feature-card">
            <h4 style="color: #60a5fa;">[ 03 ] 6-Digit Hashed PIN Governance</h4>
            <p style="font-size: 0.88rem; color: #94a3b8;">
                Protects both portals with SHA-256 PIN hashing, brute-force lockouts, and mandatory PIN re-verification on every reviewer action.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <hr style="border-color: rgba(255,255,255,0.07); margin-top: 2rem;">
    <div style="display:flex; justify-content:space-between; color:#64748b; font-size:0.82rem; padding-bottom:1rem;">
        <span>© 2026 The Receipt Graveyard | Enterprise Audit OS</span>
        <span>Full-Stack Deterministic Compliance Platform</span>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# STAGE 2: 6-DIGIT PIN GATE WITH LOCKOUT PROTECTION
# ==============================================================================
elif st.session_state.auth["stage"] == "login":
    role_pick = st.session_state.auth["role_pick"]
    role_name = "Employee" if role_pick == "emp" else "Finance Reviewer"

    _, center_col, _ = st.columns([1, 1.3, 1])
    with center_col:
        st.markdown(f"## {role_name} Security PIN Gate")
        st.caption("Server-side role verification & 6-digit SHA-256 PIN authentication.")

        default_id = "E101" if role_pick == "emp" else "R001"
        default_pin = "482913" if role_pick == "emp" else "619274"

        uid_in = st.text_input("User ID", value=default_id).strip().upper()
        pin_in = st.text_input("6-Digit Security PIN", value=default_pin, type="password", max_chars=6)

        c_b1, c_b2 = st.columns(2)
        enter_clicked = c_b1.button("Verify & Enter Portal", use_container_width=True)
        back_clicked = c_b2.button("Change Role", use_container_width=True)

        if back_clicked:
            st.session_state.auth["stage"] = "land"
            st.rerun()

        if enter_clicked:
            now = time.time()
            lock_until = st.session_state.auth["locks"].get(uid_in, 0)
            if now < lock_until:
                wait_sec = int(lock_until - now) + 1
                st.error(f"Account locked due to repeated failures. Try again in {wait_sec} seconds.")
            else:
                matched_user = next((u for u in st.session_state.users if u["id"] == uid_in), None)
                if not matched_user or matched_user["role"] != role_pick or matched_user["pin_hash"] != hash_pin(pin_in):
                    fails = st.session_state.auth["fails"].get(uid_in, 0) + 1
                    if fails >= 5:
                        st.session_state.auth["locks"][uid_in] = now + 30
                        st.session_state.auth["fails"][uid_in] = 0
                        st.error("5 failed attempts. Account locked for 30 seconds.")
                    else:
                        st.session_state.auth["fails"][uid_in] = fails
                        st.error(f"ID or PIN incorrect ({5 - fails} attempts remaining before lockout).")
                else:
                    st.session_state.auth["fails"][uid_in] = 0
                    st.session_state.auth["user"] = matched_user
                    st.session_state.auth["last_active"] = now
                    st.session_state.auth["stage"] = "app"
                    log_event("Login", f"{matched_user['name']} ({matched_user['id']}) authenticated via PIN gate", matched_user["name"])
                    st.rerun()

        st.info(
            "Demo Accounts: Employees: **E101** / `482913`, **E102** / `735104`, **E103** / `260817` | "
            "Reviewer: **R001** / `619274`"
        )


# ==============================================================================
# STAGE 3A: AUTHENTICATED EMPLOYEE PORTAL
# ==============================================================================
elif st.session_state.auth["stage"] == "app" and st.session_state.auth["user"]["role"] == "emp":
    user = st.session_state.auth["user"]
    st.markdown(f"# Employee Expense Portal — {user['name']}")

    # Top KPI Bar
    my_receipts = [r for r in st.session_state.ledger if r["uid"] == user["id"]]
    used_30d = sum(
        r["inr"] for r in my_receipts
        if r["status"] != "rejected" and (date.today() - datetime.strptime(r["date"], "%Y-%m-%d").date()).days <= 30
    )
    claimed_list = [r for r in reversed(my_receipts) if r["status"] in ("approved", "partial")]
    unclaimed_list = [r for r in reversed(my_receipts) if r["status"] not in ("approved", "partial")]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Last 30 Days Spend", f"{fmt_inr(used_30d)} / {fmt_inr(active_pol['month'])}")
    k2.metric("Claimed Receipts", str(len(claimed_list)))
    k3.metric("Unclaimed / Under Review", str(len(unclaimed_list)))
    k4.metric("Active Policy Version", f"v{active_pol['v']}")

    emp_tab1, emp_tab2 = st.tabs(["Submit a Receipt", f"Status Tracker (Claimed: {len(claimed_list)} | Unclaimed: {len(unclaimed_list)})"])

    with emp_tab1:
        # Show immediate decision banner if a receipt was just submitted
        if st.session_state.last_submitted_receipt:
            lr = st.session_state.last_submitted_receipt
            chip_cls = STATUS_CHIPS.get(lr["status"], "chip-wn")
            heading_txt = f"Approved: {fmt_inr(lr['paid'])} will be paid" if lr["status"] == "approved" else f"Sent for Review ({STATUS_LABELS[lr['status']]})"
            reasons_html = "".join(f"<li>{r}</li>" for r in lr["reasons"]) if lr["reasons"] else f"<li>Everything checks out against Policy v{lr['ver']}.</li>"
            st.markdown(f"""
            <div class="role-card" style="border-top-color: {'#22c55e' if lr['status']=='approved' else '#f59e0b'};">
                <span class="chip {chip_cls}">{STATUS_LABELS[lr['status']]}</span>
                <span class="chip chip-in">{lr['tag']}</span>
                <h3 style="margin-top:0.5rem;">{heading_txt}</h3>
                <ul>{reasons_html}</ul>
            </div>
            """, unsafe_allow_html=True)

        col_form, col_id = st.columns([1.45, 1], gap="large")

        with col_id:
            st.markdown("### Employee Identity & Payout Account")
            emp_desig = st.text_input("Designation", value=user.get("designation", "Senior Account Executive"))
            emp_org = st.text_input("Organisation / Division", value=user.get("organization", "Enterprise Sales"))
            emp_gst = st.text_input("Company / Employee GSTIN", value=user.get("gst_number", "27AABCU9603R1ZN"))
            emp_bank = st.selectbox(
                "Expense Reimbursement Account",
                [
                    user.get("bank_account", "HDFC Salary A/c (•••• 4092)"),
                    "ICICI Corporate Expense Card (•••• 8812)",
                    "Axis Direct Reimbursement A/c (•••• 1104)"
                ]
            )
            user["designation"] = emp_desig
            user["organization"] = emp_org
            user["gst_number"] = emp_gst
            user["bank_account"] = emp_bank

        with col_form:
            st.markdown("### Receipt Details & Upload")
            up_file = st.file_uploader("Receipt image (JPG, JPEG or PNG, under 5 MB)", type=["jpg", "jpeg", "png"])

            ocr_info = {"is_small": False, "detected_lines": "", "merchant": "", "subtotal": 0.0, "tax": 0.0, "tip": 0.0, "total_detected": 0.0}
            img_bytes = None
            if up_file is not None:
                img_bytes = up_file.getvalue()
                if len(img_bytes) > 5 * 1024 * 1024:
                    st.error("Image must be under 5 MB.")
                    img_bytes = None
                else:
                    ocr_info = extract_receipt_via_rapidocr(img_bytes)
                    st.image(img_bytes, caption=f"Preview ({ocr_info['width']}x{ocr_info['height']}px)", width=180)
                    if ocr_info["is_small"]:
                        st.warning("Low resolution (<400px): this will be flagged as hard to read. Consider retaking the photo.")

            c1, c2 = st.columns(2)
            with c1:
                purpose = st.selectbox("Purpose", PURPOSES)
                exp_date = st.date_input("Date", value=date.today(), max_value=date.today())
                cur_code = st.selectbox("Currency", list(FX_RATES.keys()))
            with c2:
                default_place = f"{ocr_info['merchant']}, Mumbai" if ocr_info["merchant"] else ""
                place = st.text_input("Place where money was used", value=default_place, placeholder="e.g. Taj Restaurant, Mumbai")
                exp_time = st.time_input("Time", value=datetime.now().time())
                default_amt = ocr_info["total_detected"] if ocr_info["total_detected"] > 0 else 0.0
                amount = st.number_input("Amount", min_value=0.0, step=10.0, value=float(default_amt))

            if cur_code != "INR" and amount > 0:
                st.caption(f"Automatic Exchange Conversion: **{cur_code} {amount:,.2f} ≈ {fmt_inr(amount * FX_RATES[cur_code])}** (Rate: ₹{FX_RATES[cur_code]}/{cur_code})")

            # Colleagues ("People with me")
            other_emps = [u for u in st.session_state.users if u["role"] == "emp" and u["id"] != user["id"]]
            colleague_Selection = st.multiselect(
                "People with me (Colleagues)",
                options=[u["id"] for u in other_emps],
                format_func=lambda x: f"{get_user(x)['name']} ({x})"
            )

            # Dynamic Multi-Client Rows
            st.markdown("#### Client Details (Required for Client Meals)")
            c_btn1, c_btn2, _ = st.columns([1, 1, 2])
            if c_btn1.button("+ Add Client Row", use_container_width=True):
                st.session_state.client_rows_count += 1
            if c_btn2.button("- Remove Row", use_container_width=True) and st.session_state.client_rows_count > 1:
                st.session_state.client_rows_count -= 1

            clients_collected = []
            for idx in range(st.session_state.client_rows_count):
                rc1, rc2, rc3 = st.columns(3)
                cn = rc1.text_input(f"Client Name #{idx+1}", key=f"cn_{idx}", placeholder="e.g. Sandeep Rao")
                cr = rc2.text_input(f"Designation #{idx+1}", key=f"cr_{idx}", placeholder="e.g. Procurement Manager")
                co = rc3.text_input(f"Organisation #{idx+1}", key=f"co_{idx}", placeholder="e.g. Tata Projects")
                if cn.strip() or cr.strip() or co.strip():
                    clients_collected.append({"name": cn.strip(), "role": cr.strip(), "org": co.strip()})

            default_items = ocr_info["detected_lines"] if ocr_info["detected_lines"] else ""
            items_txt = st.text_area(
                "Items on the receipt (one per line — auto-filled by RapidOCR when image is uploaded)",
                value=default_items,
                height=80,
                placeholder="e.g. Dinner, Soft drinks"
            )
            notes_txt = st.text_input("Notes (optional)")
            sim_blurry = st.checkbox("Simulate a blurry, cropped, or low-resolution photo")

            if st.button("Submit Receipt for Automated Audit", use_container_width=True):
                if up_file is None and not sim_blurry and amount <= 0:
                    st.error("Upload a receipt image and enter a valid place and amount.")
                elif not place.strip() or amount <= 0:
                    st.error("Place, date, time, and a positive amount are required.")
                else:
                    if lottie_scanning and LOTTIE_AVAILABLE:
                        st_lottie(lottie_scanning, height=90, key="scan_emp")
                    new_r = {
                        "id": st.session_state.nid,
                        "uid": user["id"],
                        "purpose": purpose,
                        "place": place.strip(),
                        "city": infer_city(place),
                        "date": exp_date.strftime("%Y-%m-%d"),
                        "time": exp_time.strftime("%H:%M"),
                        "cur": cur_code,
                        "amt": float(amount),
                        "inr": round(float(amount) * FX_RATES[cur_code], 2),
                        "clients": clients_collected,
                        "col": colleague_Selection,
                        "notes": notes_txt.strip(),
                        "items": items_txt.strip(),
                        "small": bool(ocr_info["is_small"] or sim_blurry),
                        "file": up_file.name if up_file else "simulated_receipt.jpg",
                        "note": "",
                        "ocr_subtotal": ocr_info["subtotal"],
                        "ocr_tax": ocr_info["tax"],
                        "ocr_tip": ocr_info["tip"],
                        "image_bytes": img_bytes
                    }
                    st.session_state.nid += 1
                    evaluate_receipt(new_r, st.session_state.ledger)
                    st.session_state.ledger.append(new_r)
                    st.session_state.last_submitted_receipt = new_r
                    log_event("Receipt Submitted", f"#{new_r['id']} {new_r['purpose']} ({fmt_inr(new_r['inr'])}) -> {new_r['status']}")
                    st.rerun()

    with emp_tab2:
        sub_c, sub_u = st.tabs([f"Claimed ({len(claimed_list)})", f"Unclaimed ({len(unclaimed_list)})"])

        with sub_c:
            if not claimed_list:
                st.info("No claimed receipts yet.")
            else:
                for r in claimed_list:
                    chip_cls = STATUS_CHIPS.get(r["status"], "chip-ok")
                    approval_by = "Partially paid" if r["paid"] < r["inr"] else ("Auto-approved by System" if r["by"] == "System" else f"Approved by {r['by']}")
                    st.markdown(f"""
                    <div class="feature-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <b>#{r['id']} {r['purpose']} — {r['place']}</b>
                            <span><span class="chip {chip_cls}">{approval_by}</span> <span class="chip chip-in">Policy v{r['ver']}</span></span>
                        </div>
                        <div style="font-size:0.86rem; color:#94a3b8; margin-top:4px;">
                            Date: {r['date']} {r['time']} | Claimed: {r['cur']} {r['amt']:,.2f} ({fmt_inr(r['inr'])}) | <b>Paid: {fmt_inr(r['paid'])}</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with sub_u:
            if not unclaimed_list:
                st.info("No unclaimed or pending receipts.")
            else:
                for r in unclaimed_list:
                    chip_cls = STATUS_CHIPS.get(r["status"], "chip-wn")
                    reason_str = r.get("note") or "; ".join(r.get("reasons", [])) or "Pending review"
                    st.markdown(f"""
                    <div class="feature-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <b>#{r['id']} {r['purpose']} — {r['place']}</b>
                            <span><span class="chip {chip_cls}">{STATUS_LABELS[r['status']]}</span> <span class="chip chip-in">{r.get('tag', 'Review')}</span></span>
                        </div>
                        <div style="font-size:0.86rem; color:#94a3b8; margin-top:4px;">
                            Date: {r['date']} {r['time']} | Amount: {r['cur']} {r['amt']:,.2f} ({fmt_inr(r['inr'])}) | Policy v{r['ver']}
                        </div>
                        <div style="margin-top:8px; color:#fca5a5; font-size:0.9rem;">
                            <b>Reason:</b> {reason_str}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if r["status"] in ("info", "rejected"):
                        if st.button(f"Dispute Decision #{r['id']}", key=f"disp_{r['id']}"):
                            r["status"] = "flagged"
                            r["tag"] = "Disputed"
                            r["reasons"].append("Employee disputed this decision for re-evaluation")
                            log_event("Dispute Raised", f"Receipt #{r['id']} disputed by {user['name']}")
                            st.success(f"Receipt #{r['id']} sent back to Finance Reviewer.")
                            st.rerun()


# ==============================================================================
# STAGE 3B: AUTHENTICATED FINANCE REVIEWER PORTAL
# ==============================================================================
elif st.session_state.auth["stage"] == "app" and st.session_state.auth["user"]["role"] == "rev":
    rev_user = st.session_state.auth["user"]
    st.markdown(f"# Finance Governance Center — {rev_user['name']}")

    compliant_list = [r for r in reversed(st.session_state.ledger) if r["status"] in ("approved", "partial")]
    non_compliant_list = [r for r in reversed(st.session_state.ledger) if r["status"] not in ("approved", "partial")]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compliant Claims", str(len(compliant_list)))
    m2.metric("Non-Compliant Queue", str(len(non_compliant_list)))
    m3.metric("Total Approved Payout", fmt_inr(sum(r["paid"] for r in st.session_state.ledger)))
    m4.metric("Active Policy Version", f"v{active_pol['v']}")

    rtab1, rtab2, rtab3, rtab4 = st.tabs([
        f"Receipts Received ({len(st.session_state.ledger)})",
        "Flagged Employees",
        "Policies (View, Editor & History)",
        "Audit Log & Backup"
    ])

    # --- TAB 1: RECEIPTS RECEIVED (COMPLIANT VS NON-COMPLIANT) ---
    with rtab1:
        sub_nc, sub_comp = st.tabs([
            f"Non-Compliant / Needs Review ({len(non_compliant_list)})",
            f"Compliant ({len(compliant_list)})"
        ])

        with sub_nc:
            if not non_compliant_list:
                st.info("All receipts are compliant. Nothing waiting for review.")
            else:
                for r in non_compliant_list:
                    emp_u = get_user(r["uid"])
                    chip_cls = STATUS_CHIPS.get(r["status"], "chip-wn")
                    with st.expander(f"#{r['id']} [{STATUS_LABELS[r['status']]}] {emp_u['name']} — {r['purpose']} at {r['place']} ({fmt_inr(r['inr'])})", expanded=True):
                        c_info, c_act = st.columns([1.3, 1], gap="medium")
                        with c_info:
                            st.markdown(f"""
                            * **Employee:** {emp_u['name']} (`{emp_u['id']}`) · {emp_u.get('designation', '')} ({emp_u.get('organization', '')})
                            * **Reimbursement A/c:** `{emp_u.get('bank_account', 'Salary A/c')}` | **GSTIN:** `{emp_u.get('gst_number', 'N/A')}`
                            * **Date & Place:** {r['date']} {r['time']} · {r['place']} (City Rule: `{r['city']}`)
                            * **Amount:** {r['cur']} {r['amt']:,.2f} = **{fmt_inr(r['inr'])}** (Evaluated under **Policy v{r['ver']}**)
                            * **Tag:** `{r.get('tag', 'Review')}` | **Items:** `{r.get('items', 'N/A')}`
                            """)
                            if r.get("col"):
                                col_names = ", ".join(get_user(cid)["name"] for cid in r["col"])
                                st.markdown(f"* **Colleagues Present:** {col_names}")
                            if r.get("clients"):
                                cl_str = "; ".join(f"{c['name']} ({c['role']}, {c['org']})" for c in r["clients"])
                                st.markdown(f"* **Client Attendees:** {cl_str}")
                            st.markdown("**Triggered Rule Violations:**")
                            for reason in r.get("reasons", []):
                                st.error(reason)
                            if r.get("note"):
                                st.caption(f"Reviewer Note: {r['note']}")
                            if r.get("image_bytes"):
                                st.image(r["image_bytes"], width=200)

                        with c_act:
                            st.markdown("#### Reviewer Decision (PIN Required)")
                            rev_reason = st.text_input("Reason for decision (required)", key=f"rr_{r['id']}", value=r.get("note", ""))
                            custom_pay = st.number_input("Custom Payout Amount (₹, optional)", key=f"cp_{r['id']}", min_value=0.0, value=float(r["inr"]), step=100.0)
                            rev_pin = st.text_input("Your 6-Digit Reviewer PIN", key=f"rp_{r['id']}", type="password", max_chars=6)

                            b1, b2 = st.columns(2)
                            b3, b4 = st.columns(2)
                            act_choice = None
                            if b1.button("Approve", key=f"ap_{r['id']}", use_container_width=True):
                                act_choice = "approve"
                            if b2.button("Pay Up to Cap", key=f"cap_{r['id']}", use_container_width=True):
                                act_choice = "cap"
                            if b3.button("Ask for Info", key=f"inf_{r['id']}", use_container_width=True):
                                act_choice = "info"
                            if b4.button("Reject", key=f"rej_{r['id']}", use_container_width=True):
                                act_choice = "reject"

                            if act_choice:
                                if not rev_reason.strip():
                                    st.error("A reviewer reason is required.")
                                elif hash_pin(rev_pin) != rev_user["pin_hash"]:
                                    st.error("Reviewer PIN incorrect.")
                                else:
                                    pol_v = get_policy_for_date(r["date"])
                                    cap_val = pol_v["caps"].get(r["purpose"], r["inr"])
                                    if act_choice == "approve":
                                        r["status"] = "approved" if custom_pay >= r["inr"] else "partial"
                                        r["paid"] = min(r["inr"], custom_pay)
                                        r["tag"] = "Cleared"
                                    elif act_choice == "cap":
                                        r["status"] = "partial"
                                        r["paid"] = min(r["inr"], cap_val)
                                        r["tag"] = "Capped"
                                    elif act_choice == "info":
                                        r["status"] = "info"
                                        r["paid"] = 0.0
                                        r["tag"] = "Needs info"
                                    elif act_choice == "reject":
                                        r["status"] = "rejected"
                                        r["paid"] = 0.0
                                        r["tag"] = "Rejected"
                                    r["note"] = f"{rev_reason.strip()} (by {rev_user['name']})"
                                    r["by"] = rev_user["name"]
                                    log_event(f"Reviewer Decision: {act_choice.upper()}", f"Receipt #{r['id']} ({emp_u['name']}) -> Paid {fmt_inr(r['paid'])}. Reason: {rev_reason.strip()}")
                                    st.rerun()

        with sub_comp:
            if not compliant_list:
                st.info("No compliant receipts recorded yet.")
            else:
                rows = []
                for r in compliant_list:
                    eu = get_user(r["uid"])
                    rows.append({
                        "Receipt #": r["id"],
                        "Employee": f"{eu['name']} ({eu['id']})",
                        "Purpose": r["purpose"],
                        "Place": r["place"],
                        "Date": r["date"],
                        "Claimed": fmt_inr(r["inr"]),
                        "Paid": fmt_inr(r["paid"]),
                        "Policy": f"v{r['ver']}",
                        "Approved By": r["by"]
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # --- TAB 2: FLAGGED EMPLOYEES MONITOR ---
    with rtab2:
        st.markdown("### Flagged Employees (Last 30 Days Behavioral & Limit Analysis)")
        flagged_ count = 0
        for emp in [u for u in st.session_state.users if u["role"] == "emp"]:
            emp_rs = [
                r for r in st.session_state.ledger
                if r["uid"] == emp["id"] and (date.today() - datetime.strptime(r["date"], "%Y-%m-%d").date()).days <= 30
            ]
            nc_rs = [r for r in emp_rs if r["status"] not in ("approved", "partial")]
            tot_30d = sum(r["inr"] for r in emp_rs if r["status"] != "rejected")
            messy_rs = [r for r in emp_rs if r.get("tag") == "Messy" or r.get("small")]
            just_under_cap = [
                r for r in emp_rs
                if 0.9 * get_policy_for_date(r["date"])["caps"].get(r["purpose"], 999999) <= r["inr"] <= get_policy_for_date(r["date"])["caps"].get(r["purpose"], 999999)
            ]
            has_dup = any(r.get("tag") == "Duplicate" for r in emp_rs)

            flags_found = []
            if len(nc_rs) >= 2:
                flags_found.append(f"{len(nc_rs)} non-compliant receipts")
            if tot_30d > active_pol["month"]:
                flags_found.append(f"Crossed the 30-day monthly limit ({fmt_inr(tot_30d)} / {fmt_inr(active_pol['month'])})")
            if len(messy_rs) >= 2:
                flags_found.append(f"Repeated unreadable/blurry receipts ({len(messy_rs)})")
            if len(just_under_cap) >= 2:
                flags_found.append(f"Claims repeatedly just under category cap ({len(just_under_cap)} claims)")
            if has_dup:
                flags_found.append("Duplicate receipt submission detected")

            if flags_found:
                flagged_count += 1
                cur_state = st.session_state.flag_states.get(emp["id"], "Open")
                chip_cls = "chip-in" if cur_state == "Dismissed" else "chip-wn"
                st.markdown(f"""
                <div class="feature-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0;">{emp['name']} ({emp['id']}) — {emp.get('organization', '')}</h4>
                        <span class="chip {chip_cls}">Status: {cur_state}</span>
                    </div>
                    <div style="color:#94a3b8; font-size:0.86rem; margin:4px 0 8px 0;">
                        Last 30 Days Spend: <b>{fmt_inr(tot_30d)}</b> of {fmt_inr(active_pol['month'])} limit
                    </div>
                    <ul>{"".join(f"<li>{f}</li>" for f in flags_found)}</ul>
                </div>
                """, unsafe_allow_html=True)
                fb1, fb2, fb3, _ = st.columns([1, 1, 1, 2])
                if fb1.button("Send Reminder", key=f"rem_{emp['id']}", use_container_width=True):
                    st.session_state.flag_states[emp["id"]] = "Reminder sent"
                    log_event("Reminder Sent", f"Compliance reminder sent to {emp['name']}")
                    st.rerun()
                if fb2.button("Place Under Watch", key=f"wat_{emp['id']}", use_container_width=True):
                    st.session_state.flag_states[emp["id"]] = "Under watch"
                    log_event("Employee Watch", f"{emp['name']} placed under compliance watch")
                    st.rerun()
                if fb3.button("Dismiss Flag", key=f"dis_{emp['id']}", use_container_width=True):
                    st.session_state.flag_states[emp["id"]] = "Dismissed"
                    log_event("Flag Dismissed", f"Flag dismissed for {emp['name']}")
                    st.rerun()

        if flagged_count == 0:
            st.info("No employees are currently flagged.")

    # --- TAB 3: POLICIES (READ-ONLY VIEW, VERSIONED EDITOR & CHANGE HISTORY) ---
    with rtab3:
        ptab_v, ptab_e, ptab_h = st.tabs(["Policy View", "Policy Editor (Option C)", "Change History"])

        with ptab_v:
            st.markdown(f"### Active Corporate Expense Policy — Version v{active_pol['v']}")
            st.caption(f"Effective from `{active_pol['from']}` · Set by `{active_pol['by']}` · Reason: *{active_pol['why']}*")
            pv1, pv2 = st.columns(2, gap="large")
            with pv1:
                st.markdown("#### Category Caps per Receipt")
                for k, v in active_pol["caps"].items():
                    st.markdown(f"* **{k}:** `{fmt_inr(v)}`")
            with pv2:
                st.markdown("#### Daily Limits by City")
                for k, v in active_pol["daily"].items():
                    st.markdown(f"* **{k}:** `{fmt_inr(v)}`")
                st.markdown("#### Governance Thresholds")
                st.markdown(f"""
                * **Filing Window:** `{active_pol['win']} days`
                * **Manager Sign-Off Above:** `{fmt_inr(active_pol['appr'])}`
                * **30-Day Monthly Limit:** `{fmt_inr(active_pol['month'])}`
                * **Non-Reimbursable Items:** `{', '.join(active_pol['banned'])}`
                """)
            st.info(f"**Loaded Policy Text:** {active_pol.get('document_text', '')}")

        with ptab_e:
            st.markdown(f"### Publish New Policy Version (Creates v{active_pol['v'] + 1})")
            st.caption("Earlier versions are preserved. Receipts are always judged against the policy version effective on their expense date.")

            with st.expander("Option 1: Ingest Unstructured Policy Document Text"):
                sample_doc = (
                    "CORPORATE POLICY UPDATE: Filing window is 45 days. Monthly limit is ₹30,000. "
                    "Manager sign-off above ₹12,000. Client meal cap ₹2,000. Mumbai daily limit ₹7,000."
                )
                doc_text_in = st.text_area("Paste Policy Document Text", value=active_pol.get("document_text", sample_doc), height=100)
                if st.button("Extract Thresholds from Document Text"):
                    extracted = parse_unstructured_policy_doc(doc_text_in, active_pol)
                    st.session_state["draft_pol"] = extracted
                    st.success("Thresholds extracted into the editor fields below. Review, enter your PIN, and click Publish.")

            draft = st.session_state.get("draft_pol", active_pol)

            ec1, ec2 = st.columns(2)
            new_caps = {}
            with ec1:
                st.markdown("#### Category Caps (₹)")
                for p_name in PURPOSES:
                    new_caps[p_name] = st.number_input(f"{p_name} cap (₹)", value=float(draft["caps"].get(p_name, 1000.0)), step=100.0)
            new_daily = {}
            with ec2:
                st.markdown("#### Daily City Limits & General Rules")
                for c_name in ["Mumbai", "Delhi", "Other"]:
                    new_daily[c_name] = st.number_input(f"Daily limit: {c_name} (₹)", value=float(draft["daily"].get(c_name, 3500.0)), step=250.0)
                new_win = st.number_input("Filing window (days)", value=int(draft["win"]), min_value=1, max_value=180)
                new_appr = st.number_input("Manager sign-off above (₹)", value=float(draft["appr"]), step=500.0)
                new_mon = st.number_input("Monthly limit per employee (₹)", value=float(draft["month"]), step=1000.0)

            new_banned_str = st.text_input("Not reimbursable (comma separated)", value=", ".join(draft["banned"]))
            g1, g2, g3 = st.columns(3)
            why_chg = g1.text_input("Reason for change (required)", placeholder="e.g. Q4 inflation cap adjustment")
            eff_date = g2.date_input("Effective from", value=date.today())
            pol_pin = g3.text_input("Your 6-Digit Reviewer PIN", type="password", max_chars=6, key="pol_pin_in")

            if st.button("Publish New Policy Version", use_container_width=True):
                if not why_chg.strip():
                    st.error("A reason for the policy change is required.")
                elif hash_pin(pol_pin) != rev_user["pin_hash"]:
                    st.error("Reviewer PIN incorrect.")
                else:
                    banned_list = [x.strip().lower() for x in new_banned_str.split(",") if x.strip()]
                    changes = []
                    for k in PURPOSES:
                        if new_caps[k] != active_pol["caps"][k]:
                            changes.append(("Category caps", f"{k}: {fmt_inr(active_pol['caps'][k])} → {fmt_inr(new_caps[k])}"))
                    for k in ["Mumbai", "Delhi", "Other"]:
                        if new_daily[k] != active_pol["daily"][k]:
                            changes.append(("Daily limits", f"{k}: {fmt_inr(active_pol['daily'][k])} → {fmt_inr(new_daily[k])}"))
                    if new_win != active_pol["win"]:
                        changes.append(("Other rules", f"Filing window: {active_pol['win']}d → {new_win}d"))
                    if new_appr != active_pol["appr"]:
                        changes.append(("Other rules", f"Sign-off threshold: {fmt_inr(active_pol['appr'])} → {fmt_inr(new_appr)}"))
                    if new_mon != active_pol["month"]:
                        changes.append(("Other rules", f"Monthly limit: {fmt_inr(active_pol['month'])} → {fmt_inr(new_mon)}"))
                    if banned_list != active_pol["banned"]:
                        changes.append(("Non-reimbursable items", f"{', '.join(active_pol['banned'])} → {', '.join(banned_list)}"))

                    if not changes:
                        st.error("No parameter changes detected to publish.")
                    else:
                        next_v = active_pol["v"] + 1
                        new_pol_obj = {
                            "v": next_v,
                            "from": eff_date.strftime("%Y-%m-%d"),
                            "by": rev_user["name"],
                            "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "why": why_chg.strip(),
                            "document_text": draft.get("document_text", active_pol.get("document_text", "")),
                            "caps": new_caps,
                            "daily": new_daily,
                            "banned": banned_list,
                            "win": int(new_win),
                            "appr": float(new_appr),
                            "month": float(new_mon),
                            "big_ticket_gst": active_pol.get("big_ticket_gst", 15000.0)
                        }
                        st.session_state.policies.append(new_pol_obj)
                        for sec, chg_txt in changes:
                            st.session_state.policy_history.append({
                                "v": next_v,
                                "at": datetime.now().strftime("%Y-%m-%d"),
                                "by": rev_user["name"],
                                "sec": sec,
                                "why": why_chg.strip(),
                                "chg": chg_txt
                            })
                        st.session_state.pop("draft_pol", None)
                        log_event("Policy Published", f"Published Policy v{next_v} ({len(changes)} changes): {why_chg.strip()}")
                        st.success(f"Published Policy Version v{next_v}!")
                        st.rerun()

        with ptab_h:
            st.markdown("### Immutable Policy Change History")
            hist_df = pd.DataFrame(list(reversed(st.session_state.policy_history)))
            hist_df.columns = ["Version", "When", "Who", "Section", "Why", "What Changed"]
            st.dataframe(hist_df, use_container_width=True)

    # --- TAB 4: IMMUTABLE AUDIT LOG & JSON/CSV EXPORT ---
    with rtab4:
        st.markdown("### Immutable System Audit Trail & Ledger Export")
        ex1, ex2 = st.columns(2)
        if st.session_state.ledger:
            clean_ledger = pd.DataFrame(st.session_state.ledger).drop(columns=["image_bytes"], errors="ignore")
            ex1.download_button(
                "Download Full Receipt Ledger (CSV)",
                clean_ledger.to_csv(index=False).encode("utf-8"),
                "receipt_graveyard_ledger.csv",
                "text/csv",
                use_container_width=True
            )
        backup_payload = json.dumps({
            "policies": st.session_state.policies,
            "policy_history": st.session_state.policy_history,
            "ledger": [{k: v for k, v in r.items() if k != "image_bytes"} for r in st.session_state.ledger],
            "audit_log": st.session_state.audit_log
        }, indent=2, default=str)
        ex2.download_button(
            "Download Full Governance State Backup (JSON)",
            backup_payload,
            "receipt_graveyard_backup.json",
            "application/json",
            use_container_width=True
        )

        st.divider()
        if not st.session_state.audit_log:
            st.info("No audit log events recorded yet.")
        else:
            st.dataframe(pd.DataFrame(st.session_state.audit_log), use_container_width=True)
