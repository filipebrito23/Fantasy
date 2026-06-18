from datetime import datetime, timezone
from num2words import num2words
import pandas as pd
import streamlit as st
from sqlalchemy import text
from db_v5 import engine, init_db_v5, healthcheck_db_v5, is_postgres_v5
from auth_v5 import authenticate_user_v5, get_all_users_v5, create_user_v5, change_password_v5
from auction_v5 import (
    close_expired_bids_v5,
    submit_bid_v5,
    get_players_with_state_v5,
    get_bid_history_v5,
    get_team_rows_v5,
    get_audit_rows_v5,
    get_all_bids_v5,
    update_bid_v5,
    delete_bid_v5,
)

pg = st.navigation([
    st.Page("pages/lei.py", title="Leilão"),
    st.Page("pages/teams.py", title="Elencos")
    ])
