import os
import re
import streamlit as st
import google.generativeai as genai

# Configuration
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "models/gemini-2.0-flash-exp"

# Helper functions
def build_user_context(name: str, duration_sec: int, summaries: str) -> str:
    """Return the contextual block for the system prompt."""
    summaries = summaries.strip() or "No previous sessions"
    return (
        "## CONTEXTUAL INFORMATION\n"
        f"- User name: {name}\n"
        f"- Expected conversation duration: {duration_sec} seconds\n"
        "- Summaries of previous sessions (most recent first):\n"
        f"{summaries}\n"
    )

def merge_prompt(user_block: str, coach_template: str) -> str:
    placeholder = "<>Userinfo</>"
    if placeholder in coach_template:
        return coach_template.replace(placeholder, user_block)
    return f"{user_block}\n{coach_template}"

def extract_action_items(text: str) -> str:
    """Extract content from <actionitems>...</actionitems> tags."""
    pattern = r'<actionitems>(.*?)</actionitems>'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        return '\n'.join(match.strip() for match in matches)
    return ""

def extract_response_content(text: str) -> str:
    """Extract content from <response>...</response> tags."""
    pattern = r'<response>(.*?)</response>'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()
    # If no response tags found, return the original text (fallback)
    return text

def gemini_chat(system_prompt: str, user_msg: str, history: list):
    """Chat with Gemini using a system prompt and conversation history."""
    # Create model with system instruction
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt
    )
    # Start chat with history only
    chat = model.start_chat(history=history or [])
    resp = chat.send_message(user_msg)
    return resp.text, chat.history

# Streamlit UI
st.set_page_config(page_title="Prompt A/B Lab", layout="wide")
st.title("🧪 Prompt A/B Lab (Gemini)")

# Sidebar – user context inputs
with st.sidebar:
    st.header("User info")
    user_name = st.text_input("User name", "Alice")
    duration_min = st.number_input("Session length (minutes)", 1, 120, 5)
    prev_summaries = st.text_area("Previous session summaries", height=120)

context_block = build_user_context(user_name, duration_min * 60, prev_summaries)

# Initialize persistent state
if "variants" not in st.session_state:
    st.session_state.variants = {
        "Prompt-A": {
            "template": "<>Userinfo</>\n\nYou are a friendly coach. Answer in <=50 words.",
            "history": [],
            "last": "",
            "action_items": ""
        },
        "Prompt-B": {
            "template": "<>Userinfo</>\n\nYou are a concise coach. Answer in <=30 words and end with 🎯.",
            "history": [],
            "last": "",
            "action_items": ""
        }
    }

variant_names = list(st.session_state.variants.keys())
tabs = st.tabs(variant_names)

for name, tab in zip(variant_names, tabs):
    var_state = st.session_state.variants[name]
    with tab:
        var_state["template"] = st.text_area(
            "Coach prompt template (<>Userinfo</> will be replaced)",
            value=var_state["template"], key=f"tpl_{name}", height=200)

        st.markdown("---")
        st.subheader("Conversation")
        
        # Show history
        for entry in var_state["history"]:
            role = entry.role.capitalize()
            # Handle parts - they contain the actual text content
            if hasattr(entry, 'parts') and entry.parts:
                raw_part = entry.parts[0].text if hasattr(entry.parts[0], 'text') else str(entry.parts[0])
                # If it's a model response, extract clean content; if user input, show as-is
                if role == "Model":
                    part = extract_response_content(raw_part)
                else:
                    part = raw_part
            else:
                part = "No content"
            st.markdown(f"**{role}:** {part}")

        user_msg = st.text_input("Your message", key=f"msg_{name}")
        if st.button("Send", key=f"send_{name}") and user_msg:
            sys_prompt = merge_prompt(context_block, var_state["template"])
            raw_reply, new_hist = gemini_chat(sys_prompt, user_msg, var_state["history"])
            var_state["history"] = new_hist
            # Extract clean response content (without tags) for display
            clean_response = extract_response_content(raw_reply)
            var_state["last"] = clean_response
            # Extract action items from the raw reply
            var_state["action_items"] = extract_action_items(raw_reply)
            st.rerun()
        
        # Action Items button and display
        if st.button("Show Action Items", key=f"action_{name}"):
            if var_state["action_items"]:
                st.info("**Latest Action Items:**")
                st.write(var_state["action_items"])
            else:
                st.warning("No action items found in the latest response.")

    st.session_state.variants[name] = var_state

# Latest replies side-by-side
st.markdown("## Latest replies comparison")
col1, col2 = st.columns(2)
col1.subheader(variant_names[0])
col1.write(st.session_state.variants[variant_names[0]]["last"])
col2.subheader(variant_names[1])
col2.write(st.session_state.variants[variant_names[1]]["last"])

# Action Items comparison
st.markdown("## Action Items comparison")
col3, col4 = st.columns(2)
col3.subheader(f"{variant_names[0]} - Action Items")
if st.session_state.variants[variant_names[0]]["action_items"]:
    col3.write(st.session_state.variants[variant_names[0]]["action_items"])
else:
    col3.write("_No action items found_")

col4.subheader(f"{variant_names[1]} - Action Items")
if st.session_state.variants[variant_names[1]]["action_items"]:
    col4.write(st.session_state.variants[variant_names[1]]["action_items"])
else:
    col4.write("_No action items found_") 