import streamlit as st
import pandas as pd

st.set_page_config(page_title="Job Email Tracker", layout="wide")

st.title("📬 AI-Powered Job Email Tracker")

df = pd.read_csv("job_emails.csv")
df['Date'] = pd.to_datetime(df['Date'])
df.sort_values('Date', ascending=False, inplace=True)

with st.expander("Filters"):
    classification = st.multiselect("Filter by Classification", options=df['Classification'].unique(), default=list(df['Classification'].unique()))
    df = df[df['Classification'].isin(classification)]

st.dataframe(df[['From', 'Date', 'Subject', 'Summary']], use_container_width=True)

st.markdown("---")
st.markdown("Built with ❤️ to never miss an interview email again.")