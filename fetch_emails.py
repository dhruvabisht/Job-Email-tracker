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

# Update these lists as needed:
INCLUDE_SENDERS = [
    'myworkday.com', 'successfactors.eu', 'recruiting.honeywell.com', 'deptagency.com',
    'talentupdates@recruiting.honeywell.com', 'productsdc12pm.successfactors.eu',
    'notification_from_people_services@mastercard.com', 'fragomen@myworkday.com',
    'jasna.tanevska@deptagency.com', 'correspondencethegreatwep3@productsdc12pm.successfactors.eu'
]
EXCLUDED_SENDERS = [
    'linkedin.com', 'indeed.com', 'job alerts', 'noreply@linkedin.com', 'noreply@indeed.com',
    'jobs-listings@linkedin.com', 'messaging-digest-noreply@linkedin.com',
    'khanacademy.org', 'jobscan.co', 'aib.ie', 'hec.edu', 'geu.ac.in', 'talentoutreach', 'perfume shop', 'glanbia.com'
]
INCLUDE_KEYWORDS = [
    'application submitted', 'application received', 'interview', 'assessment', 'offer',
    'rejected', 'not selected', 'next steps', 'unfortunately', 'thank you for applying',
    'status update', 'decision', 'scheduled', 'invitation', 'progress', 'update',
    'hiring process', 'move forward with other candidates', 'invited', 'video assessment',
    'online assessment', 'one-way interview', 'congratulations', 'selected', 'shortlisted'
]
EXCLUDED_KEYWORDS = [
 'newsletter', 'report', 'deals', 'open for', 'meet your', 'explained', 'thank you for visiting', 'new jobs posted', 'digest', 'father\'s day', 'mba', 'alumn', 'academy', 'match report', 'explained', 'open for', 'meet your', 'explained', 'thank you for visiting', 'new jobs posted', 'digest', 'father\'s day', 'mba', 'alumn', 'academy', 'match report'
]

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

# Helper to check if email is relevant
def is_relevant_email(email_data):
    sender = email_data['sender'].lower()
    subject = email_data['subject'].lower()
    body = email_data['body'].lower()
    if any(excluded in sender for excluded in EXCLUDED_SENDERS):
        return False
    if any(keyword in subject or keyword in body for keyword in EXCLUDED_KEYWORDS):
        return False
    if any(included in sender for included in INCLUDE_SENDERS):
        return True
    if any(keyword in subject or keyword in body for keyword in INCLUDE_KEYWORDS):
        return True
    return False

# Helper to check if email is a next-stage/interview email
NEXT_STAGE_KEYWORDS = [
    'progress', 'next stage', 'interview', 'assessment', 'invited', 'invitation', 'one-way interview', 'video assessment', 'shortlisted', 'move forward'
]
def is_next_stage_email(email_data):
    subject = email_data['subject'].lower()
    body = email_data['body'].lower()
    return any(keyword in subject or keyword in body for keyword in NEXT_STAGE_KEYWORDS)

# --- OpenAI API update ---
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def summarize_text(text, subject=None, sender=None):
    if not OPENAI_API_KEY:
        return "(Summary disabled - OPENAI_API_KEY not set)"
    if not text or len(text.strip()) < 30:
        return "(Too short to summarize)"
    email_hash = sha256(text.strip().encode('utf-8')).hexdigest()
    if email_hash in summary_cache:
        return summary_cache[email_hash]
    try:
        prompt = (
            "You are an assistant that summarizes job application emails. "
            "Given the email content, sender, and subject, generate a concise summary in this format: "
            "- For application submission: 'Application submitted to {company} ({role})'\n"
            "- For rejection: 'Rejected from {company} for {role}'\n"
            "- For next stage/interview: 'Selected for next stage at {company} for {role} (complete by {date})'\n"
            "If a deadline is mentioned, include it. If you can't find company or role, use placeholders."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Sender: {sender}\nSubject: {subject}\nEmail: {text[:2000]}"}
        ]
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=100,
            temperature=0.3
        )
        summary = response.choices[0].message.content.strip()
        summary_cache[email_hash] = summary
        return summary
    except Exception as e:
        print("OpenAI API error:", e)
        return f"(Summary failed: {e})"

# =========== MAIN LOGIC =============
def main():
    service = get_gmail_service()
    query = ''  # Fetch all, filter in Python
    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
        messages = results.get('messages', [])
    except HttpError as error:
        print(f'An error occurred: {error}')
        return
    emails_data = []
    for msg in messages:
        data = extract_email_data(service, msg['id'])
        if data and is_relevant_email(data):
            data['highlight'] = is_next_stage_email(data)
            data['summary'] = summarize_text(data['body'], data['subject'], data['sender'])
            emails_data.append(data)
    emails_data.sort(key=lambda x: x['date'], reverse=True)
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Sender Email', 'Date', 'Subject', 'Summary', 'Highlight'])
        for email in emails_data:
            writer.writerow([
                email['sender'],
                email['date'].strftime('%Y-%m-%d %H:%M:%S'),
                email['subject'],
                email['summary'],
                'yes' if email.get('highlight') else ''
            ])
    print(f'✅ {len(emails_data)} emails processed and saved to {CSV_FILE}')

if __name__ == '__main__':
    main()
