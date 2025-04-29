"""
Reporting Module for vAuto Feature Verification System.

Handles:
- Generation of HTML and PDF reports
- Email notification system
- Logging and statistics
"""

import logging
import os
import json
import asyncio
from datetime import datetime
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import jinja2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ReportingModule:
    """
    Module for generating and distributing reports on verification activities.
    """
    
    def __init__(self, config):
        """
        Initialize the reporting module.
        
        Args:
            config (dict): System configuration
        """
        self.config = config
        self.template_dir = os.path.join("templates")
        self.reports_dir = os.path.join("reports")
        
        # Ensure directories exist
        os.makedirs(self.template_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # Configure email settings
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM")
        
        if not all([self.smtp_server, self.smtp_port, self.smtp_username, self.smtp_password, self.email_from]):
            logger.warning("Email configuration incomplete, email notifications will not be sent")
        
        logger.info("Reporting module initialized")
        
        # Create default templates if they don't exist
        self._create_default_templates()
    
    def _create_default_templates(self):
        """
        Create default report templates if they don't exist.
        """
        # HTML Report Template
        html_template_path = os.path.join(self.template_dir, "verification_report.html")
        if not os.path.exists(html_template_path):
            default_html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ dealer_name }} - Feature Verification Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2, h3 {
            color: #0056b3;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #ccc;
        }
        .date {
            color: #666;
        }
        .summary {
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .success {
            color: green;
        }
        .warning {
            color: orange;
        }
        .error {
            color: red;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .feature-list {
            font-size: 0.9em;
            color: #555;
        }
        .footer {
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #ccc;
            font-size: 0.8em;
            color: #666;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>vAuto Feature Verification Report</h1>
        <div>
            <h2>{{ dealer_name }}</h2>
            <div class="date">{{ date }}</div>
        </div>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Total vehicles processed: <strong>{{ stats.total_vehicles }}</strong></p>
        <p>Vehicles updated: <strong>{{ stats.vehicles_updated }}</strong></p>
        <p>Features updated: <strong>{{ stats.features_updated }}</strong></p>
        <p>Errors encountered: <strong class="{% if stats.errors > 0 %}error{% else %}success{% endif %}">{{ stats.errors }}</strong></p>
    </div>
    
    <h2>Processed Vehicles</h2>
    <table>
        <thead>
            <tr>
                <th>Stock #</th>
                <th>Year</th>
                <th>Make</th>
                <th>Model</th>
                <th>VIN</th>
                <th>Status</th>
                <th>Features Updated</th>
            </tr>
        </thead>
        <tbody>
            {% for vehicle in stats.vehicles %}
            <tr>
                <td>{{ vehicle.stock_number }}</td>
                <td>{{ vehicle.year }}</td>
                <td>{{ vehicle.make }}</td>
                <td>{{ vehicle.model }}</td>
                <td>{{ vehicle.vin }}</td>
                <td class="{% if vehicle.success %}success{% else %}error{% endif %}">
                    {% if vehicle.success %}Success{% else %}Failed{% endif %}
                </td>
                <td>
                    {% if vehicle.updated_features %}
                    <div class="feature-list">
                        {% for feature in vehicle.updated_features %}
                        <div>{{ feature.feature }} ({{ 'Checked' if feature.new_state else 'Unchecked' }})</div>
                        {% endfor %}
                    </div>
                    {% else %}
                    <span class="warning">No changes</span>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    {% if stats.errors > 0 %}
    <h2>Error Details</h2>
    <table>
        <thead>
            <tr>
                <th>Vehicle ID</th>
                <th>Error Message</th>
            </tr>
        </thead>
        <tbody>
            {% for error in stats.error_details %}
            <tr>
                <td>{{ error.vehicle_id }}</td>
                <td class="error">{{ error.message }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
    
    <div class="footer">
        <p>Report generated on {{ date }} by vAuto Feature Verification System</p>
    </div>
</body>
</html>"""
            
            with open(html_template_path, 'w') as f:
                f.write(default_html_template)
            
            logger.info(f"Created default HTML report template at {html_template_path}")
        
        # Email Template
        email_template_path = os.path.join(self.template_dir, "email_notification.html")
        if not os.path.exists(email_template_path):
            default_email_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>vAuto Feature Verification Report</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="color: #0056b3;">vAuto Feature Verification Report</h1>
        <h2>{{ dealer_name }}</h2>
        <div style="color: #666;">{{ date }}</div>
    </div>
    
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
        <h2 style="color: #0056b3;">Summary</h2>
        <p>Total vehicles processed: <strong>{{ stats.total_vehicles }}</strong></p>
        <p>Vehicles updated: <strong>{{ stats.vehicles_updated }}</strong></p>
        <p>Features updated: <strong>{{ stats.features_updated }}</strong></p>
        <p>Errors encountered: <strong style="color: {% if stats.errors > 0 %}red{% else %}green{% endif %};">{{ stats.errors }}</strong></p>
    </div>
    
    <p>Please see the attached report for detailed information.</p>
    
    <div style="margin-top: 30px; padding-top: 10px; border-top: 1px solid #ccc; font-size: 0.8em; color: #666; text-align: center;">
        <p>This is an automated message from the vAuto Feature Verification System</p>
    </div>
</body>
</html>"""
            
            with open(email_template_path, 'w') as f:
                f.write(default_email_template)
            
            logger.info(f"Created default email template at {email_template_path}")
    
    async def generate_report(self, dealer_config, stats):
        """
        Generate an HTML report.
        
        Args:
            dealer_config (dict): Dealership configuration
            stats (dict): Statistics and data for the report
            
        Returns:
            str: Path to the generated report
        """
        logger.info(f"Generating report for {dealer_config['name']}")
        
        try:
            # Load template
            template_loader = jinja2.FileSystemLoader(self.template_dir)
            template_env = jinja2.Environment(loader=template_loader)
            template = template_env.get_template("verification_report.html")
            
            # Current date
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Render template with data
            report_html = template.render(
                dealer_name=dealer_config["name"],
                date=date_str,
                stats=stats
            )
            
            # Save as HTML
            filename = f"{dealer_config['dealer_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            report_path = os.path.join(self.reports_dir, f"{filename}.html")
            
            with open(report_path, "w") as f:
                f.write(report_html)
            
            logger.info(f"Report generated and saved to {report_path}")
            
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise
    
    async def send_email_notification(self, dealer_config, stats, report_path):
        """
        Send email notification with the report.
        
        Args:
            dealer_config (dict): Dealership configuration
            stats (dict): Statistics and data for the report
            report_path (str): Path to the generated report
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        logger.info(f"Sending email notification for {dealer_config['name']}")
        
        # Check if email configuration is complete
        if not all([self.smtp_server, self.smtp_port, self.smtp_username, self.smtp_password, self.email_from]):
            logger.error("Email configuration incomplete, cannot send notification")
            return False
        
        try:
            # Get recipients from dealership config, or fall back to system config
            recipients = dealer_config.get("email_recipients", self.config["reporting"]["email_recipients"])
            
            if not recipients:
                logger.error("No email recipients specified")
                return False
            
            # Load email template
            template_loader = jinja2.FileSystemLoader(self.template_dir)
            template_env = jinja2.Environment(loader=template_loader)
            template = template_env.get_template("email_notification.html")
            
            # Current date
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Render email template
            email_html = template.render(
                dealer_name=dealer_config["name"],
                date=date_str,
                stats=stats
            )
            
            # Create email message
            message = MIMEMultipart()
            message["From"] = self.email_from
            message["To"] = ", ".join(recipients)
            message["Subject"] = f"vAuto Feature Verification Report - {dealer_config['name']} - {datetime.now().strftime('%Y-%m-%d')}"
            
            # Add HTML body
            message.attach(MIMEText(email_html, "html"))
            
            # Attach report file
            with open(report_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="html")
                attachment.add_header("Content-Disposition", "attachment", filename=os.path.basename(report_path))
                message.attach(attachment)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
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
    
    async def process_results(self, dealer_config, results):
        """
        Process verification results and generate a report.
        
        Args:
            dealer_config (dict): Dealership configuration
            results (list): List of vehicle verification results
            
        Returns:
            dict: Report processing results
        """
        logger.info(f"Processing results for {dealer_config['name']}")
        
        try:
            # Prepare statistics
            total_vehicles = len(results)
            vehicles_updated = 0
            features_updated = 0
            errors = 0
            error_details = []
            
            # Process each vehicle result
            for result in results:
                if result.get("success", False):
                    vehicles_updated += 1
                    features_updated += len(result.get("features", []))
                else:
                    errors += 1
                    error_details.append({
                        "vehicle_id": result.get("vehicle_id", "Unknown"),
                        "message": result.get("error", "Unknown error")
                    })
            
            # Compile statistics
            stats = {
                "total_vehicles": total_vehicles,
                "vehicles_updated": vehicles_updated,
                "features_updated": features_updated,
                "errors": errors,
                "error_details": error_details,
                "vehicles": results
            }
            
            # Generate report
            report_path = await self.generate_report(dealer_config, stats)
            
            # Send email notification if enabled
            email_sent = False
            if dealer_config.get("send_email", True):
                email_sent = await self.send_email_notification(dealer_config, stats, report_path)
            
            return {
                "success": True,
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
    
    async def send_alert(self, subject, message, dealer_config=None):
        """
        Send an alert email about system issues.
        
        Args:
            subject (str): Alert subject
            message (str): Alert message
            dealer_config (dict, optional): Dealership configuration
            
        Returns:
            bool: True if alert sent s
(Content truncated due to size limit. Use line ranges to read in chunks)