"""
email_sender.py - SMTP (Gmail) でメールを送信
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MY_NAME


def send_email(to_address: str, subject: str, body: str) -> bool:
    """
    メールを送信する。
    成功: True / 失敗: False
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  [SKIP] Gmail設定がありません (GMAIL_ADDRESS / GMAIL_APP_PASSWORD)")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{MY_NAME} <{GMAIL_ADDRESS}>"
        msg["To"]      = to_address

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_address, msg.as_string())

        print(f"  [OK]   {to_address} へメール送信完了")
        return True

    except Exception as e:
        print(f"  [ERR]  {to_address} : {e}")
        return False
