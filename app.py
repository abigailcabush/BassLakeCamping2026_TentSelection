import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Camping Assignments", page_icon="🏕️")

# --- 1. CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Read the data (ttl=0 ensures it pulls fresh data every time)
users_df = conn.read(worksheet="Users", ttl=0).fillna("")
tents_df = conn.read(worksheet="Tents", ttl=0).fillna("")

# Ensure column structures exist even if the sheet is blank initially
if "Name" not in users_df.columns:
    users_df = pd.DataFrame(columns=["Name", "Status", "Assigned_Tent"])
if "Owner" not in tents_df.columns:
    tents_df = pd.DataFrame(columns=["Owner", "Type", "Capacity"])

# --- 2. HELPER FUNCTIONS ---
def get_guests(owner_name):
    # Returns a list of names assigned to this tent
    return users_df[users_df["Assigned_Tent"] == owner_name]["Name"].tolist()

def assign_guest(guest_name, target_tent):
    # Update the user's assigned tent
    users_df.loc[users_df["Name"] == guest_name, "Assigned_Tent"] = target_tent
    conn.update(worksheet="Users", data=users_df)
    st.rerun()

def save_tent(owner, shelter_type, capacity):
    global tents_df
    # Add a new row to the tents dataframe
    new_tent = pd.DataFrame([{"Owner": owner, "Type": shelter_type, "Capacity": capacity}])
    tents_df = pd.concat([tents_df, new_tent], ignore_index=True)
    conn.update(worksheet="Tents", data=tents_df)
    
def remove_tent(owner):
    global tents_df
    # Boot all guests in this tent to the HELP bucket
    users_df.loc[users_df["Assigned_Tent"] == owner, "Assigned_Tent"] = "HELP"
    conn.update(worksheet="Users", data=users_df)
    
    # Remove the tent row
    tents_df = tents_df[tents_df["Owner"] != owner]
    conn.update(worksheet="Tents", data=tents_df)
    
    # Reset owner status
    users_df.loc[users_df["Name"] == owner, "Status"] = ""
    conn.update(worksheet="Users", data=users_df)

# --- 3. MAIN UI ---
st.title("🏕️ Camping Tent Assignments")

user_list = ["-- Select your name --"] + users_df["Name"].tolist()
current_user = st.selectbox("Who are you?", user_list)

if current_user != "-- Select your name --":
    st.divider()
    
    # Get current user's data
    user_row = users_df[users_df["Name"] == current_user].iloc[0]
    user_status = user_row["Status"]
    user_tent = user_row["Assigned_Tent"]
    
    # --- IF NO SELECTION MADE YET ---
    if user_status == "":
        st.subheader(f"Hi, {current_user}! What is your plan?")
        choice = st.radio(
            "Select an option:",
            ["1) I have my own tent / sleeping arrangement", 
             "2) I plan to sleep in a friend's tent", 
             "3) I need help finding somewhere to sleep"],
            index=None
        )
        
        if choice:
            if choice.startswith("1"):
                users_df.loc[users_df["Name"] == current_user, "Status"] = "owner"
                conn.update(worksheet="Users", data=users_df)
            elif choice.startswith("2"):
                users_df.loc[users_df["Name"] == current_user, "Status"] = "guest"
                conn.update(worksheet="Users", data=users_df)
            elif choice.startswith("3"):
                users_df.loc[users_df["Name"] == current_user, "Status"] = "needs_help"
                users_df.loc[users_df["Name"] == current_user, "Assigned_Tent"] = "HELP"
                conn.update(worksheet="Users", data=users_df)
            st.rerun()

    # --- IF USER IS A TENT OWNER ---
    elif user_status == "owner":
        st.subheader("Your Sleeping Arrangement")
        
        # Check if they exist in the Tents sheet
        tent_exists = current_user in tents_df["Owner"].values
        
        if not tent_exists:
            shelter_type = st.radio("What are you sleeping in?", ["Tent", "Car"])
            capacity = st.number_input("I have space for __ additional people to join me:", min_value=0, max_value=5, value=0)
            
            if st.button("Save My Tent"):
                save_tent(current_user, shelter_type, capacity)
                st.success("Saved! You can view the assignments below.")
                st.rerun()
                
        else:
            # Display existing tent details
            my_tent = tents_df[tents_df["Owner"] == current_user].iloc[0]
            my_guests = get_guests(current_user)
            st.info(f"You are hosting in your {my_tent['Type']} with space for {my_tent['Capacity']} guests.")
            
            with st.expander("Edit My Tent"):
                new_cap = st.number_input("Update capacity:", min_value=0, max_value=5, value=int(my_tent['Capacity']))
                col1, col2 = st.columns(2)
                
                if col1.button("Update Capacity"):
                    # Edge case: If capacity reduced below current guest count, boot the extras
                    if new_cap < len(my_guests):
                        diff = len(my_guests) - new_cap
                        booted = my_guests[-diff:] # Grab the most recent ones
                        for bg in booted:
                            users_df.loc[users_df["Name"] == bg, "Assigned_Tent"] = "HELP"
                        conn.update(worksheet="Users", data=users_df)
                        st.toast(f"Updated! {len(booted)} guest(s) were moved to the help pool.")
                    
                    tents_df.loc[tents_df["Owner"] == current_user, "Capacity"] = new_cap
                    conn.update(worksheet="Tents", data=tents_df)
                    st.rerun()
                    
                if col2.button("Remove My Tent", type="primary"):
                    remove_tent(current_user)
                    st.rerun()

    # --- TENT SELECTION BOARD ---
    if user_status in ["guest", "needs_help", "owner"]:
        
        # Only show the board if the owner has finished setting up their tent
        tent_exists = current_user in tents_df["Owner"].values
        if user_status != "owner" or tent_exists:
            
            st.divider()
            st.subheader("🏕️ Tent Selection Board")
            
            if user_status == "owner":
                st.caption("You are a tent owner. You can view assignments but cannot join other tents.")
            
            # Loop through all available tents
            for index, tent in tents_df.iterrows():
                owner = tent["Owner"]
                capacity = int(tent["Capacity"])
                guests = get_guests(owner)
                avail = capacity - len(guests)
                
                guests_str = ", ".join(guests) if guests else "None yet"
                
                col1, col2, col3 = st.columns([2, 3, 1])
                with col1:
                    st.markdown(f"**{owner}'s {tent['Type']}**")
                with col2:
                    st.write(f"Guests: {guests_str}")
                with col3:
                    if avail > 0:
                        st.success(f"{avail} spaces left")
                        # Show join button if they aren't the owner, and aren't already in this tent
                        if user_status != "owner" and user_tent != owner:
                            if st.button("Join", key=f"join_{owner}"):
                                assign_guest(current_user, owner)
                    else:
                        st.error("FULL")
                st.write("---")
                
            # The "HELP" Bucket
            st.subheader("🆘 Help Me Find a Spot!")
            help_guests = get_guests("HELP")
            help_str = ", ".join(help_guests) if help_guests else "No one currently!"
            
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                st.markdown("**Unassigned / Need Help**")
            with col2:
                st.write(f"People: {help_str}")
            with col3:
                st.info("Unlimited spaces")
                if user_status != "owner" and user_tent != "HELP":
                    if st.button("Join", key="join_help"):
                        assign_guest(current_user, "HELP")

    # Emergency Reset Button (For you, the admin)
    if st.button("Reset My Choice", type="secondary"):
        users_df.loc[users_df["Name"] == current_user, "Status"] = ""
        users_df.loc[users_df["Name"] == current_user, "Assigned_Tent"] = ""
        conn.update(worksheet="Users", data=users_df)
        
        # If they were a tent owner, delete their tent
        if current_user in tents_df["Owner"].values:
            remove_tent(current_user)
        st.rerun()
