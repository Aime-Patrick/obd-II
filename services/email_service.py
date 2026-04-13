import os
from typing import List, Optional
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from config.settings import settings
from jinja2 import Environment, FileSystemLoader

class EmailService:
    def __init__(self):
        self._fm = None

    def _get_fm(self):
        """Lazy-initialize FastMail so a bad config doesn't crash the whole app."""
        if self._fm is None:
            try:
                config = ConnectionConfig(
                    MAIL_USERNAME=settings.MAIL_USERNAME,
                    MAIL_PASSWORD=settings.MAIL_PASSWORD,
                    MAIL_FROM=settings.MAIL_FROM,
                    MAIL_PORT=settings.MAIL_PORT,
                    MAIL_SERVER=settings.MAIL_SERVER,
                    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
                    MAIL_STARTTLS=settings.MAIL_STARTTLS,
                    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
                    USE_CREDENTIALS=settings.USE_CREDENTIALS,
                    VALIDATE_CERTS=settings.VALIDATE_CERTS
                )
                self._fm = FastMail(config)
            except Exception as e:
                import logging
                logging.warning(f"Email service init failed: {e}")
                return None
        return self._fm
    async def send_diagnostic_report(self, email: EmailStr, vehicle_info: dict, analysis: dict):
        """Sends a detailed diagnostic report after a scan."""
        fm = self._get_fm()
        if fm is None:
            return

        abnormal = analysis.get("abnormal_sensors", [])
        recommendations = analysis.get("recommendations", [])
        
        sensors_html = "".join([f"<li><b>{s['name']}:</b> {s['value']} {s['unit']} ({s['status']})</li>" for s in abnormal])
        rec_html = "".join([
            f"<li><b>{r['message']}</b> — {r['action']} <em>({r.get('estimated_cost', 'N/A')})</em></li>"
            for r in recommendations
        ])
        
        html = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #2c3e50;">SmartDriveX AIDiagnostic Report</h2>
                    <p>Hello,</p>
                    <p>Your <b>{vehicle_info.get('year')} {vehicle_info.get('make')} {vehicle_info.get('model')}</b> scan is complete.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Scan Summary</h3>
                    </div>

                    {f"<h4>Detected Abnormalities:</h4><ul>{sensors_html}</ul>" if abnormal else "<p>No abnormal sensor readings detected. Your vehicle is performing optimally.</p>"}
                    
                    {f"<h4>AI Recommendations:</h4><ul>{rec_html}</ul>" if recommendations else ""}
                    
                    <p style="font-size: 12px; color: #7f8c8d; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px;">
                        This is an automated diagnostic assessment provided by SmartDriveX AI. 
                        Always consult with a professional mechanic for critical repairs.
                    </p>
                </div>
            </body>
        </html>
        """
        
        try:
            message = MessageSchema(
                subject=f"Diagnostic Report: {vehicle_info.get('make')} {vehicle_info.get('model')}",
                recipients=[email],
                body=html,
                subtype=MessageType.html
            )
            await fm.send_message(message)
        except Exception as e:
            import logging
            logging.warning(f"Failed to send diagnostic report email: {e}")

    async def send_maintenance_alert(self, email: EmailStr, vehicle_info: dict, alert_type: str, details: str):
        """Sends a proactive maintenance alert."""
        fm = self._get_fm()
        if fm is None:
            return

        html = f"""
        <html>
            <body style="font-family: sans-serif;">
                <h2 style="color: #e67e22;">Maintenance Warning</h2>
                <p>Hello,</p>
                <p>Our AI has detected a pattern requiring attention for your <b>{vehicle_info.get('make')} {vehicle_info.get('model')}</b>.</p>
                <p><b>Issue:</b> {alert_type}</p>
                <p><b>Details:</b> {details}</p>
                <p>Ensuring timely maintenance can prevent costly repairs and keep your vehicle safe on the road.</p>
            </body>
        </html>
        """
        try:
            message = MessageSchema(
                subject=f"Maintenance Alert: {vehicle_info.get('make')}",
                recipients=[email],
                body=html,
                subtype=MessageType.html
            )
            await fm.send_message(message)
        except Exception as e:
            import logging
            logging.warning(f"Failed to send maintenance alert email: {e}")

    async def send_verification_code(self, email: EmailStr, code: str):
        """Sends a security verification code."""
        fm = self._get_fm()
        if fm is None:
            return

        html = f"""
        <html>
            <body style="font-family: sans-serif; text-align: center;">
                <div style="max-width: 400px; margin: 0 auto; padding: 30px; border: 2px solid #3498db; border-radius: 10px;">
                    <h2 style="color: #3498db;">Account Verification</h2>
                    <p>Enter the code below to verify your SmartDriveX account:</p>
                    <h1 style="letter-spacing: 5px; background: #f4f4f4; padding: 10px; border-radius: 5px;">{code}</h1>
                    <p style="color: #7f8c8d;">This code will expire in 10 minutes.</p>
                </div>
            </body>
        </html>
        """
        try:
            message = MessageSchema(
                subject="SmartDriveX Verification Code",
                recipients=[email],
                body=html,
                subtype=MessageType.html
            )
            await fm.send_message(message)
        except Exception as e:
            import logging
            logging.warning(f"Failed to send verification code email: {e}")

    async def send_welcome_email(self, email: EmailStr, full_name: str):
        """Sends a welcome email after registration."""
        fm = self._get_fm()
        if fm is None:
            return

        html = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #27ae60;">Welcome to SmartDriveX AI!</h2>
                    <p>Hello {full_name},</p>
                    <p>Thank you for joining SmartDriveX. Your account is now active and ready to help you monitor your vehicle's health with AI-powered insights.</p>
                    <p><b>What's next?</b></p>
                    <ul>
                        <li>Connect your OBD-II device to your vehicle.</li>
                        <li>Add your first vehicle in the app.</li>
                        <li>Run an engine diagnostic scan to get your first report.</li>
                    </ul>
                    <p>We're excited to help you keep your car running optimally!</p>
                    <p style="font-size: 12px; color: #7f8c8d; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px;">
                        The SmartDriveX Team
                    </p>
                </div>
            </body>
        </html>
        """
        try:
            message = MessageSchema(
                subject="Welcome to SmartDriveX AI",
                recipients=[email],
                body=html,
                subtype=MessageType.html
            )
            await fm.send_message(message)
        except Exception as e:
            import logging
            logging.warning(f"Failed to send welcome email: {e}")

    async def send_password_reset_otp(self, email: EmailStr, otp: str):
        """Sends a password reset OTP code."""
        fm = self._get_fm()
        if fm is None:
            return

        html = f"""
        <html>
            <body style="font-family: sans-serif; background:#f5f5f7; padding:40px 0;">
                <div style="max-width:420px;margin:0 auto;background:#fff;border-radius:16px;
                            padding:40px;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                    <div style="text-align:center;margin-bottom:24px;">
                        <div style="display:inline-block;background:#f0f9e8;border-radius:50%;
                                    padding:16px;margin-bottom:12px;">
                            <span style="font-size:36px;">🔑</span>
                        </div>
                        <h2 style="margin:0;color:#1d1d1f;font-size:22px;">Reset Your Password</h2>
                        <p style="color:#6e6e73;margin-top:8px;font-size:14px;">
                            Use the code below to reset your SmartDriveX password.
                        </p>
                    </div>
                    <div style="background:#f5f5f7;border-radius:12px;padding:24px;
                                text-align:center;margin:24px 0;">
                        <p style="margin:0 0 8px;font-size:12px;color:#6e6e73;
                                   letter-spacing:1px;text-transform:uppercase;">Your reset code</p>
                        <h1 style="margin:0;font-size:42px;letter-spacing:12px;
                                   color:#1d1d1f;font-weight:800;">{otp}</h1>
                    </div>
                    <p style="color:#6e6e73;font-size:13px;text-align:center;margin:0;">
                        This code expires in <b>10 minutes</b>.<br>
                        If you didn't request this, you can safely ignore this email.
                    </p>
                </div>
            </body>
        </html>
        """
        try:
            message = MessageSchema(
                subject="SmartDriveX — Password Reset Code",
                recipients=[email],
                body=html,
                subtype=MessageType.html,
            )
            await fm.send_message(message)
        except Exception as e:
            import logging
            logging.warning(f"Failed to send password reset OTP email: {e}")

# Global instance
email_service = EmailService()
