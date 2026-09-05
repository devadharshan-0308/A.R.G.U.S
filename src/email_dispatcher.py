"""
Direct Municipal Email Dispatcher
─────────────────────────────────
Natively dispatches official municipal road hazard alerts and PWD maintenance
work-order spreadsheets (CSV attachments) directly via Gmail SMTP.
Strictly configured to prevent spam flagging:
- RFC 5322 compliance (Date, Message-ID, MIME-Version)
- Sender header strictly aligned with Google account identity
- Standard multipart/alternative hierarchy (text + html)
- Clean text/csv attachment MIME typing
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
from typing import Any, Dict, Optional, Tuple, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("EmailDispatcher")

SMTP_HOST = "smtp.gmail.com"

# Standard verified identities
STANDARD_SENDER = "devadharshan03082006@gmail.com"
STANDARD_RECIPIENTS = [
    "corporationunicipal26@gmail.com"
]


def get_smtp_credentials() -> Tuple[str, str, List[str]]:
    sender = os.getenv("SMTP_SENDER_EMAIL", STANDARD_SENDER).strip()
    password = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
    recipients_raw = os.getenv("MUNICIPAL_DISPATCH_EMAIL", "")
    if recipients_raw:
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    else:
        recipients = list(STANDARD_RECIPIENTS)
    return sender, password, recipients


def _connect_smtp(sender: str, password: str, timeout: float = 7.0) -> smtplib.SMTP:
    """
    Connects to Gmail SMTP using dual-port fallback:
    First tries Port 465 (SSL). If blocked by network/firewall, falls back to Port 587 (STARTTLS).
    """
    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=timeout)
        server.login(sender, password)
        return server
    except Exception as e_ssl:
        logger.info(f"Port 465 SSL unavailable ({e_ssl}), falling back to Port 587 STARTTLS...")
        server = smtplib.SMTP(SMTP_HOST, 587, timeout=timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        return server


def send_pwd_workorder_email(
    summary: Dict[str, Any],
    csv_path: str,
    recipient_email: Optional[str] = None,
    bus_id: str = "TN-MTC-BUS-104"
) -> Tuple[bool, str]:
    """
    Sends the PWD civil maintenance work-order dossier and attached CSV
    directly to municipal authorities without asking for an email and without spam flagging.
    """
    sender, password, default_recipients = get_smtp_credentials()

    if recipient_email:
        target_emails = [r.strip() for r in recipient_email.split(",") if r.strip()]
    else:
        target_emails = default_recipients

    if not password:
        msg = "SMTP_APP_PASSWORD is not configured in .env."
        logger.warning(msg)
        return False, msg

    total_orders = summary.get("total_orders", 0)
    budget_inr = summary.get("total_budget_inr", 0)
    prios = summary.get("priority_counts", {})
    p1 = prios.get("P1 - CRITICAL", 0)
    p2 = prios.get("P2 - HIGH", 0)
    p3 = prios.get("P3 - MEDIUM", 0)

    # 1. Outer Container: multipart/mixed (required for attachments)
    msg = MIMEMultipart("mixed")
    msg["From"] = f"Devadharshan <{sender}>"
    msg["To"] = ", ".join(target_emails)
    msg["Reply-To"] = sender
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")
    msg["MIME-Version"] = "1.0"
    msg["Subject"] = f"PWD Road Maintenance Survey Report - Greater Chennai Corporation"

    # 2. Body Container: multipart/alternative (plain text + html)
    alt_part = MIMEMultipart("alternative")

    plain_text = (
        f"Dear Municipal Engineering Team,\n\n"
        f"An automated road distress survey has been completed by transit fleet unit {bus_id}.\n"
        f"Official municipal repair schedule compliant with Indian Road Congress (IRC) civil specifications.\n\n"
        f"SURVEY SUMMARY:\n"
        f"- Total Civil Work Orders: {total_orders} Orders\n"
        f"- Estimated Municipal Budget: INR {budget_inr:,}\n"
        f"- P1 Critical Priority (24h SLA): {p1} Defects\n"
        f"- P2 High Priority (48h SLA): {p2} Defects\n"
        f"- P3 Medium Priority (7d SLA): {p3} Defects\n\n"
        f"The complete IRC repair schedule spreadsheet is attached.\n\n"
        f"Regards,\n"
        f"Devadharshan\n"
        f"AI Urban Infrastructure Surveillance Team\n"
        f"Smart India Hackathon Prototype\n"
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.5; margin: 0; padding: 10px;">
  <div style="max-width: 620px; margin: auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background-color: #059669; color: #ffffff; padding: 18px 24px; text-align: center;">
      <h2 style="margin: 0; font-size: 18px; letter-spacing: 0.5px;">GREATER CHENNAI CORPORATION</h2>
      <p style="margin: 4px 0 0 0; font-size: 12px; letter-spacing: 1px;">MUNICIPAL PUBLIC WORKS DEPARTMENT (CIVIL ROADS & BRIDGES)</p>
    </div>

    <div style="padding: 22px;">
      <p style="margin-top: 0; font-size: 14px; color: #334155;">
        Dear Municipal Engineering Team,<br><br>
        An automated road distress survey has been completed by transit fleet unit <strong>{bus_id}</strong>.
        Enclosed is the official municipal repair schedule compliant with Indian Road Congress (IRC) civil specifications.
      </p>

      <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; margin: 16px 0;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><b>Total Civil Work Orders:</b></td>
            <td style="padding: 6px 0; font-weight: bold; color: #0284c7; text-align: right;">{total_orders} Orders</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><b>Estimated Municipal Budget:</b></td>
            <td style="padding: 6px 0; font-weight: bold; color: #059669; text-align: right;">INR {budget_inr:,}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><b>P1 Critical (24h SLA):</b></td>
            <td style="padding: 6px 0; font-weight: bold; color: #dc2626; text-align: right;">{p1} Defects</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><b>P2 High Priority (48h SLA):</b></td>
            <td style="padding: 6px 0; font-weight: bold; color: #d97706; text-align: right;">{p2} Defects</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;"><b>P3 Medium Priority (7d SLA):</b></td>
            <td style="padding: 6px 0; font-weight: bold; color: #64748b; text-align: right;">{p3} Defects</td>
          </tr>
        </table>
      </div>

      <p style="color: #475569; font-size: 13px;">
        📎 <strong>Attached Spreadsheet:</strong> The complete IRC repair schedule with GPS coordinates and unit costs is attached as:
        <code>{os.path.basename(csv_path) if csv_path else "PWD_WORK_ORDER.csv"}</code>
      </p>

      <p style="color: #64748b; font-size: 13px; margin-bottom: 0;">
        Regards,<br>
        <strong>Devadharshan</strong><br>
        AI Urban Infrastructure Surveillance Team
      </p>
    </div>

    <div style="background-color: #f8fafc; padding: 12px; text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0;">
      Smart India Hackathon Prototype · Automated Mobile Urban Surveillance Platform
    </div>
  </div>
</body>
</html>"""

    alt_part.attach(MIMEText(plain_text, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt_part)

    # 3. Attachment: Clean text/csv MIME part
    if csv_path and os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                csv_data = f.read()
            csv_part = MIMEText(csv_data, "csv", "utf-8")
            csv_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(csv_path)
            )
            msg.attach(csv_part)
        except Exception as e_att:
            logger.warning(f"Could not attach CSV file: {e_att}")

    try:
        server = _connect_smtp(sender, password)
        refusals = server.sendmail(sender, target_emails, msg.as_string())
        server.quit()
        if refusals:
            logger.warning(f"Some recipients refused: {refusals}")
        success_msg = "Work-order docket & CSV successfully dispatched to Municipal Authorities!"
        logger.info(success_msg)
        return True, success_msg
    except smtplib.SMTPAuthenticationError:
        err = "Authentication Failed: Invalid App Password. Verify your 16-letter code in .env."
        logger.error(err)
        return False, err
    except Exception as e:
        err = f"SMTP Error: {str(e)}"
        logger.error(err)
        return False, err
