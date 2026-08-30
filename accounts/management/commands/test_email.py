from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sends a test email via configured Django/Gmail SMTP backend to verify email deliverability.'

    def add_arguments(self, parser):
        parser.add_argument(
            'recipient',
            type=str,
            help='Recipient email address (e.g. your-email@gmail.com)'
        )

    def handle(self, *args, **options):
        recipient = options['recipient'].strip().lower()

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write(self.style.MIGRATE_HEADING(" Django SMTP Configuration Diagnostics"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))

        # Safe inspection - Never print the password
        has_password = bool(getattr(settings, 'EMAIL_HOST_PASSWORD', None))
        masked_user = getattr(settings, 'EMAIL_HOST_USER', '')
        
        self.stdout.write(f"  EMAIL_BACKEND       : {getattr(settings, 'EMAIL_BACKEND', 'Not Set')}")
        self.stdout.write(f"  EMAIL_HOST          : {getattr(settings, 'EMAIL_HOST', 'Not Set')}")
        self.stdout.write(f"  EMAIL_PORT          : {getattr(settings, 'EMAIL_PORT', 'Not Set')}")
        self.stdout.write(f"  EMAIL_USE_TLS       : {getattr(settings, 'EMAIL_USE_TLS', 'Not Set')}")
        self.stdout.write(f"  EMAIL_USE_SSL       : {getattr(settings, 'EMAIL_USE_SSL', 'Not Set')}")
        self.stdout.write(f"  EMAIL_HOST_USER     : {masked_user if masked_user else self.style.WARNING('(Empty - Needs Configuration in .env)')}")
        self.stdout.write(f"  EMAIL_HOST_PASSWORD : {'******** (Configured)' if has_password else self.style.WARNING('(Missing - Needs 16-character App Password in .env)')}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL  : {getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not Set')}")
        self.stdout.write(f"  Recipient           : {recipient}")
        self.stdout.write("-" * 60)

        if not masked_user or not has_password:
            self.stdout.write(self.style.WARNING(
                "\n[WARNING] EMAIL_HOST_USER or EMAIL_HOST_PASSWORD is not configured in .env.\n"
                "To send real emails via Gmail:\n"
                "1. Go to your Google Account -> Security -> 2-Step Verification.\n"
                "2. Generate an 'App Password' (16 characters).\n"
                "3. Set EMAIL_HOST_USER=your_email@gmail.com and EMAIL_HOST_PASSWORD=your_app_password in your .env file.\n"
            ))

        self.stdout.write("Attempting to send test email...")

        subject = "CrowdFund Egypt - SMTP Configuration Test"
        timestamp_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        body_text = (
            f"Hello,\n\n"
            f"This is a test email sent from CrowdFund Egypt Django Application.\n"
            f"If you received this message, your Gmail SMTP settings are 100% working correctly!\n\n"
            f"Details:\n"
            f"- Timestamp: {timestamp_str}\n"
            f"- Host: {getattr(settings, 'EMAIL_HOST', '')}:{getattr(settings, 'EMAIL_PORT', '')}\n"
            f"- Sender: {getattr(settings, 'DEFAULT_FROM_EMAIL', '')}\n\n"
            f"Best regards,\n"
            f"CrowdFund Egypt Platform"
        )
        
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f8fafc; color: #1e293b;">
          <div style="max-width: 540px; margin: auto; background: #ffffff; padding: 28px; border-radius: 12px; border: 1px solid #e2e8f0;">
            <h2 style="color: #0d6efd; margin-top: 0;">🇪🇬 CrowdFund Egypt</h2>
            <h3 style="color: #198754;">✓ SMTP Test Successful!</h3>
            <p>Your Django Gmail SMTP configuration is active and delivering emails properly.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px;">
              <tr><td style="padding: 6px; font-weight: bold;">Timestamp:</td><td>{timestamp_str}</td></tr>
              <tr><td style="padding: 6px; font-weight: bold;">Host:</td><td>{getattr(settings, 'EMAIL_HOST', '')}:{getattr(settings, 'EMAIL_PORT', '')}</td></tr>
              <tr><td style="padding: 6px; font-weight: bold;">From:</td><td>{getattr(settings, 'DEFAULT_FROM_EMAIL', '')}</td></tr>
              <tr><td style="padding: 6px; font-weight: bold;">To:</td><td>{recipient}</td></tr>
            </table>
            <p style="font-size: 12px; color: #64748b; margin-top: 24px;">CrowdFund Egypt Automated Test</p>
          </div>
        </body>
        </html>
        """

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient]
            )
            msg.attach_alternative(body_html, "text/html")
            msg.send(fail_silently=False)
            
            self.stdout.write(self.style.SUCCESS(
                f"\n[SUCCESS] Test email was sent successfully to {recipient}!"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"\n[FAILURE] Failed to send email via SMTP."
            ))
            self.stdout.write(self.style.ERROR(f"Error Details: {str(e)}\n"))
            self.stdout.write(self.style.NOTICE(
                "Troubleshooting Tips:\n"
                "1. If 'BadCredentials' / (535, 5.7.8): Ensure you are using a 16-character Google 'App Password',\n"
                "   NOT your standard personal Google password. 2-Step Verification must be enabled.\n"
                "2. If Connection Refused / Timeout: Check port (587 with TLS) and ensure outgoing SMTP is allowed by your network/firewall.\n"
                "3. Verify EMAIL_HOST_USER matches the Google account that generated the App Password.\n"
            ))
