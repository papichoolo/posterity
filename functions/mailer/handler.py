import json
import os
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

SENDER_EMAIL = os.environ["SENDER_EMAIL"]
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
GSI_NAME = "StatusNextCheckInIndex"


def _build_checklist_html(resolutions: list[dict]) -> str:
    """Render the resolution checklist as HTML with Windows 95 styling."""
    items = []
    for r in resolutions:
        icon = "✅" if r.get("completed") else "⬜"
        text = r.get("text", "")
        style = "text-decoration: line-through; color: #666;" if r.get("completed") else "color: #000;"
        items.append(
            f'<li style="margin: 6px 0; font-size: 13px; list-style-type: none;">{icon} <span style="{style}">{text}</span></li>'
        )
    return f'<ul style="margin: 0; padding: 0;">{"".join(items)}</ul>'


def _build_email_html(capsule: dict, is_final: bool = False) -> str:
    """Build the full HTML email body with Windows 95 styling."""
    name = capsule["name"]
    check_in_count = capsule.get("checkInCount", 0) + 1
    created_at = capsule["createdAt"][:10]  # YYYY-MM-DD
    ends_at = capsule.get("endsAt", "N/A")
    resolutions = capsule.get("resolutions", [])

    # Calculate days since creation
    created_dt = datetime.fromisoformat(capsule["createdAt"])
    days_elapsed = (datetime.now(timezone.utc) - created_dt).days

    checklist_html = _build_checklist_html(resolutions)

    if is_final:
        title_bar_text = "Posterity - Message Delivered"
        heading = "Your message has arrived."
        subheading = f"Final Check-in &bull; Sealed on {created_at} &bull; {days_elapsed} days completed"
        quote = "&ldquo;The future you wrote to is now the present.&rdquo;"
        lead_text = f"<strong>{days_elapsed} days</strong> have passed since you sealed your message on <strong>{created_at}</strong>."
        closing_text = "Here is what you started with:"
    else:
        title_bar_text = f"Posterity - Check-In #{check_in_count}"
        heading = "Time moves forward."
        subheading = f"Check-in #{check_in_count} &bull; Sealed on {created_at} &bull; Ends {ends_at}"
        quote = "&ldquo;Are you closer to what you promised, or did time change the direction?&rdquo;"
        lead_text = f"It has been <strong>{days_elapsed} days</strong> since you sealed this message on <strong>{created_at}</strong>."
        closing_text = "Take a look at what you set out to do:"

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="
        margin: 0; padding: 24px;
        background-color: #008080;
        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    ">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
                <td align="center">
                    <div style="
                        max-width: 520px;
                        background-color: #c0c0c0;
                        border-top: 2px solid #ffffff;
                        border-left: 2px solid #ffffff;
                        border-right: 2px solid #000000;
                        border-bottom: 2px solid #000000;
                        padding: 2px;
                        text-align: left;
                        box-shadow: 2px 2px 0px rgba(0,0,0,0.5);
                    ">
                        <!-- Title Bar -->
                        <div style="
                            background: #000080;
                            color: #ffffff;
                            padding: 4px 6px;
                            font-weight: bold;
                            font-size: 12px;
                            letter-spacing: 0.5px;
                        ">
                            {title_bar_text}
                        </div>

                        <!-- Window Content -->
                        <div style="padding: 14px; font-size: 13px; color: #000000; line-height: 1.5;">
                            <h2 style="margin: 0 0 4px 0; font-size: 16px; color: #000080;">
                                {heading}
                            </h2>
                            <p style="margin: 0 0 12px 0; font-size: 11px; color: #555555;">
                                {subheading}
                            </p>

                            <div style="
                                border-top: 1px solid #808080;
                                border-left: 1px solid #808080;
                                border-right: 1px solid #ffffff;
                                border-bottom: 1px solid #ffffff;
                                background-color: #ffffff;
                                padding: 12px;
                                margin-bottom: 14px;
                            ">
                                <p style="margin: 0 0 10px 0;">
                                    Hi <strong>{name}</strong>,
                                </p>
                                <p style="margin: 0 0 10px 0;">
                                    {lead_text}
                                </p>
                                <p style="margin: 0 0 10px 0; font-style: italic; color: #333333; border-left: 3px solid #000080; padding-left: 8px;">
                                    {quote}
                                </p>
                                <p style="margin: 0;">
                                    {closing_text}
                                </p>
                            </div>

                            <!-- Resolutions Fieldset Box -->
                            <fieldset style="
                                border-top: 1px solid #ffffff;
                                border-left: 1px solid #ffffff;
                                border-right: 1px solid #808080;
                                border-bottom: 1px solid #808080;
                                padding: 10px;
                                margin: 0 0 14px 0;
                                background-color: #c0c0c0;
                            ">
                                <legend style="background-color: #c0c0c0; padding: 0 4px; font-weight: bold; font-size: 12px;">
                                    Your Resolutions
                                </legend>
                                <div style="
                                    background: #ffffff;
                                    border-top: 1px solid #808080;
                                    border-left: 1px solid #808080;
                                    border-right: 1px solid #ffffff;
                                    border-bottom: 1px solid #ffffff;
                                    padding: 10px;
                                ">
                                    {checklist_html}
                                </div>
                            </fieldset>

                            <!-- Status Bar -->
                            <div style="
                                border-top: 1px solid #808080;
                                border-left: 1px solid #808080;
                                border-right: 1px solid #ffffff;
                                border-bottom: 1px solid #ffffff;
                                padding: 3px 6px;
                                font-size: 11px;
                                color: #333333;
                                background-color: #d4d0c8;
                            ">
                                Posterity &mdash; Delivered across time.
                            </div>
                        </div>
                    </div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via Resend REST API. Returns True on success."""
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY is not configured in environment variables")
        return False

    url = "https://api.resend.com/emails"
    payload = json.dumps({
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Posterity/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201):
                resp_body = json.loads(resp.read().decode("utf-8"))
                logger.info(f"Check-in email sent via Resend to {to_email} (id: {resp_body.get('id')})")
                return True
            logger.error(f"Resend returned unexpected status code {resp.status}")
            return False
    except urllib.error.HTTPError as e:
        error_content = e.read().decode("utf-8")
        logger.error(f"Resend HTTP error {e.code} sending email to {to_email}: {error_content}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email via Resend to {to_email}: {e}")
        return False


def _get_due_capsules(today_str: str) -> list[dict]:
    """Query DynamoDB GSI for active capsules due for check-in."""
    capsules = []
    response = table.query(
        IndexName=GSI_NAME,
        KeyConditionExpression=(
            Key("status").eq("active") & Key("nextCheckIn").lte(today_str)
        ),
    )
    capsules.extend(response.get("Items", []))

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName=GSI_NAME,
            KeyConditionExpression=(
                Key("status").eq("active") & Key("nextCheckIn").lte(today_str)
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        capsules.extend(response.get("Items", []))

    return capsules


def lambda_handler(event, context):
    """Daily cron handler — check for due capsules and send emails."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    logger.info(f"Mailer invoked at {now.isoformat()}, checking for capsules due <= {today_str}")

    capsules = _get_due_capsules(today_str)
    logger.info(f"Found {len(capsules)} due capsule(s)")

    sent = 0
    failed = 0
    completed = 0

    for capsule in capsules:
        capsule_id = capsule["capsuleId"]
        email = capsule["email"]
        name = capsule["name"]
        check_in_days = int(capsule["checkInDays"])
        check_in_count = int(capsule.get("checkInCount", 0))
        ends_at = capsule.get("endsAt", "9999-12-31")

        # Check if the plan has expired
        is_final = ends_at <= today_str

        if is_final:
            # Send final summary email
            subject = f"The wait is over, {name}."
            html_body = _build_email_html(capsule, is_final=True)
            success = _send_email(email, subject, html_body)

            if success:
                # Mark as completed
                table.update_item(
                    Key={"capsuleId": capsule_id},
                    UpdateExpression="SET #s = :s, lastCheckIn = :lc, checkInCount = :cc",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": "completed",
                        ":lc": today_str,
                        ":cc": check_in_count + 1,
                    },
                )
                completed += 1
                logger.info(f"Message {capsule_id} completed for {email}")
            else:
                failed += 1
        else:
            # Send regular check-in email
            subject = f"A message from your past self — Check-in #{check_in_count + 1}, {name}"
            html_body = _build_email_html(capsule, is_final=False)
            success = _send_email(email, subject, html_body)

            if success:
                next_check_in = (now + timedelta(days=check_in_days)).strftime("%Y-%m-%d")
                table.update_item(
                    Key={"capsuleId": capsule_id},
                    UpdateExpression="SET nextCheckIn = :nc, lastCheckIn = :lc, checkInCount = :cc",
                    ExpressionAttributeValues={
                        ":nc": next_check_in,
                        ":lc": today_str,
                        ":cc": check_in_count + 1,
                    },
                )
                sent += 1
                logger.info(f"Check-in #{check_in_count + 1} sent to {email} for message {capsule_id}")
            else:
                failed += 1

    summary = {
        "date": today_str,
        "due": len(capsules),
        "sent": sent,
        "completed": completed,
        "failed": failed,
    }
    logger.info(f"Mailer summary: {json.dumps(summary)}")

    return summary
