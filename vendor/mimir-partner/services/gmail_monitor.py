import imaplib
import email
import os
import time
import threading
import tempfile
from email.header import decode_header
from database import db_session, SystemSettings
from reconciliation_engine import process_reconciliation

class GmailMonitor:
    def __init__(self, callback=None):
        self._running = False
        self._thread = None
        self.callback = callback
        
    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[*] Gmail Monitor started.")
        
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[*] Gmail Monitor stopped.")
        
    def _monitor_loop(self):
        while self._running:
            try:
                db_session.expire_all()
                settings = db_session.query(SystemSettings).first()
                if not settings or not settings.gmail_monitor_enabled:
                    time.sleep(10)
                    continue
                    
                user = settings.gmail_address
                password = settings.gmail_app_password
                folder = settings.gmail_folder or "INBOX"
                
                if not user or not password:
                    time.sleep(30)
                    continue
                
                # Connect to Gmail
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(user, password)
                
                # Select the folder
                status, messages = mail.select(f'"{folder}"')
                if status != "OK":
                    print(f"[!] Gmail Monitor: Could not select folder {folder}.")
                    mail.logout()
                    time.sleep(60)
                    continue
                
                # Search for unread emails
                status, messages = mail.search(None, "UNSEEN")
                if status == "OK":
                    for num in messages[0].split():
                        if not self._running: break
                        
                        status, msg_data = mail.fetch(num, "(RFC822)")
                        if status != "OK": continue
                        
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                
                                # Process attachments
                                csv_extracted = False
                                for part in msg.walk():
                                    if part.get_content_maintype() == "multipart": continue
                                    if part.get("Content-Disposition") is None: continue
                                    
                                    filename = part.get_filename()
                                    if filename and filename.lower().endswith('.csv'):
                                        # Download the attachment
                                        filepath = os.path.join(tempfile.gettempdir(), filename)
                                        with open(filepath, "wb") as f:
                                            f.write(part.get_payload(decode=True))
                                            
                                        print(f"[*] Gmail Monitor: Found CSV {filename}. Processing recon...")
                                        if self.callback: self.callback("Recon Active", "Processing incoming CSV...")
                                        
                                        # Force mark as read immediately to prevent infinite loops if recon fails
                                        mail.store(num, '+FLAGS', '\\Seen')
                                        
                                        # Run Recon!
                                        result = process_reconciliation(filepath)
                                        
                                        # Log result and trigger UI callback if needed
                                        success = result.get('success', False)
                                        msg_text = f"Recon {'Succeeded' if success else 'Failed'}: {result.get('prices_updated', 0)} prices updated."
                                        print(f"[*] Gmail Monitor: {msg_text}")
                                        
                                        if self.callback:
                                            self.callback("Recon Completed", msg_text)
                                            
                                        csv_extracted = True
                                        
                                if csv_extracted:
                                    pass
                                else:
                                    # No CSV found, leave it as read or unread? 
                                    # By default fetching marks it as read, which is fine so we don't re-process emails without attachments.
                                    pass
                                    
                mail.close()
                mail.logout()
            except Exception as e:
                print(f"[!] Gmail Monitor Error: {e}")
                
            # Sleep for 60 seconds before checking again
            for _ in range(60):
                if not self._running: break
                time.sleep(1)

# Global instance
gmail_monitor_instance = None

def get_gmail_monitor(callback=None):
    global gmail_monitor_instance
    if not gmail_monitor_instance:
        gmail_monitor_instance = GmailMonitor(callback)
    elif callback:
        gmail_monitor_instance.callback = callback
    return gmail_monitor_instance
