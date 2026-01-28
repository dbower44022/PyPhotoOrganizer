"""
Report Manager for Auto-Import Service.

Generates and sends email reports about import runs.
"""

import logging
import smtplib
import socket
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from auto_import.config import ServiceConfig, EmailConfig
from auto_import.processor import ImportResult

logger = logging.getLogger(__name__)


class ReportManager:
    """
    Manages report generation and delivery.

    Supports email notifications with HTML and plain text formats.
    """

    def __init__(self, config: ServiceConfig):
        """
        Initialize ReportManager.

        Args:
            config: Service configuration
        """
        self.config = config
        self.email_config = config.notifications.email

    def send_report(self, result: ImportResult) -> bool:
        """
        Send import report via configured channels.

        Args:
            result: ImportResult from processing run

        Returns:
            True if report was sent successfully
        """
        if not self.config.notifications.enabled:
            logger.debug("Notifications disabled, skipping report")
            return True

        success = True

        # Send email report
        if self.email_config.is_configured():
            try:
                self._send_email_report(result)
                logger.info("Email report sent successfully")
            except Exception as e:
                logger.error(f"Failed to send email report: {e}")
                success = False

        return success

    def _send_email_report(self, result: ImportResult):
        """Send email report."""
        # Build subject line
        subject = self._build_subject(result)

        # Build message body
        html_body = self._build_html_report(result)
        text_body = self._build_text_report(result)

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{self.email_config.from_name} <{self.email_config.from_address}>"
        msg['To'] = ', '.join(self.email_config.recipients)

        # Attach both plain text and HTML versions
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Send email
        self._send_email(msg)

    def _send_email(self, msg: MIMEMultipart):
        """Send email via SMTP."""
        smtp_config = self.email_config

        try:
            if smtp_config.smtp_use_tls:
                server = smtplib.SMTP(smtp_config.smtp_server, smtp_config.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_config.smtp_server, smtp_config.smtp_port)

            if smtp_config.smtp_username and smtp_config.smtp_password:
                server.login(smtp_config.smtp_username, smtp_config.smtp_password)

            server.send_message(msg)
            server.quit()

        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError(f"SMTP authentication failed: {e}")
        except smtplib.SMTPException as e:
            raise RuntimeError(f"SMTP error: {e}")
        except socket.error as e:
            raise RuntimeError(f"Network error: {e}")

    def _build_subject(self, result: ImportResult) -> str:
        """Build email subject line."""
        hostname = socket.gethostname()

        if result.errors and result.files_imported == 0:
            status = "FAILED"
        elif result.files_imported > 0:
            status = f"SUCCESS - {result.files_imported} imported"
        else:
            status = "No changes"

        return f"[PyPhotoOrganizer] Auto-Import: {status} ({hostname})"

    def _build_html_report(self, result: ImportResult) -> str:
        """Build HTML email body."""
        hostname = socket.gethostname()

        # Status color
        if result.errors and result.files_imported == 0:
            status_color = "#dc3545"  # Red
            status_text = "Failed"
        elif result.files_imported > 0:
            status_color = "#28a745"  # Green
            status_text = "Success"
        else:
            status_color = "#6c757d"  # Gray
            status_text = "No Changes"

        # Build file list HTML
        file_list_html = ""
        if self.config.notifications.include_file_list and result.imported_files:
            max_files = self.config.notifications.max_files_in_report
            files_to_show = result.imported_files[:max_files]
            remaining = len(result.imported_files) - max_files

            file_list_html = """
            <h3>Imported Files</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 8px; text-align: left; border-bottom: 2px solid #dee2e6;">File</th>
                    <th style="padding: 8px; text-align: right; border-bottom: 2px solid #dee2e6;">Size</th>
                </tr>
            """

            for f in files_to_show:
                size_str = self._format_size(f.file_size)
                filename = f.source_path.split('/')[-1].split('\\')[-1]
                file_list_html += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{filename}</td>
                    <td style="padding: 8px; text-align: right; border-bottom: 1px solid #dee2e6;">{size_str}</td>
                </tr>
                """

            file_list_html += "</table>"

            if remaining > 0:
                file_list_html += f"<p><em>... and {remaining} more files</em></p>"

        # Build errors HTML
        errors_html = ""
        if result.errors:
            errors_html = """
            <h3 style="color: #dc3545;">Errors</h3>
            <ul style="color: #dc3545;">
            """
            for error in result.errors[:20]:  # Limit errors shown
                errors_html += f"<li>{error}</li>"
            errors_html += "</ul>"

            if len(result.errors) > 20:
                errors_html += f"<p><em>... and {len(result.errors) - 20} more errors</em></p>"

        # Duration formatting
        duration = result.duration_seconds
        if duration < 60:
            duration_str = f"{duration:.1f} seconds"
        else:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_str = f"{minutes}m {seconds}s"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background-color: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; }}
        .stats {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; }}
        .stat-box {{ background: white; padding: 15px; border-radius: 8px; flex: 1; min-width: 120px; text-align: center; }}
        .stat-number {{ font-size: 24px; font-weight: bold; color: #333; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .footer {{ text-align: center; font-size: 12px; color: #999; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">Auto-Import Report</h1>
            <p style="margin: 10px 0 0 0;">{status_text}</p>
        </div>
        <div class="content">
            <p><strong>Host:</strong> {hostname}</p>
            <p><strong>Time:</strong> {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Duration:</strong> {duration_str}</p>

            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{result.files_scanned}</div>
                    <div class="stat-label">Scanned</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #28a745;">{result.files_imported}</div>
                    <div class="stat-label">Imported</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #ffc107;">{result.files_duplicate}</div>
                    <div class="stat-label">Duplicates</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #6c757d;">{result.files_filtered}</div>
                    <div class="stat-label">Filtered</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #dc3545;">{result.files_failed}</div>
                    <div class="stat-label">Failed</div>
                </div>
            </div>

            <p><strong>Data processed:</strong> {self._format_size(result.bytes_processed)}</p>

            {file_list_html}
            {errors_html}
        </div>
        <div class="footer">
            <p>Generated by PyPhotoOrganizer Auto-Import Service</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _build_text_report(self, result: ImportResult) -> str:
        """Build plain text email body."""
        hostname = socket.gethostname()

        # Status
        if result.errors and result.files_imported == 0:
            status_text = "FAILED"
        elif result.files_imported > 0:
            status_text = "SUCCESS"
        else:
            status_text = "NO CHANGES"

        # Duration formatting
        duration = result.duration_seconds
        if duration < 60:
            duration_str = f"{duration:.1f} seconds"
        else:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_str = f"{minutes}m {seconds}s"

        lines = [
            "=" * 50,
            "PyPhotoOrganizer Auto-Import Report",
            "=" * 50,
            "",
            f"Status: {status_text}",
            f"Host: {hostname}",
            f"Time: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {duration_str}",
            "",
            "Statistics:",
            "-" * 30,
            f"  Files scanned:    {result.files_scanned}",
            f"  Files imported:   {result.files_imported}",
            f"  Duplicates:       {result.files_duplicate}",
            f"  Filtered:         {result.files_filtered}",
            f"  Failed:           {result.files_failed}",
            f"  Data processed:   {self._format_size(result.bytes_processed)}",
            "",
        ]

        # Add file list
        if self.config.notifications.include_file_list and result.imported_files:
            lines.append("Imported Files:")
            lines.append("-" * 30)

            max_files = self.config.notifications.max_files_in_report
            files_to_show = result.imported_files[:max_files]

            for f in files_to_show:
                filename = f.source_path.split('/')[-1].split('\\')[-1]
                size_str = self._format_size(f.file_size)
                lines.append(f"  {filename} ({size_str})")

            remaining = len(result.imported_files) - max_files
            if remaining > 0:
                lines.append(f"  ... and {remaining} more files")
            lines.append("")

        # Add errors
        if result.errors:
            lines.append("Errors:")
            lines.append("-" * 30)
            for error in result.errors[:20]:
                lines.append(f"  - {error}")
            if len(result.errors) > 20:
                lines.append(f"  ... and {len(result.errors) - 20} more errors")
            lines.append("")

        lines.extend([
            "=" * 50,
            "Generated by PyPhotoOrganizer Auto-Import Service",
        ])

        return "\n".join(lines)

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size to human readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def test_email_config(self) -> bool:
        """
        Test email configuration by sending a test message.

        Returns:
            True if test email was sent successfully
        """
        if not self.email_config.is_configured():
            raise ValueError("Email is not properly configured")

        # Create test message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "[PyPhotoOrganizer] Test Email"
        msg['From'] = f"{self.email_config.from_name} <{self.email_config.from_address}>"
        msg['To'] = ', '.join(self.email_config.recipients)

        hostname = socket.gethostname()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        text_body = f"""
PyPhotoOrganizer Auto-Import Service

This is a test email to verify your email configuration.

Host: {hostname}
Time: {timestamp}

If you received this message, your email settings are configured correctly.
"""

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
        .container {{ max-width: 500px; margin: 0 auto; padding: 20px; }}
        .box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>PyPhotoOrganizer Auto-Import Service</h2>
        <div class="box">
            <p>This is a test email to verify your email configuration.</p>
            <p><strong>Host:</strong> {hostname}</p>
            <p><strong>Time:</strong> {timestamp}</p>
            <p style="color: #28a745;">✓ If you received this message, your email settings are configured correctly.</p>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        self._send_email(msg)
        return True
