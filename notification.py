import smtplib
import logging
import requests
import json
from typing import List, Optional
from datetime import datetime, time

class NotificationError(Exception):
    pass

def send_email(receivers, smtp_host, smtp_port, subject, msg, retries=3):
    sender = "awx_prd@comcast.com"
    receivers = receivers  # Ensure this is a list of email addresses

    smtpHost = smtp_host
    smtpPort = smtp_port
    subject = subject

    # Construct the email message with proper UTF-8 encoding
    message = ("From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n"
               % (sender, ", ".join(receivers), subject))
    message += msg

    # Encode the message in UTF-8
    message = message.encode('utf-8')

    for attempt in range(retries):
        try:
            # Log the SMTP server and port being used
            logging.debug(f"Attempting to connect to SMTP server: {smtp_host}:{smtp_port} (Attempt {attempt + 1})")

            # Connect to the SMTP server
            smtp = smtplib.SMTP(smtpHost, smtpPort, timeout=10)
            smtp.set_debuglevel(2)  # Enable debug output
            smtp.ehlo()  # Identify yourself to the SMTP server

            # Log the sender, receivers, and message
            logging.debug(f"Sender: {sender}")
            logging.debug(f"Receivers: {receivers}")
            logging.debug(f"Message: {message.decode('utf-8')}")  # Decode for logging

            # Send the email
            smtp.sendmail(sender, receivers, message)
            smtp.quit()
            logging.info("Successfully sent email")
            return "Success"
        except smtplib.SMTPConnectError as e:
            logging.error(f"Failed to connect to SMTP server: {e}")
            if attempt < retries - 1:
                time.sleep(5)  # Wait for 5 seconds before retrying
                continue
            return "Failed"
        except smtplib.SMTPException as e:
            logging.error(f"SMTP error occurred: {e}")
            return "Failed"
        except Exception as e:
            logging.error(f"Unexpected error occurred: {e}")
            return "Failed"


def send_slack_notification(job_id, job_url, job_name, started_at):
    webhook_url = "https://hooks.slack.com/services/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"
    proxy = {
        "http": "http://cxscorpproxy.comcast.net:3128",
        "https": "http://cxscorpproxy.comcast.net:3128"
    }
    
    # Format the timestamp for a professional look
    started_at_formatted = datetime.fromisoformat(started_at).strftime("%Y-%m-%d %H:%M:%S")
    
    # Create a professional and business-oriented message
    message = (
        f":white_check_mark: *AWX Job Notification* :white_check_mark:\n\n"
        f"*Job Name:* {job_name}\n"
        f"*Job ID:* {job_id}\n"
        f"*Started At:* {started_at_formatted}\n\n"
        f"The job has completed successfully. For more details, please review the logs:\n"
        f"{job_url}"
    )
    
    payload = {
        "channel": "efv-infra",
        "username": "efv-infra-bot",
        "text": message,
        "icon_emoji": ":robot_face:"
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers, proxies=proxy)
        response.raise_for_status()
        print("Notification sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send notification: {e}")


def send_failslack_notification(job_id, job_url, job_name, started_at, failed_output):
    webhook_url = "https://hooks.slack.com/services/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"
    proxy = {
        "http": "http://cxscorpproxy.comcast.net:3128",
        "https": "http://cxscorpproxy.comcast.net:3128"
    }
    
    # Format the timestamp for a professional look
    started_at_formatted = datetime.fromisoformat(started_at).strftime("%Y-%m-%d %H:%M:%S")
    
    message = (
        f":x: *AWX Job Notification* :x:\n\n"
        f"*Job Name:* {job_name}\n"
        f"*Job ID:* {job_id}\n"
        f"*Started At:* {started_at_formatted}\n\n"
        f":x: *FAILED* :x: The job has failed. For more details, please review the logs:\n"
        f"{job_url}\n\n"
        f"*Failed Output:*\n"
        f"```{failed_output}```"  # Use triple backticks for code formatting in Slack
    )
    
    payload = {
        "channel": "efv-infra",
        "username": "efv-infra-bot",
        "text": message,
        "icon_emoji": ":robot_face:"
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers, proxies=proxy)
        response.raise_for_status()
        print("Notification sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send notification: {e}")