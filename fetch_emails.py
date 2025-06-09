import os
import base64
import csv
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email import message_from_bytes
from email.header import decode_header
import openai
import pytz
from hashlib import sha256

# =========== CONFIG =============
# Load these from environment variables (set in GitHub Secrets and Streamlit Cloud)
CLIENT_ID = os.environ.get('GMAIL_CLIENT_ID')
CLIENT_SECRET = os.environ.get('GMAIL_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('GMAIL_REFRESH_TOKEN')

# OpenAI API Key for summarization
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# CSV file path
CSV_FILE = 'job_emails.csv'

# Irish timezone
IRISH_TZ = pytz.timezone('Europe/Dublin')

# =========== AUTH ==============
def get_gmail_service():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        raise ValueError("Missing required Gmail credentials. Please check your environment variables.")

    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES
    )
    
    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
    except Exception as e:
        print("Failed to refresh token:", e)
        raise
        
    service = build('gmail', 'v1', credentials=creds)
    return service

    # List of substrings to exclude (case-insensitive match)
    EXCLUDED_SENDERS = [
        'linkedin.com',
        'indeed.com',
        'tcsion.com',
        'github.com',
        'vodafone',
        'aib.ie',
        'jobs2web.com',
        'match.indeed.com',
        'noreply@linkedin.com',
        'messaging-digest-noreply@linkedin.com'
    ]

    emails_data = []
    for msg in messages:
        data = extract_email_data(service, msg['id'])
        if data:
            sender_lower = data['sender'].lower()
            if any(excluded in sender_lower for excluded in EXCLUDED_SENDERS):
                continue  # Skip excluded senders
            data['summary'] = summarize_text(data['body'])
            emails_data.append(data)


# =========== EMAIL PROCESSING ==============
def decode_mime_words(s):
    decoded_fragments = decode_header(s)
    return ''.join(
        str(t[0], t[1] or 'utf-8') if isinstance(t[0], bytes) else t[0]
        for t in decoded_fragments
    )

def extract_email_data(service, msg_id):
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
        raw_msg = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
        email_msg = message_from_bytes(raw_msg)
    except Exception as e:
        print(f"Failed to get message {msg_id}: {e}")
        return None

    # Extract From
    sender = email_msg.get('From', '')

    # Extract Date
    date_str = email_msg.get('Date', '')
    try:
        date_obj = datetime.strptime(date_str[:-6], '%a, %d %b %Y %H:%M:%S')  # Remove timezone part
        date_obj = IRISH_TZ.localize(date_obj)
    except Exception:
        date_obj = datetime.now(IRISH_TZ)

    # Extract Subject
    subject_raw = email_msg.get('Subject', '')
    subject = decode_mime_words(subject_raw)

    # Extract snippet or first 500 chars for summarization
    body = ''
    if email_msg.is_multipart():
        for part in email_msg.walk():
            if part.get_content_type() == 'text/plain':
                try:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                    break
                except Exception:
                    continue
    else:
        try:
            body = email_msg.get_payload(decode=True).decode(email_msg.get_content_charset() or 'utf-8')
        except Exception:
            body = ''

    return {
        'sender': sender,
        'date': date_obj,
        'subject': subject,
        'body': body
    }

# =========== OPENAI SUMMARY =============
# Simple in-memory cache to avoid duplicate summaries during one run
summary_cache = {}

def summarize_text(text):
    if not OPENAI_API_KEY:
        return "(Summary disabled - OPENAI_API_KEY not set)"

    # Fallback: Skip summarization if body is too short
    if not text or len(text.strip()) < 30:
        return "(Too short to summarize)"

    # Use SHA-256 hash of email body for caching
    email_hash = sha256(text.strip().encode('utf-8')).hexdigest()
    if email_hash in summary_cache:
        return summary_cache[email_hash]

    try:
        import openai
        openai.api_key = OPENAI_API_KEY

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes job-related emails for a job seeker in 1–2 clear, concise sentences."
                },
                {
                    "role": "user",
                    "content": f"Summarize this email for job application purposes:\n\n{text[:2000]}"
                }
            ],
            max_tokens=100,
            temperature=0.3
        )

        summary = response.choices[0].message["content"].strip()
        summary_cache[email_hash] = summary  # Cache result
        return summary

    except Exception as e:
        print("OpenAI API error:", e)
        return "(Summary failed)"


# =========== MAIN LOGIC =============
def main():
    service = get_gmail_service()

    # Query: filter emails related to job/applications/interview/work
    query = '(subject:job OR subject:application OR subject:interview OR subject:work OR from:(linkedin.com OR indeed.com OR "noreply@"))'

    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
        messages = results.get('messages', [])
    except HttpError as error:
        print(f'An error occurred: {error}')
        return

    emails_data = []
    for msg in messages:
        data = extract_email_data(service, msg['id'])
        if data:
            data['summary'] = summarize_text(data['body'])
            emails_data.append(data)

    # Sort by date descending
    emails_data.sort(key=lambda x: x['date'], reverse=True)

    # Write to CSV
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Sender Email', 'Date', 'Subject', 'Summary'])
        for email in emails_data:
            writer.writerow([
                email['sender'],
                email['date'].strftime('%Y-%m-%d %H:%M:%S'),
                email['subject'],
                email['summary']
            ])

    print(f'✅ {len(emails_data)} emails processed and saved to {CSV_FILE}')

if __name__ == '__main__':
    main()
