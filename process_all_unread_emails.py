import base64
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import pprint as pp

import fire
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from openai import OpenAI
from tqdm.auto import tqdm

# If modifying these SCOPES, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
_here = Path(__file__).parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filename=_here / "LOG-process_all_unread_emails.log",
    filemode="a",
)


def get_gmail_service(
    authorized_user_file: str = "token.json",
    credentials_file: str = "credentials.json",
):
    """
    Returns a Gmail service using the provided authorized user file and credentials
    file. If the authorized user file exists, it uses the stored credentials;
    otherwise, it prompts the user to log in and saves the obtained credentials
    for future use. Returns the Gmail service.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(authorized_user_file):
        creds = Credentials.from_authorized_user_file(authorized_user_file, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(authorized_user_file, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_emails(
    gmail: Resource, page_token: Optional[str]
) -> Tuple[List[Dict[str, Union[str, List[str]]]], Optional[str]]:
    """
    Fetch emails from the Gmail API using the provided page token.

    Args:
        gmail (Resource): The Gmail API resource object.
        page_token (str): The page token for fetching the next page of emails.

    Returns:
        Tuple[List[Dict[str, Union[str, List[str]]]], Optional[str]]: A tuple containing a list of email messages
        and an optional page token for fetching the next page of emails.
    """
    try:
        results = (
            gmail.users()
            .messages()
            .list(
                userId="me",
                labelIds=["UNREAD"],
                pageToken=page_token,  # Include the page token in the request if there is one
            )
            .execute()
        )
    except Exception as e:
        logging.error(f"Failed to fetch emails: {e}")
        return [], None

    messages: List[Dict[str, Union[str, List[str]]]] = results.get("messages", [])
    page_token = results.get("nextPageToken")
    return messages, page_token


def parse_email_data(
    gmail: Resource, message_info: Dict[str, Union[str, List[str]]]
) -> Dict[str, Union[str, List[str]]]:
    """
    Parses email data from a Gmail message and returns a dictionary containing subject, to, from, cc, labels, and body.

    Args:
        gmail (Resource): The Gmail resource to fetch email data.
        message_info (Dict[str, Union[str, List[str]]]): Information about the email message.

    Returns:
        Dict[str, Union[str, List[str]]]: A dictionary containing parsed email data.
    """
    # Fetch email data with 'full' format
    try:
        msg = (
            gmail.users()
            .messages()
            .get(userId="me", id=message_info["id"], format="full")
            .execute()
        )
    except Exception as e:
        logging.error(f"Failed to fetch email data: {e}")
        return {}

    try:
        headers = msg["payload"]["headers"]
        subject = next(
            header["value"] for header in headers if header["name"] == "Subject"
        )
        to = next(header["value"] for header in headers if header["name"] == "To")
        sender = next(header["value"] for header in headers if header["name"] == "From")
        cc = next(
            (header["value"] for header in headers if header["name"] == "Cc"), None
        )
    except Exception as e:
        logging.error(f"Failed to parse email data: {e}")
        return {}

    logging.debug(f"Fetched email - Subject: {subject}, Sender: {sender}")

    # Extract the plain text body
    parts = msg["payload"].get("parts", [])
    for part in parts:
        if part["mimeType"] == "text/plain":
            body = part["body"].get("data", "")
            body = base64.urlsafe_b64decode(body.encode("ASCII")).decode("utf-8")
            break
    else:
        body = ""

    # Parse email data
    email_data_parsed: Dict[str, Union[str, List[str]]] = {
        "subject": subject,
        "to": to,
        "from": sender,
        "cc": cc,
        "labels": msg["labelIds"],
        "body": body,
    }
    return email_data_parsed


def evaluate_email(
    email_data: Dict[str, Union[str, List[str]]],
    user_first_name: str,
    user_last_name: str,
    client: OpenAI,
    model: str = "gpt-4o",
    MAX_EMAIL_LEN: int = 5000,
) -> bool:
    """
    evaluate_email - Evaluates an email for whether it is worth the time with an LLM

    :param Dict[str, Union[str, List[str]]] email_data: object containing email data
    :param str user_first_name: first name of the user
    :param str user_last_name: last name of the user
    :param OpenAI client: OpenAI client object
    :param str model: GPT-4 model to use for evaluation, defaults to "gpt-4o"
    :param int MAX_EMAIL_LEN: maximum length of the email, defaults to 5000 characters
    :return bool: True if email should be marked as read, False otherwise
    """
    system_message: Dict[str, str] = {
        "role": "system",
        "content": (
            f"As an AI assistant, your task is to manage the Gmail inbox of {user_first_name} {user_last_name} "
            "by identifying promotional emails, unimportant notifications, and filler content in their personal account. "
            "Your primary goal is to ensure that personal communications and important messages are not mistakenly filtered out.\n\n"
            'Respond with "True" if the email should be marked as read (promotional/automated/unimportant), or "False" if it '
            "should remain unread (personal/important).\n\n"
            "Email Classification Process:\n"
            "1. Sender Analysis:\n"
            f"   - If the sender's name includes '{user_last_name}' or is a known acquaintance, likely personal.\n"
            "   - Check if the sender's email is from a personal domain (e.g., gmail.com, outlook.com) vs. a company domain.\n"
            "2. Subject Line Review:\n"
            "   - Look for promotional keywords like 'offer', 'discount', 'sale', 'newsletter'.\n"
            "   - Identify notification-type subjects like 'Your daily summary', 'New post from...', 'You have new likes'.\n"
            "   - Personal subjects often include names, personal references, or specific non-promotional topics.\n"
            "3. Email Body Examination:\n"
            f"   - Personal emails often address {user_first_name} by name and contain personalized content.\n"
            "   - Promotional emails typically have generic greetings and focus on products/services.\n"
            "   - Notifications often contain updates that don't require immediate action.\n"
            "4. Consider Context and Importance:\n"
            "   - Emails requiring action (e.g., Venmo payments, account verifications) should not be marked as read.\n"
            "   - Emails from critical sources (banks, government, schools) should remain unread.\n"
            "   - Routine notifications from social media, apps, or services can often be marked as read.\n\n"
            "Examples of Emails to Mark as Read (True):\n"
            "- Promotional: 'Your Weekly Newsletter from XYZ', 'Flash Sale: 50% Off Today Only!'\n"
            "- Notifications: 'Your daily LinkedIn update', 'New followers on Twitter', 'Your screen time report'\n"
            "- Filler Content: 'Check out what's new on our platform', 'Your monthly horoscope is ready'\n"
            "- Automated: Emails from 'noreply@' addresses, 'Your order has shipped' (unless it's a high-value item)\n\n"
            "Examples of Emails to Keep Unread (False):\n"
            f"- 'Dinner plans for Saturday?' from a '{user_last_name}' family member\n"
            "- 'Your account statement is ready' from a bank\n"
            f"- 'Following up on our conversation' addressed specifically to {user_first_name}\n"
            "- 'Action required: Verify your account' from a critical service\n"
            "- Emails mentioning shared experiences or containing personal questions/information\n"
            "- 'Your prescription is ready for pickup' from a pharmacy\n\n"
            "Additional Guidelines:\n"
            "- Mark as read recurring notifications that don't typically require action (e.g., weekly app usage summaries).\n"
            "- Keep unread any notifications about account security, payments, or important updates to services.\n"
            "- For subscriptions or newsletters, consider the value and frequency. High-value, low-frequency content "
            "might be worth keeping unread, while daily updates from the same source could be marked as read.\n"
            "- Be cautious with emails from professional networks or job-related services, as these might contain "
            "important opportunities.\n\n"
            "When in doubt, err on the side of caution and respond with 'False' to avoid missing important communications.\n\n"
            "The email information will be provided in this format:\n"
            "Subject: <email subject>\n"
            "To: <to names, to emails>\n"
            "From: <from name, from email>\n"
            "Cc: <cc names, cc emails>\n"
            "Gmail labels: <labels>\n"
            "Body: <plaintext body of the email>\n\n"
            'Your response must be only "True" or "False".'
        ),
    }

    # Check if 'body' key exists
    if "body" in email_data:
        truncated_body = email_data["body"][:MAX_EMAIL_LEN] + (
            "..." if len(email_data["body"]) > MAX_EMAIL_LEN else ""
        )
    else:
        logging.error(f"No 'body' key in email data - {pp.pformat(email_data)}")
        return False

    truncated_body = email_data["body"][:MAX_EMAIL_LEN] + (
        "..." if len(email_data["body"]) > MAX_EMAIL_LEN else ""
    )
    user_message: Dict[str, str] = {
        "role": "user",
        "content": (
            f"Subject: {email_data['subject']}\n"
            f"To: {email_data['to']}\n"
            f"From: {email_data['from']}\n"
            f"Cc: {email_data['cc']}\n"
            f"Gmail labels: {email_data['labels']}\n"
            f"Body: {truncated_body}"
        ),
    }

    # Send the messages to GPT-4, TODO add retry logic
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[system_message, user_message],
            max_tokens=1,
            temperature=0.0,
        )
    except Exception as e:
        logging.error(f"Failed to evaluate email with {model}: {e}")
        return False

    # Extract and return the response
    return completion.choices[0].message.content.strip() == "True"


def process_email(
    gmail: Resource,
    message_info: Dict[str, Union[str, List[str]]],
    email_data_parsed: Dict[str, Union[str, List[str]]],
    user_first_name: str,
    user_last_name: str,
    client: OpenAI,
    model: str = "gpt-4o",
) -> int:
    """
    process_email - Processes an email and marks it as read if it is not worth the time.

    :param Resource gmail: gmail resource object
    :param Dict[str, Union[str, List[str]]] message_info: email message info
    :param Dict[str, Union[str, List[str]]] email_data_parsed: parsed email data from Gmail
    :param str user_first_name: first name of the user
    :param str user_last_name: last name of the user
    :param OpenAI client: OpenAI client
    :param str model: GPT-4 model to use for evaluation, defaults to "gpt-4o"
    :return int: 1 if email is marked as read, 0 otherwise
    """

    # Safely get subject and sender with fallbacks
    subject = email_data_parsed.get("subject", "No Subject")
    sender = email_data_parsed.get("from", "Unknown Sender")

    subject_snippet = (subject[:50] + "...") if len(subject) > 50 else subject

    # Evaluate email
    if evaluate_email(
        email_data_parsed, user_first_name, user_last_name, client, model=model
    ):
        logging.info(
            f"Email '{subject_snippet}' from '{sender}' is not worth the time, marking as read"
        )
        # Remove UNREAD label
        try:
            gmail.users().messages().modify(
                userId="me", id=message_info["id"], body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            logging.debug("Email marked as read successfully")
            return 1
        except Exception as e:
            logging.error(f"Failed to mark email as read: {e}")
    else:
        logging.info(
            f"Email '{subject_snippet}' from '{sender}' is worth the time, leaving as unread"
        )
    return 0


def report_statistics(
    total_unread_emails: int, total_pages_fetched: int, total_marked_as_read: int
) -> None:
    logging.info(
        f"Total number of unread emails fetched: {total_unread_emails}\n"
        f"Total number of pages fetched: {total_pages_fetched}\n"
        f"Total number of emails marked as read: {total_marked_as_read}\n"
        f"Final number of unread emails: {total_unread_emails - total_marked_as_read}\n"
    )


def main(
    user_first_name: str,
    user_last_name: str,
    authorized_user_file: str = "token.json",
    credentials_file: str = "credentials.json",
    model: str = "gpt-4o",
):
    """
    Main function to process emails for a user.

    Args:
    user_first_name (str): The first name of the user.
    user_last_name (str): The last name of the user.
    authorized_user_file (str, optional): The file containing authorized user information. Defaults to "token.json".
    credentials_file (str, optional): The file containing user credentials. Defaults to "credentials.json".
    model (str, optional): The model to be used for processing emails. Defaults to "gpt-4o".
    """

    logging.info(f"Processing emails for {user_first_name} {user_last_name}")
    gmail = get_gmail_service(authorized_user_file, credentials_file)

    logging.info(f"Using model: {model}")
    client = OpenAI()

    page_token: Optional[str] = None

    total_unread_emails = 0
    total_pages_fetched = 0
    total_marked_as_read = 0

    while True:  # Continue looping until no more pages of messages
        # Fetch unread emails
        messages, page_token = fetch_emails(gmail, page_token)
        total_pages_fetched += 1
        logging.debug(f"Fetched page {total_pages_fetched} of emails")

        total_unread_emails += len(messages)
        for message_info in tqdm(messages, desc="Processing emails"):
            # TODO process emails on a single page in parallel
            # Fetch and parse email data
            email_data_parsed = parse_email_data(gmail, message_info)

            # Process email
            total_marked_as_read += process_email(
                gmail,
                message_info,
                email_data_parsed,
                user_first_name,
                user_last_name,
                client,
                model=model,
            )

        if not page_token:
            logging.info("No more pages of messages, exiting...")
            break

    report_statistics(total_unread_emails, total_pages_fetched, total_marked_as_read)
    logging.info("Finished processing emails")


if __name__ == "__main__":
    fire.Fire(main)
