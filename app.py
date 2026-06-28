import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Camping Assignments", page_icon="🏕️")

# How long to reuse Google Sheet reads before asking Google again.
# Increase to 60 if you still hit quota.
CACHE_SECONDS = 30

# --- 1. CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)


@st.cache_data(ttl=CACHE_SECONDS)
def load_data():
    """
    Cached Google Sheets read.

    Important:
    - conn.read(..., ttl=0) keeps the GSheetsConnection itself from caching stale data.
    - @st.cache_data controls the app-level cache instead.
    """
    users = conn.read(worksheet="Users", ttl=0).fillna("")
    tents = conn.read(worksheet="Tents", ttl=0).fillna("")

    if "Name" not in users.columns:
        users = pd.DataFrame(columns=["Name", "Status", "Assigned_Tent"])

    if "Owner" not in tents.columns:
        tents = pd.DataFrame(columns=["Owner", "Type", "Capacity"])

    return users, tents


def save_users(users):
    conn.update(worksheet="Users", data=users)
    load_data.clear()


def save_tents(tents):
    conn.update(worksheet="Tents", data=tents)
    load_data.clear()


def save_users_and_tents(users, tents):
    conn.update(worksheet="Users", data=users)
    conn.update(worksheet="Tents", data=tents)
    load_data.clear()


users_df, tents_df = load_data()

# --- 2. HELPER FUNCTIONS ---
def get_guests(owner_name):
    return users_df[users_df["Assigned_Tent"] == owner_name]["Name"].tolist()


def assign_guest(guest_name, target_tent):
    users_df.loc[users_df["Name"] == guest_name, "Assigned_Tent"] = target_tent
    save_users(users_df)
    st.rerun()


def save_tent(owner, shelter_type, capacity):
    new_tent = pd.DataFrame([
        {
            "Owner": owner,
            "Type": shelter_type,
            "Capacity": capacity
        }
    ])

    updated_tents = pd.concat([tents_df, new_tent], ignore_index=True)
    save_tents(updated_tents)


def remove_tent(owner):
    """
    Remove a tent and fully reset everyone who was assigned to it.

    This makes affected users look like they never made a selection:
    Status = ""
    Assigned_Tent = ""
    """
    updated_users = users_df.copy()
    updated_tents = tents_df.copy()

    # Reset all guests assigned to this tent
    updated_users.loc[
        updated_users["Assigned_Tent"] == owner,
        ["Status", "Assigned_Tent"]
    ] = ["", ""]

    # Reset the tent owner too
    updated_users.loc[
        updated_users["Name"] == owner,
        ["Status", "Assigned_Tent"]
    ] = ["", ""]

    # Remove the tent row
    updated_tents = updated_tents[updated_tents["Owner"] != owner]

    save_users_and_tents(updated_users, updated_tents)


# Optional manual refresh without forcing every rerun to hit Google Sheets
if st.sidebar.button("Refresh assignments"):
    load_data.clear()
    st.rerun()

# --- 3. MAIN UI ---
st.title("Bass Lake Tents! 🏕️")

st.markdown(
    """
    <style>
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: white !important;
        color: black !important;
        border: 1px solid #999999 !important;
    }

    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background-color: #f2f2f2 !important;
        color: black !important;
        border: 1px solid #666666 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

user_list = ["--"] + users_df["Name"].tolist()

current_user = st.selectbox(
    "Select Your Name:",
    user_list,
    filter_mode=None
)

reset_col1, reset_col2 = st.columns([2, 1])

with reset_col1:
    st.empty()

with reset_col2:
    reset_clicked = st.button(
        "Reset all my selections",
        type="secondary",
        key="top_reset_all_my_selections"
    )

if reset_clicked and current_user != "-- Select your name --":
    updated_users = users_df.copy()
    updated_tents = tents_df.copy()

    updated_users.loc[
        updated_users["Name"] == current_user,
        ["Status", "Assigned_Tent"]
    ] = ["", ""]

    # If they were a tent owner, delete their tent and reset guests
    if current_user in updated_tents["Owner"].values:
        updated_users.loc[
            updated_users["Assigned_Tent"] == current_user,
            ["Status", "Assigned_Tent"]
        ] = ["", ""]

        updated_tents = updated_tents[updated_tents["Owner"] != current_user]

        save_users_and_tents(updated_users, updated_tents)
    else:
        save_users(updated_users)

    st.rerun()

if current_user != "-- Select your name --":
    st.divider()

    user_row = users_df[users_df["Name"] == current_user].iloc[0]
    user_status = user_row["Status"]
    user_tent = user_row["Assigned_Tent"]

    # --- IF NO SELECTION MADE YET ---
    if user_status == "":
        st.subheader(f"Hi, {current_user}! What is your plan?")

        choice = st.radio(
            "Select an option:",
            [
                "1) I have my own tent / sleeping arrangement",
                "2) I plan to sleep in a friend's tent",
                "3) I need help finding somewhere to sleep"
            ],
            index=None
        )

        if choice:
            if choice.startswith("1"):
                users_df.loc[users_df["Name"] == current_user, "Status"] = "owner"

            elif choice.startswith("2"):
                users_df.loc[users_df["Name"] == current_user, "Status"] = "guest"

            elif choice.startswith("3"):
                users_df.loc[users_df["Name"] == current_user, "Status"] = "needs_help"
                users_df.loc[users_df["Name"] == current_user, "Assigned_Tent"] = "HELP"

            save_users(users_df)
            st.rerun()

        # --- IF USER IS A TENT OWNER ---
    elif user_status == "owner":
        st.subheader("Your Sleeping Arrangement")

        tent_exists = current_user in tents_df["Owner"].values

        if not tent_exists:
            shelter_type = st.radio("What are you sleeping in?", ["Tent", "Car"])

            capacity = st.number_input(
                "I have space for __ additional people to join me:",
                min_value=0,
                max_value=5,
                value=0
            )

            if st.button("Save"):
                save_tent(current_user, shelter_type, capacity)
                st.success("Saved! You can view the assignments below.")
                st.rerun()

        else:
            my_tent = tents_df[tents_df["Owner"] == current_user].iloc[0]
            my_guests = get_guests(current_user)

            st.info(
                f"You are hosting in your {my_tent['Type']} "
                f"with space for {int(my_tent['Capacity'])} guest(s)."
            )

            with st.expander("Edit My Tent"):
                st.markdown(
                    """
                    <style>
                    div[data-testid="stButton"] button[kind="secondary"] {
                        background-color: #1f4d3a;
                        color: white;
                        border: none;
                    }

                    div[data-testid="stButton"] button[kind="secondary"]:hover {
                        background-color: #173b2c;
                        color: white;
                        border: none;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

                cap_col, update_col = st.columns([2, 1])

                with cap_col:
                    new_cap = st.number_input(
                        "Update capacity:",
                        min_value=0,
                        max_value=5,
                        value=int(my_tent["Capacity"])
                    )

                with update_col:
                    st.markdown("<br>", unsafe_allow_html=True)

                    if st.button("Update Capacity", key="update_capacity_btn"):
                        updated_users = users_df.copy()
                        updated_tents = tents_df.copy()

                        # If capacity reduced below current guest count, reset extras
                        if new_cap < len(my_guests):
                            diff = len(my_guests) - new_cap
                            reset_guests = my_guests[-diff:]

                            updated_users.loc[
                                updated_users["Name"].isin(reset_guests),
                                ["Status", "Assigned_Tent"]
                            ] = ["", ""]

                            st.toast(
                                f"Updated! {len(reset_guests)} guest(s) were reset and will need to make a new selection."
                            )

                        updated_tents.loc[
                            updated_tents["Owner"] == current_user,
                            "Capacity"
                        ] = new_cap

                        save_users_and_tents(updated_users, updated_tents)
                        st.rerun()

                st.divider()

                st.caption("Removing your tent will reset anyone assigned to your tent.")

                if st.button("Remove My Tent", type="primary", key="remove_tent_btn"):
                    remove_tent(current_user)
                    st.rerun()

    # --- CONFIRMATION MESSAGE IF USER ALREADY HAS AN ASSIGNMENT ---
    if user_tent != "":
        st.divider()

        if user_tent == "HELP":
            st.warning(
                "You are currently listed under **Help Me Find a Spot**. "
                "You have not been assigned to a tent yet."
            )

        elif user_tent in tents_df["Owner"].values:
            assigned_tent = tents_df[tents_df["Owner"] == user_tent].iloc[0]

            st.success(
                f"You are currently assigned to **{user_tent}'s {assigned_tent['Type']}**."
            )

        else:
            st.info(
                f"You are currently assigned to **{user_tent}**, "
                "but that tent is no longer listed. You may want to update your selection."
            )

    # --- TENT SELECTION BOARD ---
    if user_status in ["guest", "needs_help", "owner"]:

        tent_exists = current_user in tents_df["Owner"].values

        if user_status != "owner" or tent_exists:
            st.divider()
            st.subheader("Current Availible Tents to Sign Up for:")

            for index, tent in tents_df.iterrows():
                owner = tent["Owner"]
                capacity = int(tent["Capacity"])
                guests = get_guests(owner)
                avail = capacity - len(guests)

                col1, col2, col3 = st.columns([2, 2.75, 1.25])

                with col1:
                    st.markdown(f"**{owner}'s {tent['Type']}**")
                
                with col2:
                    st.markdown("**Guests:**")
                
                    if guests:
                        for guest in guests:
                            st.write(guest)
                    else:
                        st.write("None yet")
                
                with col3:
                    if user_tent == owner:
                        st.info("[SELECTED]")
                
                    if avail > 0:
                        st.success(f"{avail} spaces left")
                
                        if user_status != "owner" and user_tent != owner:
                            if st.button("Join", key=f"join_{owner}"):
                                assign_guest(current_user, owner)
                    else:
                        st.error("FULL")
                st.write("---")

            # The HELP bucket
            st.subheader("🆘 Help Me Find a Spot!")

            help_guests = get_guests("HELP")

            col1, col2, col3 = st.columns([2, 2.75, 1.25])

            with col1:
                st.markdown("**Unassigned / Need Help**")
            
            with col2:
                st.markdown("**People:**")
            
                if help_guests:
                    for guest in help_guests:
                        st.write(guest)
                else:
                    st.write("No one currently!")
            
            with col3:
                if user_tent == "HELP":
                    st.info("[SELECTED]")
            
                if user_status != "owner" and user_tent != "HELP":
                    if st.button("Join", key="join_help"):
                        assign_guest(current_user, "HELP")

 
