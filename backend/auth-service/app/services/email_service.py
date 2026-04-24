from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, MailSettings, SandBoxMode
import jwt
import os
from datetime import datetime, timedelta

from app.config import SENDGRID_API_KEY, SECRET_KEY

FROM_EMAIL =  os.getenv("FROM_EMAIL", "uetfoody@gmail.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def generate_verification_token_email(email: str):
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {
        "sub": email,
        "type": "email_verification",
        "exp": expire
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

def send_verification_email(email: str, username: str, token: str):
    if not SENDGRID_API_KEY:
        print("Warning: SENDGRID_API_KEY not set, skipping email")
        return False
    
    verification_link = f"{FRONTEND_URL}/verify-email?token={token}"
    
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject='Verify Your Email Address',
        html_content=f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Welcome, {username}! 👋</h2>
                <p style="color: #666; line-height: 1.6;">
                    Your account has been created successfully! To unlock all features, 
                    please verify your email address.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" 
                       style="display: inline-block; padding: 14px 28px; 
                              background-color: #4F46E5; color: white; text-decoration: none; 
                              border-radius: 6px; font-weight: 600;">
                        Verify Email Address
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    Or copy and paste this link into your browser:
                </p>
                <p style="color: #4F46E5; word-break: break-all; font-size: 14px;">
                    {verification_link}
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    This link will expire in 24 hours. If you didn't create an account, 
                    please ignore this email.
                </p>
            </body>
        </html>
        """
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_change_password_email(email: str, username: str, token: str):
    """Send change password email using SendGrid"""
    if not SENDGRID_API_KEY:
        print("Warning: SENDGRID_API_KEY not set, skipping email")
        return False
    
    change_password_link = f"{FRONTEND_URL}/forgot-password?token={token}"
    
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject='Change Your Password',
        html_content=f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Hi {username}! 👋</h2>
                <p style="color: #666; line-height: 1.6;">
                    You requested to change your password. Click the button below to proceed:
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{change_password_link}" 
                       style="display: inline-block; padding: 14px 28px; 
                              background-color: #F59E0B; color: white; text-decoration: none; 
                              border-radius: 6px; font-weight: 600;">
                        Change Password
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    Or copy and paste this link into your browser:
                </p>
                <p style="color: #F59E0B; word-break: break-all; font-size: 14px;">
                    {change_password_link}
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    This link will expire in 1 hour. If you didn't request this, 
                    please ignore this email and your password will remain unchanged.
                </p>
            </body>
        </html>
        """
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_reset_password_email(email: str, username: str, token: str):
    """Send reset password email using SendGrid"""
    if not SENDGRID_API_KEY:
        print("Warning: SENDGRID_API_KEY not set, skipping email")
        return False
    
    reset_password_link = f"{FRONTEND_URL}/forgot-password?token={token}"
    
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject='Reset Your Password',
        html_content=f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Hi {username}! 👋</h2>
                <p style="color: #666; line-height: 1.6;">
                    We received a request to reset your password. Click the button below to create a new password:
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_password_link}" 
                       style="display: inline-block; padding: 14px 28px; 
                              background-color: #EF4444; color: white; text-decoration: none; 
                              border-radius: 6px; font-weight: 600;">
                        Reset Password
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    Or copy and paste this link into your browser:
                </p>
                <p style="color: #EF4444; word-break: break-all; font-size: 14px;">
                    {reset_password_link}
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    This link will expire in 1 hour. If you didn't request a password reset, 
                    please ignore this email and your password will remain unchanged.
                </p>
            </body>
        </html>
        """
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_set_password_email(email: str, username: str, token: str):
    """Send set password email using SendGrid"""
    if not SENDGRID_API_KEY:
        print("Warning: SENDGRID_API_KEY not set, skipping email")
        return False
    
    set_password_link = f"{FRONTEND_URL}/set-password?token={token}"
    
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject='Set Your Account Password',
        html_content=f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Hi {username}! 👋</h2>
                <p style="color: #666; line-height: 1.6;">
                    You requested to set a password for your account. This will allow you to 
                    sign in with both Google and email/password.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{set_password_link}" 
                       style="display: inline-block; padding: 14px 28px; 
                              background-color: #4F46E5; color: white; text-decoration: none; 
                              border-radius: 6px; font-weight: 600;">
                        Set Password
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    Or copy and paste this link into your browser:
                </p>
                <p style="color: #4F46E5; word-break: break-all; font-size: 14px;">
                    {set_password_link}
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    This link will expire in 1 hour for security reasons. If you didn't request this, 
                    please ignore this email.
                </p>
            </body>
        </html>
        """
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
    
def send_test_email(email: str, username: str, token: str):
    """Send set password email using SendGrid"""
    if not SENDGRID_API_KEY:
        print("Warning: SENDGRID_API_KEY not set, skipping email")
        return False
    
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=email,
        subject='Set Your Account Password',
        html_content=f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Hi {username}! 👋</h2>
                <p style="color: #666; line-height: 1.6;">
                   Test email for set password functionality.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    test email.
                </p>
            </body>
        </html>
        """
    )
    
    message.mail_settings = MailSettings(sandbox_mode=SandBoxMode(enable=False))
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.set_sendgrid_data_residency("global")
        response = sg.send(message)
        print(f"Email sent with status code: {response.status_code}")
        print(f"Response: {response}")
        return response.status_code == 202
    except Exception as e:
        print(f"Error sending email: {e}")
        return False