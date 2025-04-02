import os
import smtplib
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from .env
load_dotenv()

# Get email credentials
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

def send_test_email():
    try:
        # Create email message
        message = MIMEMultipart()
        message["From"] = EMAIL_ADDRESS
        message["To"] = ALERT_EMAIL
        message["Subject"] = "Test Email from FastAPI"

        body = "Hello! This is a test email from your FastAPI app."
        message.attach(MIMEText(body, "plain"))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()  # Secure the connection
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

        # Send the email
        server.sendmail(EMAIL_ADDRESS, ALERT_EMAIL, message.as_string())
        server.quit()

        print(f"✅ Test email sent successfully to {ALERT_EMAIL}!")
    except Exception as e:
        print(f"❌ Error sending test email: {e}")

# Run the test
send_test_email()
