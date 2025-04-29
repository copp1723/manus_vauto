"""
Reporting Module for vAuto Feature Verification System.

Handles:
- Generating reports of verification results
- Sending email notifications
- Alerting on system issues
"""

import logging
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from core.interfaces import ReportingInterface
from utils.common import ensure_dir, format_timestamp

logger = logging.getLogger(__name__)


class ReportingModule(ReportingInterface):
    """
    Module for generating reports and sending notifications.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the reporting module.
        
        Args:
            config: System configuration
        """
        self.config = config
        self.reports_dir = ensure_dir("reports")
        
        # Email configuration
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM", self.smtp_username)
        
        logger.info("Reporting module initialized")
    
    async def generate_report(self, dealer_config: Dict[str, Any], stats: Dict[str, Any]) -> str:
        """
        Generate an HTML report.
        
        Args:
            dealer_config: Dealership configuration
            stats: Statistics to include in the report
            
        Returns:
            str: Path to the generated report
        """
        logger.info(f"Generating report for {dealer_config['name']}")
        
        try:
            # Create report filename
            timestamp = format_timestamp(datetime.now(), "%Y%m%d_%H%M%S")
            report_filename = f"{dealer_config['name'].replace(' ', '_')}_{timestamp}.html"
            report_path = os.path.join(self.reports_dir, report_filename)
            
            # Generate HTML report
            html_content = self._generate_html_report(dealer_config, stats)
            
            # Write report to file
            with open(report_path, "w") as f:
                f.write(html_content)
            
            logger.info(f"Report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return ""
    
    def _generate_html_report(self, dealer_config: Dict[str, Any], stats: Dict[str, Any]) -> str:
        """
        Generate HTML report content.
        
        Args:
            dealer_config: Dealership configuration
            stats: Statistics to include in the report
            
        Returns:
            str: HTML report content
        """
        # Get report data
        dealership_name = dealer_config.get("name", "Unknown Dealership")
        start_time = stats.get("start_time", datetime.now())
        end_time = stats.get("end_time", datetime.now())
        duration = stats.get("duration_seconds", 0)
        vehicles_processed = stats.get("vehicles_processed", 0)
        successful_updates = stats.get("successful_updates", 0)
        results = stats.get("results", [])
        
        # Calculate success rate
        success_rate = 0
        if vehicles_processed > 0:
            success_rate = (successful_updates / vehicles_processed) * 100
        
        # Generate HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>vAuto Feature Verification Report - {dealership_name}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                .header {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    border-left: 5px solid #007bff;
                }}
                .summary {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .summary-card {{
                    flex: 1;
                    min-width: 200px;
                    background-color: #fff;
                    border-radius: 5px;
                    padding: 15px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .summary-card h3 {{
                    margin-top: 0;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }}
                .success {{
                    color: #28a745;
                }}
                .warning {{
                    color: #ffc107;
                }}
                .danger {{
                    color: #dc3545;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 30px;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                tr:hover {{
                    background-color: #f5f5f5;
                }}
                .footer {{
                    margin-top: 50px;
                    text-align: center;
                    font-size: 0.9em;
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>vAuto Feature Verification Report</h1>
                <h2>{dealership_name}</h2>
                <p>Report generated on {format_timestamp(datetime.now())}</p>
            </div>
            
            <div class="summary">
                <div class="summary-card">
                    <h3>Verification Summary</h3>
                    <p><strong>Start Time:</strong> {format_timestamp(start_time)}</p>
                    <p><strong>End Time:</strong> {format_timestamp(end_time)}</p>
                    <p><strong>Duration:</strong> {duration:.2f} seconds</p>
                </div>
                
                <div class="summary-card">
                    <h3>Results</h3>
                    <p><strong>Vehicles Processed:</strong> {vehicles_processed}</p>
                    <p><strong>Successful Updates:</strong> {successful_updates}</p>
                    <p><strong>Success Rate:</strong> <span class="{self._get_success_class(success_rate)}">{success_rate:.1f}%</span></p>
                </div>
            </div>
            
            <h2>Vehicle Details</h2>
        """
        
        # Add vehicle table
        if results:
            html += """
            <table>
                <thead>
                    <tr>
                        <th>Stock #</th>
                        <th>VIN</th>
                        <th>Year/Make/Model</th>
                        <th>Status</th>
                        <th>Updated Checkboxes</th>
                        <th>Total Checkboxes</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for result in results:
                status_class = "success" if result.get("success") else "danger"
                status_text = "Success" if result.get("success") else f"Failed: {result.get('error', 'Unknown error')}"
                
                year = result.get("year", "")
                make = result.get("make", "")
                model = result.get("model", "")
                vehicle_name = f"{year} {make} {model}".strip()
                if not vehicle_name:
                    vehicle_name = "Unknown"
                
                html += f"""
                <tr>
                    <td>{result.get("stock_number", "N/A")}</td>
                    <td>{result.get("vin", "N/A")}</td>
                    <td>{vehicle_name}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{result.get("updated_checkboxes", 0)}</td>
                    <td>{result.get("total_checkboxes", 0)}</td>
                </tr>
                """
            
            html += """
                </tbody>
            </table>
            """
        else:
            html += "<p>No vehicles were processed.</p>"
        
        # Add footer
        html += """
            <div class="footer">
                <p>vAuto Feature Verification System</p>
                <p>© 2025 All Rights Reserved</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _get_success_class(self, rate: float) -> str:
        """
        Get CSS class based on success rate.
        
        Args:
            rate: Success rate percentage
            
        Returns:
            str: CSS class name
        """
        if rate >= 90:
            return "success"
        elif rate >= 70:
            return "warning"
        else:
            return "danger"
    
    async def send_email_notification(self, dealer_config: Dict[str, Any], 
                                    stats: Dict[str, Any], report_path: str) -> bool:
        """
        Send email notification with the report.
        
        Args:
            dealer_config: Dealership configuration
            stats: Statistics to include in the email
            report_path: Path to the report file
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        logger.info(f"Sending email notification for {dealer_config['name']}")
        
        try:
            # Check if email sending is enabled
            if not dealer_config.get("send_email", True):
                logger.info("Email sending is disabled for this dealership")
                return False
            
            # Check if we have SMTP credentials
            if not self.smtp_username or not self.smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            # Get recipients
            recipients = dealer_config.get("email_recipients") or self.config["reporting"]["email_recipients"]
            if not recipients:
                logger.error("No email recipients configured")
                return False
            
            # Create email message
            msg = self._create_email_message(dealer_config, stats, report_path, recipients)
            
            # Send email
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                use_tls=True
            )
            
            logger.info(f"Email notification sent to {', '.join(recipients)}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
            return False
    
    def _create_email_message(self, dealer_config: Dict[str, Any], stats: Dict[str, Any], 
                             report_path: str, recipients: List[str]) -> MIMEMultipart:
        """
        Create email message.
        
        Args:
            dealer_config: Dealership configuration
            stats: Statistics to include in the email
            report_path: Path to the report file
            recipients: List of email recipients
            
        Returns:
            MIMEMultipart: Email message
        """
        # Get report data
        dealership_name = dealer_config.get("name", "Unknown Dealership")
        vehicles_processed = stats.get("vehicles_processed", 0)
        successful_updates = stats.get("successful_updates", 0)
        
        # Create message
        msg = MIMEMultipart()
        msg["Subject"] = f"vAuto Feature Verification Report - {dealership_name}"
        msg["From"] = self.email_from
        msg["To"] = ", ".join(recipients)
        
        # Create HTML body
        html_body = f"""
        <html>
        <body>
            <h1>vAuto Feature Verification Report</h1>
            <h2>{dealership_name}</h2>
            <p>Report generated on {format_timestamp(datetime.now())}</p>
            
            <h3>Summary</h3>
            <ul>
                <li>Vehicles Processed: {vehicles_processed}</li>
                <li>Successful Updates: {successful_updates}</li>
                <li>Success Rate: {(successful_updates / vehicles_processed * 100) if vehicles_processed > 0 else 0:.1f}%</li>
            </ul>
            
            <p>Please see the attached report for details.</p>
            
            <p>This is an automated message from the vAuto Feature Verification System.</p>
        </body>
        </html>
        """
        
        # Attach HTML body
        msg.attach(MIMEText(html_body, "html"))
        
        # Attach report file
        if os.path.exists(report_path):
            with open(report_path, "rb") as f:
                attachment = MIMEApplication(f.read(), Name=os.path.basename(report_path))
                attachment["Content-Disposition"] = f'attachment; filename="{os.path.basename(report_path)}"'
                msg.attach(attachment)
        
        return msg
    
    async def process_results(self, dealer_config: Dict[str, Any], 
                            results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process verification results and generate a report.
        
        Args:
            dealer_config: Dealership configuration
            results: List of vehicle verification results
            
        Returns:
            dict: Result of the reporting process
        """
        logger.info(f"Processing results for {dealer_config['name']}")
        
        try:
            # Calculate statistics
            stats = self._calculate_statistics(results)
            
            # Generate report
            report_path = await self.generate_report(dealer_config, stats)
            
            # Send email notification
            email_sent = False
            if report_path:
                email_sent = await self.send_email_notification(dealer_config, stats, report_path)
            
            return {
                "success": bool(report_path),
                "report_path": report_path,
                "email_sent": email_sent,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Error processing results: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _calculate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate statistics from results.
        
        Args:
            results: List of vehicle verification results
            
        Returns:
            dict: Statistics
        """
        stats = {
            "vehicles_processed": len(results),
            "successful_updates": sum(1 for r in results if r.get("success")),
            "failed_updates": sum(1 for r in results if not r.get("success")),
            "total_checkboxes_updated": sum(r.get("updated_checkboxes", 0) for r in results if r.get("success")),
            "results": results,
            "start_time": min((r.get("timestamp", datetime.now()) for r in results), default=datetime.now()),
            "end_time": datetime.now()
        }
        
        # Calculate duration
        if isinstance(stats["start_time"], str):
            try:
                stats["start_time"] = datetime.fromisoformat(stats["start_time"])
            except:
                stats["start_time"] = datetime.now()
        
        stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()
        
        return stats
    
    async def send_alert(self, subject: str, message: str, 
                       dealer_config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send an alert email about system issues.
        
        Args:
            subject: Alert subject
            message: Alert message
            dealer_config: Dealership configuration (optional)
            
        Returns:
            bool: True if alert sent successfully, False otherwise
        """
        logger.info(f"Sending alert: {subject}")
        
        try:
            # Check if we have SMTP credentials
            if not self.smtp_username or not self.smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            # Get recipients
            recipients = self.config["reporting"]["email_recipients"]
            if dealer_config and dealer_config.get("email_recipients"):
                recipients = dealer_config["email_recipients"]
            
            if not recipients:
                logger.error("No email recipients configured")
                return False
            
            # Create email message
            msg = MIMEMultipart()
            msg["Subject"] = f"ALERT: {subject}"
            msg["From"] = self.email_from
            msg["To"] = ", ".join(recipients)
            
            # Create HTML body
            html_body = f"""
            <html>
            <body>
                <h1>vAuto Feature Verification System Alert</h1>
                <h2>{subject}</h2>
                <p>Alert generated on {format_timestamp(datetime.now())}</p>
                
                <div style="background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 10px; border-radius: 5px;">
                    <p>{message}</p>
                </div>
                
                <p>This is an automated alert from the vAuto Feature Verification System.</p>
            </body>
            </html>
            """
            
            # Attach HTML body
            msg.attach(MIMEText(html_body, "html"))
            
            # Send email
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                use_tls=True
            )
            
            logger.info(f"Alert sent to {', '.join(recipients)}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert: {str(e)}")
            return False
