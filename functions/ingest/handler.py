import json
import uuid
import os
import re
from datetime import datetime, timedelta, timezone

import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
ses = boto3.client("ses")

SENDER_EMAIL = os.environ["SENDER_EMAIL"]

# ── Validation constants ──────────────────────────────────
MIN_CHECKIN_DAYS = 7
MAX_CHECKIN_DAYS = 1825       # ~5 years
MAX_PLAN_DURATION_DAYS = 3650 # ~10 years
MAX_RESOLUTIONS = 20
MAX_RESOLUTION_LEN = 500
MAX_NAME_LEN = 100
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _respond(status_code: int, body: dict) -> dict:
    """Build an API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _validate(data: dict) -> str | None:
    """Return an error message string, or None if valid."""
    # Required fields
    for field in ("name", "email", "resolutions", "checkInDays", "planDurationDays"):
        if field not in data:
            return f"Missing required field: {field}"

    # Name
    name = data["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_NAME_LEN:
        return f"name must be 1-{MAX_NAME_LEN} characters"

    # Email
    email = data["email"]
    if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
        return "Invalid email address"

    # Resolutions
    resolutions = data["resolutions"]
    if not isinstance(resolutions, list) or not 1 <= len(resolutions) <= MAX_RESOLUTIONS:
        return f"resolutions must be an array of 1-{MAX_RESOLUTIONS} items"
    for i, r in enumerate(resolutions):
        if not isinstance(r, str) or not 1 <= len(r.strip()) <= MAX_RESOLUTION_LEN:
            return f"Resolution #{i+1} must be 1-{MAX_RESOLUTION_LEN} characters"

    # Check-in frequency
    check_in_days = data["checkInDays"]
    if not isinstance(check_in_days, (int, float)) or not MIN_CHECKIN_DAYS <= int(check_in_days) <= MAX_CHECKIN_DAYS:
        return f"checkInDays must be between {MIN_CHECKIN_DAYS} and {MAX_CHECKIN_DAYS}"

    # Plan duration
    plan_duration_days = data["planDurationDays"]
    if not isinstance(plan_duration_days, (int, float)):
        return "planDurationDays must be a number"
    if int(plan_duration_days) < int(check_in_days):
        return "planDurationDays must be >= checkInDays"
    if int(plan_duration_days) > MAX_PLAN_DURATION_DAYS:
        return f"planDurationDays must be <= {MAX_PLAN_DURATION_DAYS}"

    return None


def lambda_handler(event, context):
    """Handle POST /capsules — seal a new message for posterity."""
    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return _respond(200, {"message": "OK"})

    # Parse body
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _respond(400, {"error": "Invalid JSON body"})

    # Validate
    error = _validate(body)
    if error:
        return _respond(400, {"error": error})

    # Extract & sanitise
    name = body["name"].strip()
    email = body["email"].strip().lower()
    check_in_days = int(body["checkInDays"])
    plan_duration_days = int(body["planDurationDays"])

    now = datetime.now(timezone.utc)
    capsule_id = str(uuid.uuid4())

    # Build resolution checklist items
    resolutions = []
    for text in body["resolutions"]:
        resolutions.append({
            "id": str(uuid.uuid4()),
            "text": text.strip(),
            "completed": False,
        })

    next_check_in = (now + timedelta(days=check_in_days)).strftime("%Y-%m-%d")
    ends_at = (now + timedelta(days=plan_duration_days)).strftime("%Y-%m-%d")

    item = {
        "capsuleId": capsule_id,
        "name": name,
        "email": email,
        "resolutions": resolutions,
        "checkInDays": check_in_days,
        "planDurationDays": plan_duration_days,
        "nextCheckIn": next_check_in,
        "endsAt": ends_at,
        "createdAt": now.isoformat(),
        "lastCheckIn": None,
        "checkInCount": 0,
        "status": "active",
    }

    table.put_item(Item=item)

    # Send the initial welcome email
    _send_welcome_email(item)

    return _respond(201, {
        "message": "Your message has been sealed for posterity.",
        "capsuleId": capsule_id,
        "nextCheckIn": next_check_in,
        "endsAt": ends_at,
        "totalCheckIns": plan_duration_days // check_in_days,
    })


def _build_checklist_html(resolutions: list[dict]) -> str:
    """Render the resolution checklist as HTML with Windows 95 styling."""
    items = []
    for r in resolutions:
        text = r.get("text", "")
        items.append(
            f'<li style="margin: 6px 0; font-size: 13px; color: #000000; list-style-type: none;">⬜ {text}</li>'
        )
    return f'<ul style="margin: 0; padding: 0;">{"".join(items)}</ul>'


def _build_welcome_email_html(capsule: dict) -> str:
    """Build the HTML body for the initial confirmation email with Win95 aesthetic."""
    name = capsule["name"]
    created_at = capsule["createdAt"][:10]
    ends_at = capsule.get("endsAt", "N/A")
    next_check_in = capsule.get("nextCheckIn", "N/A")
    check_in_days = int(capsule["checkInDays"])
    total_check_ins = int(capsule["planDurationDays"]) // check_in_days
    resolutions = capsule.get("resolutions", [])

    checklist_html = _build_checklist_html(resolutions)

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
                            Posterity - Message Sealed
                        </div>

                        <!-- Window Content -->
                        <div style="padding: 14px; font-size: 13px; color: #000000; line-height: 1.5;">
                            <h2 style="margin: 0 0 4px 0; font-size: 16px; color: #000080;">
                                Your message has been sealed.
                            </h2>
                            <p style="margin: 0 0 12px 0; font-size: 11px; color: #555555;">
                                Sealed on {created_at} &bull; Ends {ends_at} &bull; {total_check_ins} check-ins scheduled
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
                                    Your message has been sealed for posterity.
                                </p>
                                <p style="margin: 0 0 10px 0; font-style: italic; color: #333333; border-left: 3px solid #000080; padding-left: 8px;">
                                    &ldquo;Some words are meant for who you are today. Others are meant for who you will become.&rdquo;
                                </p>
                                <p style="margin: 0;">
                                    We will check in on you every <strong>{check_in_days} days</strong>. Your first reminder arrives on <strong>{next_check_in}</strong>.
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


def _send_welcome_email(capsule: dict) -> None:
    """Send the initial confirmation email when a message is first sealed."""
    name = capsule["name"]
    email = capsule["email"]
    subject = f"Your message has been sealed for posterity, {name}."
    html_body = _build_welcome_email_html(capsule)

    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(f"Welcome email sent to {email} for message {capsule['capsuleId']}")
    except Exception as e:
        # Log but don't fail message creation — the data is already saved
        logger.error(f"Failed to send welcome email to {email}: {e}")
