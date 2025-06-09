import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="📬 Job Email Tracker", layout="wide")

st.title("📬 AI-Powered Job Email Tracker")
st.markdown("This dashboard displays summaries of job-related emails from your Gmail inbox.")

CSV_PATH = "job_emails.csv"

if not os.path.exists(CSV_PATH):
    st.warning("🚧 The email data is not yet available. Please wait for the GitHub workflow to fetch emails.")
else:
    df = pd.read_csv(CSV_PATH)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by='Date', ascending=False)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Sender Email": st.column_config.TextColumn(width="small"),
            "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
            "Subject": st.column_config.TextColumn(width="medium"),
            "Summary": st.column_config.TextColumn(width="large"),
        }
    )
if st.button("🔄 Refresh CSV"):
    st.rerun()
