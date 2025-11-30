import streamlit as st
import requests

API = "http://127.0.0.1:8000"

st.set_page_config(page_title="BOT GPT", page_icon="💬", layout="wide")

# =============================================================================
# SIDEBAR - USER MANAGEMENT
# =============================================================================

with st.sidebar:
    st.title("👤 User")
    
    if "user" not in st.session_state:
        st.session_state.user = None
    
    # Create or select user
    tab1, tab2 = st.tabs(["Select", "Create"])
    
    with tab1:
        try:
            users = requests.get(f"{API}/users").json()["users"]
            if users:
                selected = st.selectbox(
                    "Choose user:",
                    options=[f"{u['name']} ({u['email']})" for u in users]
                )
                user = next(u for u in users if f"{u['name']} ({u['email']})" == selected)
                
                if st.button("Login", use_container_width=True):
                    st.session_state.user = user
                    st.success(f"Logged in as {user['name']}")
                    st.rerun()
        except:
            st.error("Backend not running")
    
    with tab2:
        with st.form("create_user"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            
            if st.form_submit_button("Create"):
                try:
                    user = requests.post(f"{API}/users", json={"name": name, "email": email}).json()
                    st.session_state.user = user
                    st.success("Created!")
                    st.rerun()
                except:
                    st.error("Error creating user")
    
    # Show current user
    if st.session_state.user:
        st.divider()
        st.success(f"**{st.session_state.user['name']}**")
        st.caption(st.session_state.user['email'])
        
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.conversation = None
            st.session_state.messages = []
            st.rerun()

# Require login
if not st.session_state.user:
    st.title("💬 BOT GPT")
    st.info("👈 Please login from sidebar")
    st.stop()

# =============================================================================
# MAIN APP
# =============================================================================

st.title("💬 BOT GPT")

# Initialize
if "conversation" not in st.session_state:
    st.session_state.conversation = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Tabs
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📋 History", "📄 Documents"])

# =============================================================================
# TAB 1: CHAT
# =============================================================================

with tab1:
    col1, col2, col3 = st.columns([1, 1, 2])
    
    # Start buttons
    with col1:
        if st.button("🗨️ Start Open Chat", use_container_width=True):
            try:
                res = requests.post(f"{API}/conversations", json={
                    "user_id": st.session_state.user["id"],
                    "first_message": "Hello!",
                    "mode": "open"
                }).json()
                
                st.session_state.conversation = res["conversation_id"]
                st.session_state.mode = "open"
                st.session_state.messages = [
                    ("user", "Hello!"),
                    ("assistant", res["assistant_response"])
                ]
                st.rerun()
            except Exception as e:
                st.error(str(e))
    
    with col2:
        if st.button("📚 Start RAG Chat", use_container_width=True):
            try:
                res = requests.post(f"{API}/conversations", json={
                    "user_id": st.session_state.user["id"],
                    "first_message": "Hello!",
                    "mode": "rag"
                }).json()
                
                st.session_state.conversation = res["conversation_id"]
                st.session_state.mode = "rag"
                st.session_state.messages = [
                    ("user", "Hello!"),
                    ("assistant", res["assistant_response"])
                ]
                st.rerun()
            except Exception as e:
                st.error(str(e))
    
    with col3:
        if st.session_state.conversation:
            mode = st.session_state.get("mode", "open")
            st.info(f"**Mode:** {mode.upper()}")
    
    st.divider()
    
    # Document upload for RAG
    if st.session_state.get("mode") == "rag":
        with st.expander("📄 Upload Document"):
            file = st.file_uploader("Choose PDF or TXT", type=["pdf", "txt"])
            
            if file:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Upload"):
                        with st.spinner("Processing..."):
                            try:
                                files = {"file": (file.name, file, file.type)}
                                res = requests.post(f"{API}/documents/upload", files=files).json()
                                st.session_state.last_doc = res["document_id"]
                                st.success(f"✅ Uploaded ({res['chunks']} chunks)")
                            except Exception as e:
                                st.error(str(e))
                
                with col2:
                    if st.session_state.get("last_doc"):
                        if st.button("Attach to Chat"):
                            try:
                                requests.post(
                                    f"{API}/conversations/{st.session_state.conversation}/attach_document",
                                    params={"document_id": st.session_state.last_doc}
                                )
                                st.success("✅ Attached!")
                            except Exception as e:
                                st.error(str(e))
    
    # Chat interface
    if not st.session_state.conversation:
        st.info("👆 Start a conversation")
    else:
        # Display messages
        for role, content in st.session_state.messages:
            with st.chat_message(role):
                st.write(content)
        
        # Input
        if prompt := st.chat_input("Type your message..."):
            # Add user message
            st.session_state.messages.append(("user", prompt))
            
            with st.chat_message("user"):
                st.write(prompt)
            
            # Get response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        res = requests.post(
                            f"{API}/conversations/{st.session_state.conversation}/messages",
                            json={"content": prompt}
                        ).json()
                        
                        reply = res["assistant_response"]
                        st.write(reply)
                        st.session_state.messages.append(("assistant", reply))
                    except Exception as e:
                        st.error(str(e))

# =============================================================================
# TAB 2: HISTORY
# =============================================================================

with tab2:
    st.subheader("📋 Your Conversations")
    
    try:
        convs = requests.get(
            f"{API}/conversations",
            params={"user_id": st.session_state.user["id"]}
        ).json()["conversations"]
        
        if convs:
            for conv in convs:
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    badge = "🗨️" if conv["mode"] == "open" else "📚"
                    st.write(f"{badge} **{conv['title']}**")
                    st.caption(f"Tokens: {conv['total_tokens']}")
                
                with col2:
                    if st.button("Resume", key=f"r{conv['id']}", use_container_width=True):
                        try:
                            detail = requests.get(f"{API}/conversations/{conv['id']}").json()
                            st.session_state.conversation = conv['id']
                            st.session_state.mode = conv['mode']
                            st.session_state.messages = [
                                (m['role'], m['content']) for m in detail['messages']
                            ]
                            st.success("Resumed!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                
                with col3:
                    if st.button("Delete", key=f"d{conv['id']}", use_container_width=True):
                        requests.delete(f"{API}/conversations/{conv['id']}")
                        st.rerun()
                
                st.divider()
        else:
            st.info("No conversations yet")
    except Exception as e:
        st.error(str(e))

# =============================================================================
# TAB 3: DOCUMENTS
# =============================================================================

with tab3:
    st.subheader("📄 Your Documents")
    
    # Upload
    file = st.file_uploader("Upload Document", type=["pdf", "txt"])
    if file and st.button("Upload"):
        with st.spinner("Processing..."):
            try:
                files = {"file": (file.name, file, file.type)}
                res = requests.post(f"{API}/documents/upload", files=files).json()
                st.success(f"✅ Uploaded: {res['chunks']} chunks")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    
    st.divider()
    
    # List documents
    try:
        docs = requests.get(
            f"{API}/documents",
            params={"user_id": st.session_state.user["id"]}
        ).json()
        
        if docs:
            for doc in docs:
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.write(f"📄 **{doc['filename']}**")
                    st.caption(f"Chunks: {doc['chunks']}")
                
                with col2:
                    if st.button("Delete", key=f"del{doc['id']}", use_container_width=True):
                        requests.delete(f"{API}/documents/{doc['id']}")
                        st.rerun()
                
                st.divider()
        else:
            st.info("No documents uploaded")
    except Exception as e:
        st.error(str(e))