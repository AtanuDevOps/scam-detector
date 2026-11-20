import hmac
import json
import math
import time
from datetime import datetime, timezone
from threading import Lock

import streamlit as st

from analyzer import analyze, get_config


st.set_page_config(
    page_title="স্ক্যাম ডিটেক্টর",
    page_icon="🛡️",
    layout="wide",
)


@st.cache_resource
def get_daily_usage():
    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "count": 0,
    }


@st.cache_resource
def get_daily_usage_lock():
    return Lock()


try:
    auth_users_config = get_config("AUTH_USERS")
    if not isinstance(auth_users_config, str):
        raise ValueError
    configured_auth_users = json.loads(auth_users_config)
    if not isinstance(configured_auth_users, dict) or not configured_auth_users:
        raise ValueError

    auth_users = {}
    for configured_username, configured_password in configured_auth_users.items():
        if not isinstance(configured_username, str) or not isinstance(
            configured_password, str
        ):
            raise ValueError
        normalized_username = configured_username.strip().lower()
        if (
            not normalized_username
            or not configured_password
            or normalized_username in auth_users
        ):
            raise ValueError
        auth_users[normalized_username] = configured_password
except (TypeError, ValueError):
    st.error("লগইন কনফিগার করা হয়নি")
    st.stop()

if st.session_state.get("auth_user") not in auth_users:
    st.session_state.pop("auth_user", None)
    st.session_state.setdefault("auth_failed_attempts", 0)

    lock_until = st.session_state.get("auth_lock_until", 0)
    remaining_seconds = max(0, math.ceil(lock_until - time.time()))
    if remaining_seconds == 0:
        st.session_state["auth_failed_attempts"] = 0
        st.session_state.pop("auth_lock_until", None)

    left, center, right = st.columns([1, 1.5, 1])
    with center:
        st.title("🛡️ স্ক্যাম ডিটেক্টর")
        st.write("সন্দেহজনক বার্তা নিরাপদে যাচাই করুন।")
        if remaining_seconds:
            st.warning(
                f"অনেকবার ভুল চেষ্টা হয়েছে। {remaining_seconds} "
                "সেকেন্ড পরে আবার চেষ্টা করুন।"
            )

        with st.form("login_form"):
            entered_username = st.text_input("ইউজারনেম বা ইমেইল")
            entered_password = st.text_input("পাসওয়ার্ড", type="password")
            login_clicked = st.form_submit_button(
                "লগইন",
                use_container_width=True,
                disabled=bool(remaining_seconds),
            )

        if login_clicked:
            normalized_username = entered_username.strip().lower()
            username_known = normalized_username in auth_users
            expected_password = auth_users.get(
                normalized_username,
                "__invalid_auth_user__",
            )
            password_matches = hmac.compare_digest(
                entered_password.encode("utf-8"),
                expected_password.encode("utf-8"),
            )
            if username_known and password_matches:
                st.session_state["auth_user"] = normalized_username
                st.session_state["auth_failed_attempts"] = 0
                st.session_state.pop("auth_lock_until", None)
                st.rerun()
            else:
                st.session_state["auth_failed_attempts"] += 1
                st.error("ইউজারনেম বা পাসওয়ার্ড ভুল")
                if st.session_state["auth_failed_attempts"] >= 5:
                    st.session_state["auth_lock_until"] = time.time() + 60
                    st.warning(
                        "অনেকবার ভুল চেষ্টা হয়েছে। "
                        f"{math.ceil(st.session_state['auth_lock_until'] - time.time())} "
                        "সেকেন্ড পরে আবার চেষ্টা করুন।"
                    )
    st.stop()

if "analysis_count" not in st.session_state:
    st.session_state.analysis_count = 0


def fill_message(text):
    st.session_state.message_text = text


st.title("🛡️ স্ক্যাম ডিটেক্টর")
st.write(
    "এসএমএস, WhatsApp, Messenger ও স্ক্রিনশট—Bangla, English বা Banglish "
    "সন্দেহজনক বার্তা পরীক্ষা করুন।"
)

with st.sidebar:
    st.write(f"লগইন করেছেন: {st.session_state['auth_user']}")
    if st.button("লগআউট"):
        st.session_state.pop("auth_user", None)
        st.session_state.pop("auth_failed_attempts", None)
        st.session_state.pop("auth_lock_until", None)
        st.session_state.pop("result", None)
        st.rerun()

    st.header("নমুনা মেসেজ")

    st.button(
        "Banglish OTP স্ক্যাম",
        use_container_width=True,
        on_click=fill_message,
        args=(
            "Apnar bKash account bondho hobe. Ekhuni OTP pathan "
            "01XXXXXXXXX number-e, na hole taka kata jabe.",
        ),
    )
    st.button(
        "ভুয়া চাকরির সুযোগ",
        use_container_width=True,
        on_click=fill_message,
        args=(
            "বিদেশি কোম্পানিতে চাকরি নিশ্চিত করতে আজই রেজিস্ট্রেশন ফি "
            "পাঠান।",
        ),
    )
    st.button(
        "নিরাপদ ব্যাংক সতর্কতা",
        use_container_width=True,
        on_click=fill_message,
        args=(
            "Your account ending 1234 was credited with BDT 2500. "
            "Available balance: BDT 10500.",
        ),
    )

    st.subheader("কীভাবে কাজ করে")
    st.write(
        "বার্তা বা স্ক্রিনশট পাঠান। AI কনটেন্টে স্ক্যামের লক্ষণ, "
        "আতঙ্ক বা সন্দেহজনক অনুরোধ খুঁজে বিশ্লেষণ করবে।"
    )
    st.caption("ভবিষ্যতে: ভয়েস ও কল বিশ্লেষণ")

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("মেসেজ লিখুন")
    message = st.text_area(
        "মেসেজ",
        key="message_text",
        height=200,
        placeholder="এখানে সন্দেহজনক মেসেজের লেখা লিখুন...",
        label_visibility="collapsed",
    )

    uploaded = st.file_uploader(
        "স্ক্রিনশট আপলোড করুন",
        type=["png", "jpg", "jpeg"],
    )
    if uploaded is not None:
        st.image(uploaded, use_container_width=True)

    analyze_clicked = st.button("বিশ্লেষণ করো", type="primary", use_container_width=True)

if analyze_clicked:
    if not message.strip() and uploaded is None:
        st.session_state.result = None
        st.warning("একটি মেসেজ লিখুন অথবা স্ক্রিনশট আপলোড করুন।")
    elif st.session_state.analysis_count >= 30:
        st.warning("এই সেশনে সর্বোচ্চ ৩০টি বিশ্লেষণ করা যাবে। পরে আবার চেষ্টা করুন।")
    else:
        try:
            max_daily_requests = int(get_config("MAX_DAILY_REQUESTS", 150))
        except (TypeError, ValueError):
            st.error("দৈনিক সীমার কনফিগারেশন সঠিক নয়।")
            st.stop()

        image_bytes = uploaded.getvalue() if uploaded is not None else None
        image_mime = uploaded.type if uploaded is not None else "image/png"
        usage = get_daily_usage()
        with get_daily_usage_lock():
            today = datetime.now(timezone.utc).date().isoformat()
            if usage["date"] != today:
                usage["date"] = today
                usage["count"] = 0

            if usage["count"] >= max_daily_requests:
                daily_cap_reached = True
            else:
                daily_cap_reached = False
                usage["count"] += 1
                st.session_state.analysis_count += 1

        if daily_cap_reached:
            st.warning("আজকের পরীক্ষার সীমা শেষ, কাল আবার চেষ্টা করুন।")
        else:
            with st.spinner("মেসেজটি বিশ্লেষণ করা হচ্ছে..."):
                st.session_state.result = analyze(
                    text=message if message.strip() else None,
                    image_bytes=image_bytes,
                    image_mime_type=image_mime,
                )

with right:
    st.subheader("ফলাফল")
    result = st.session_state.get("result")

    if result:
        verdict = result.get("verdict", "suspicious")
        if verdict not in ("scam", "suspicious", "safe"):
            verdict = "suspicious"

        banner = {
            "scam": ("🔴 স্ক্যাম", "#c62828"),
            "suspicious": ("🟡 সন্দেহজনক", "#c78a00"),
            "safe": ("🟢 নিরাপদ", "#2e7d32"),
        }
        banner_text, banner_color = banner[verdict]
        st.markdown(
            (
                f'<div style="background:{banner_color}; color:white; '
                'padding:18px 20px; border-radius:12px; font-size:28px; '
                f'font-weight:700; text-align:center;">{banner_text}</div>'
            ),
            unsafe_allow_html=True,
        )

        type_labels = {
            "otp": "ওটিপি/পিন চুরি",
            "prize": "ভুয়া পুরস্কার",
            "job": "ভুয়া চাকরি",
            "loan_app": "লোন অ্যাপ হয়রানি",
            "impersonation": "ছদ্মবেশ ধারণ",
            "none": "নেই",
        }
        confidence_labels = {
            "high": "উচ্চ",
            "medium": "মাঝারি",
            "low": "কম",
        }

        scam_type = result.get("scam_type", "none")
        confidence = result.get("confidence", "low")
        metric_left, metric_right = st.columns(2)
        metric_left.metric("স্ক্যামের ধরন", type_labels.get(scam_type, "নেই"))
        metric_right.metric(
            "নিশ্চিততা",
            confidence_labels.get(confidence, "কম"),
        )

        tactic_labels = {
            "urgency": "তাড়াহুড়ো",
            "fear": "ভয় দেখানো",
            "fake_authority": "ভুয়া কর্তৃপক্ষ",
            "greed": "লোভ",
            "secrecy": "গোপনীয়তা",
            "suspicious_link": "সন্দেহজনক লিংক",
            "payment_request": "টাকা চাওয়া",
            "impersonation": "ছদ্মবেশ",
        }
        tactics = result.get("tactics", [])
        if isinstance(tactics, list) and tactics:
            st.write("**কৌশল**")
            chips = []
            for tactic in tactics:
                if isinstance(tactic, str):
                    label = tactic_labels.get(tactic, tactic)
                    chips.append(
                        '<span style="display:inline-block; background:#e8eef7; '
                        'color:#1f3a5f; padding:5px 10px; margin:3px 5px 3px 0; '
                        f'border-radius:999px;">{label}</span>'
                    )
            if chips:
                st.markdown("".join(chips), unsafe_allow_html=True)

        reason = result.get("reason", "")
        if not isinstance(reason, str):
            reason = ""
        reason_title = "বিশ্লেষণ" if verdict == "safe" else "কেন সন্দেহজনক?"
        st.info(f"**{reason_title}**\n\n{reason}")

        st.subheader("এখন কী করবেন")
        next_steps = result.get("next_steps", [])
        if isinstance(next_steps, list) and next_steps:
            for step in next_steps:
                if isinstance(step, str):
                    st.write(f"✅ {step}")
        else:
            st.write("✅ সতর্ক থাকুন এবং বার্তাটি অফিসিয়াল চ্যানেলে যাচাই করুন।")

        if "error" in result:
            st.warning(
                "এই মুহূর্তে সার্ভারে চাপ আছে, একটু পরে আবার চেষ্টা করুন।"
            )
            with st.expander("টেকনিক্যাল তথ্য"):
                raw_error = str(result.get("error", ""))
                api_key = get_config("GEMINI_API_KEY")
                if api_key:
                    raw_error = raw_error.replace(str(api_key), "[REDACTED]")
                st.write(f"ত্রুটির বিবরণ: {raw_error}")
                if "model_used" in result:
                    st.write(f"ব্যবহৃত মডেল: {result['model_used']}")

st.caption(
    "এটি একটি AI সহায়ক টুল, চূড়ান্ত সিদ্ধান্ত নয়। "
    "কখনো OTP বা PIN কাউকে দেবেন না।"
)
