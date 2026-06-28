import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Camping Assignments", page_icon="🏕️")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. STABLE DATA LOADING ---
@st.cache_data(ttl=60)
def load_all_data():
    return conn.read(worksheet="Users").fillna(""), conn.read(worksheet="Tents").fillna("")

# --- 2. THE REFRESHER ---
def sync_and_refresh(u_df, t_df):
    conn.update(worksheet="Users", data=u_df)
    conn.update(worksheet="Tents", data=t_df)
    st.cache_data.clear()
    st.rerun()

users_df, tents_df = load_all_data()

st.title("🏕️ Camping Tent Assignments")
current_user = st.selectbox("Who are you?", ["-- Select --"] + users_df["Name"].tolist())

if current_user != "-- Select --":
    user_row = users_df[users_df["Name"] == current_user].iloc[0]
    
    # --- FLOW 1: INITIAL SETUP ---
    if user_row["Status"] == "":
        choice = st.radio("What is your plan?", 
                          ["1) I have my own tent/car", "2) I plan to sleep in a friend's tent", "3) I need help"], index=None)
        if choice:
            s = "owner" if "1)" in choice else "guest" if "2)" in choice else "needs_help"
            users_df.loc[users_df["Name"] == current_user, "Status"] = s
            if s == "needs_help": users_df.loc[users_df["Name"] == current_user, "Assigned_Tent"] = "HELP"
            sync_and_refresh(users_df, tents_df)

    # --- FLOW 2: OWNER ---
    elif user_row["Status"] == "owner":
        # Check if tent exists
        if current_user not in tents_df["Owner"].values:
            t = st.radio("Sleeping in?", ["Tent", "Car"])
            c = st.number_input("I have space for __ additional people:", 0, 5)
            if st.button("Save My Tent"):
                new_tent = pd.DataFrame([{"Owner": current_user, "Type": t, "Capacity": c}])
                tents_df = pd.concat([tents_df, new_tent], ignore_index=True)
                sync_and_refresh(users_df, tents_df)
        else:
            st.subheader("Manage My Tent")
            my_tent = tents_df[tents_df["Owner"] == current_user].iloc[0]
            new_cap = st.number_input("Update capacity:", 0, 5, value=int(my_tent['Capacity']))
            
            col1, col2 = st.columns(2)
            if col1.button("Update Capacity"):
                # Handle reducing capacity: move extra guests to HELP
                guests = users_df[users_df["Assigned_Tent"] == current_user]["Name"].tolist()
                if new_cap < len(guests):
                    users_df.loc[users_df["Name"].isin(guests[new_cap:]), "Assigned_Tent"] = "HELP"
                tents_df.loc[tents_df["Owner"] == current_user, "Capacity"] = new_cap
                sync_and_refresh(users_df, tents_df)
            
            if col2.button("Remove My Tent", type="primary"):
                users_df.loc[users_df["Assigned_Tent"] == current_user, "Assigned_Tent"] = "HELP"
                tents_df = tents_df[tents_df["Owner"] != current_user]
                users_df.loc[users_df["Name"] == current_user, "Status"] = ""
                sync_and_refresh(users_df, tents_df)

    # --- FLOW 3: SELECTION BOARD (Guests + Owners can see) ---
    st.divider()
    st.subheader("Tent Selection Board")
    
    for i, row in tents_df.iterrows():
        owner = row['Owner']
        guests = users_df[users_df["Assigned_Tent"] == owner]["Name"].tolist()
        avail = int(row["Capacity"]) - len(guests)
        
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.write(f"**{owner}** ({row['Type']})")
        c2.write(f"Guests: {', '.join(guests) if guests else 'None'}")
        
        if user_row["Status"] != "owner": # Owners can't join other tents
            if avail > 0:
                if c3.button("Join", key=f"join_{owner}"):
                    users_df.loc[users_df["Name"] == current_user, "Assigned_Tent"] = owner
                    sync_and_refresh(users_df, tents_df)
            else:
                c3.write("FULL")
    
    # Help Bucket
    st.write("---")
    help_list = users_df[users_df["Assigned_Tent"] == "HELP"]["Name"].tolist()
    st.write(f"**Help Needed Bucket:** {', '.join(help_list)}")
    if user_row["Status"] != "owner" and user_row["Assigned_Tent"] != "HELP":
        if st.button("Move to 'Help' pool"):
            users_df.loc[users_df["Name"] == current_user, "Assigned_Tent"] = "HELP"
            sync_and_refresh(users_df, tents_df)
