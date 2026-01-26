import smtplib
import ssl
import os
from email.message import EmailMessage
from typing import List, Optional
import mimetypes

class SESClient:
    # Default SES settings for us-east-1
    DEFAULT_SMTP_SERVER = "email-smtp.us-east-1.amazonaws.com"
    DEFAULT_SMTP_PORT = 465

    def __init__(self):
        self.smtp_username = os.getenv('SES_SMTP_USERNAME')
        self.smtp_password = os.getenv('SES_SMTP_PASSWORD')
        self.smtp_server = os.getenv('SES_SMTP_SERVER', self.DEFAULT_SMTP_SERVER)
        self.smtp_port = int(os.getenv('SES_SMTP_PORT', self.DEFAULT_SMTP_PORT))
        self.from_email = os.getenv('SES_FROM_EMAIL')

        if not all([self.smtp_username, self.smtp_password, self.from_email]):
             print("Warning: SES credentials (SES_SMTP_USERNAME, SES_SMTP_PASSWORD, SES_FROM_EMAIL) not found. Email sending will fail unless in dryrun mode.")

    def send_email(self, to: List[str], subject: str, text: str, attachment_path: Optional[str] = None, dryrun: bool = False):
        if dryrun:
            print(f"[DRYRUN] Sending email to {to}")
            print(f"[DRYRUN] From: {self.from_email}")
            print(f"[DRYRUN] Subject: {subject}")
            print(f"[DRYRUN] Text: {text}")
            if attachment_path:
                print(f"[DRYRUN] Attachment: {attachment_path}")
            return

        if not all([self.smtp_username, self.smtp_password, self.from_email]):
            raise ValueError("SES credentials are required to send emails.")

        # Create the email message
        msg = EmailMessage()
        msg["From"] = self.from_email
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        msg.set_content(text)

        # Add attachment if provided
        if attachment_path:
            # Guess the content type based on the file's extension
            ctype, encoding = mimetypes.guess_type(attachment_path)
            if ctype is None or encoding is not None:
                # No guess could be made, or the file is encoded (compressed), so
                # use a generic bag-of-bits type.
                ctype = 'application/octet-stream'
            
            maintype, subtype = ctype.split('/', 1)
            
            with open(attachment_path, 'rb') as f:
                file_data = f.read()
                msg.add_attachment(
                    file_data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=os.path.basename(attachment_path)
                )

        # Create an SSL context and establish a connection with the SES SMTP server
        context = ssl.create_default_context()

        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                server.login(self.smtp_username, self.smtp_password)
                response = server.send_message(msg)
                print(f"Email sent response: {response}")
                print(f"Email sent successfully to {to}")
        except Exception as e:
            print(f"Error sending email via SES: {e}")
            raise
