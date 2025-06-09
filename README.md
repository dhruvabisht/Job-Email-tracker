# 📬 AI-Powered Job Email Tracker

Automatically scan your Gmail inbox for job-related emails — including interview invites, application acknowledgments, and offers — then view them in a beautifully filtered Streamlit dashboard.

---

## 🚀 Features

- 🔍 Filters Gmail emails using keywords and senders
- 🤖 AI-like rule-based email classification
- 📊 Streamlit dashboard to visualize your job emails
- 🕘 Automatically fetches latest emails every day at 9 PM Irish time (via GitHub Action)

---

## 🛠 Setup

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/job_email_tracker.git
cd job_email_tracker
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Enable Gmail API

- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a project > Enable Gmail API
- Download `client_secret.json` and place it in the root directory

### 4. Fetch Emails Locally (First Time)

```bash
python fetch_emails.py
```

### 5. Run the Dashboard

```bash
streamlit run dashboard.py
```

---

## 🌐 Streamlit Cloud Deployment

1. Push code (including `job_emails.csv`) to a GitHub repo
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Deploy `dashboard.py`
4. Optionally, update the CSV manually or automate it using GitHub Actions

---

## ⏰ Automatic Daily Updates at 9 PM Irish Time

Set up GitHub Actions to run `fetch_emails.py` daily and push `job_emails.csv`. Use a GitHub secret for your credentials or keep it manual for now.

---

## 📁 File Structure

```
job_email_tracker/
├── client_secret.json       # Your Gmail API credentials
├── fetch_emails.py          # Fetch and classify emails
├── utils.py                 # Helper functions
├── dashboard.py             # Streamlit dashboard
├── job_emails.csv           # Output CSV
└── requirements.txt         # Python dependencies
```

---

## 👨‍💻 Author

Built with ❤️ by Dhruva Bisht, a MSc CS student to never miss a job opportunity again.
