import os
import base64
import re
import csv
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from utils import parse_email_content, classify_email

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
KEYWORDS = ['interview', 'application', 'shortlisted', 'selected', 'position', 'role', 'offer', 'rejected']

def authenticate_gmail():
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    return build('gmail', 'v1', credentials=creds)

def fetch_job_emails(service):
    query = 'subject:interview OR subject:application OR subject:offer OR subject:job OR from:(@linkedin.com OR @indeed.com OR @workday.com OR @greenhouse.io)'
    results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
    messages = results.get('messages', [])
    return messages

def main():
    service = authenticate_gmail()
    messages = fetch_job_emails(service)

    job_emails = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_data['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date_raw = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        try:
            date = datetime.strptime(date_raw[:-6], "%a, %d %b %Y %H:%M:%S")
        except:
            date = datetime.utcnow()

        snippet = msg_data.get('snippet', '')
        body = parse_email_content(msg_data)
        classification = classify_email(subject + " " + body)

        job_emails.append({
            'From': sender,
            'Date': date.strftime("%Y-%m-%d %H:%M:%S"),
            'Subject': subject,
            'Summary': snippet,
            'Classification': classification
        })

    job_emails.sort(key=lambda x: x['Date'], reverse=True)

    with open('job_emails.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=job_emails[0].keys())
        writer.writeheader()
        writer.writerows(job_emails)

    print("Saved job-related emails to job_emails.csv")

if __name__ == '__main__':
    main()