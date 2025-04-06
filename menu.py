import streamlit as st

def render_navigation():
    """Render the navigation menu for the app"""
    menu_items = {
        "Home": "/",
        "Tax Reports": "Tax_Reports",
        "Performance": "Performance",
        "Transactions": "Transactions",
        "Settings": "Settings"
    }
    
    # Create navigation menu
    st.markdown(
        """
        <style>
        .nav-container {
            display: flex;
            justify-content: center;
            gap: 20px;
            padding: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid #e6e6e6;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Create horizontal navigation using Streamlit columns
    cols = st.columns(len(menu_items))
    
    for idx, (name, path) in enumerate(menu_items.items()):
        with cols[idx]:
            if st.button(name, key=f"nav_{name}", use_container_width=True):
                if path == "/":
                    st.switch_page("Home.py")
                else:
                    st.switch_page(f"pages/{path}.py") 