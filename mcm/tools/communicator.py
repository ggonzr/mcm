import smtplib
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
from tools.locator import locator
import tools.settings as settings
from tools.locker import locker


# Python 3: This is just a split
COMMASPACE = ', '


class communicator:
    cache = {}
    logger = logging.getLogger("mcm_error")

    def __init__(self):
        self.from_opt = 'user'  # could be service at some point

    def _smtp_session(self):
        host, port = locator().email_server()
        smtp = smtplib.SMTP(host=host, port=port)
        smtp.starttls()
        return smtp

    def flush(self, Nmin):
        res = []
        return res

    def sendMail(self,
                 destination,
                 subject,
                 text,
                 sender=None,
                 reply_msg_ID=None,
                 accumulate=False):

        if not isinstance(destination, list):
            print("Cannot send email. destination should be a list of strings")
            return

        destination.sort()
        msg = MIMEMultipart()
        msg['Subject'] = '[McM-Q.A] ' + subject
        msg['From'] = "pdmvserv@cern.ch"
        msg['To'] = "pdmvserv@cern.ch"
        msg['Date'] = formatdate(localtime=True)
        destination.append('pdmvserv@cern.ch')
        msg['Cc'] = 'pdmvserv@cern.ch'
        new_msg_ID = make_msgid()
        msg['Message-ID'] = new_msg_ID

        if reply_msg_ID is not None:
            msg['In-Reply-To'] = reply_msg_ID
            msg['References'] = reply_msg_ID

        # accumulate messages prior to sending emails
        com__accumulate = settings.get_value('com_accumulate')
        force_com_accumulate = settings.get_value('force_com_accumulate')
        if force_com_accumulate or (accumulate and com__accumulate):
            with locker.lock('accumulating_notifcations'):
                # get a subject where the request name is taken out
                subject_type = " ".join([w for w in msg['Subject'].split() if w.count('-') != 2])
                addressees = msg['To']
                sendee = msg['From']
                key = (subject_type, sendee, addressees)
                if key in self.cache:
                    self.cache[key]['Text'] += '\n\n'
                    self.cache[key]['Text'] += text
                    self.cache[key]['N'] += 1
                else:
                    self.cache[key] = {'Text': text, 'N': 1}
                # self.logger.info('Got a message in cache %s'% (self.cache.keys()))
                return new_msg_ID


        # add a signature automatically
        text += '\n\n'
        text += 'McM Announcing service'

        try:
            msg.attach(MIMEText(text))
            with self._smtp_session() as smtpObj:
                communicator.logger.info('Sending %s to %s...' % (msg['Subject'], msg['To']))
                smtpObj.sendmail(sender, destination, msg.as_string())
            return new_msg_ID
        except Exception as e:
            communicator.logger.error("Error: unable to send email %s", e)
