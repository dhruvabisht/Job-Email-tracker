import base64
import re

def parse_email_content(msg):
    try:
        parts = msg['payload'].get('parts', [])
        for part in parts:
            if part['mimeType'] == 'text/plain':
                data = part['body']['data']
                decoded = base64.urlsafe_b64decode(data.encode('UTF-8')).decode('utf-8')
                return decoded
    except:
        return msg.get('snippet', '')
    return ''

def classify_email(text):
    text = text.lower()
    if 'interview' in text:
        return 'Interview Invite'
    elif 'rejected' in text:
        return 'Rejection'
    elif 'shortlisted' in text or 'selected' in text:
        return 'Shortlisted'
    elif 'offer' in text:
        return 'Offer'
    elif 'application received' in text:
        return 'Application Acknowledged'
    else:
        return 'Other'