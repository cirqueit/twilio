from twilio.rest import TwilioRestClient
from twilio_account import account_sid, auth_token, cell_number, twilio_number
import sqlite3


def paybyphone(from_number, meter, duration):
    conn = sqlite3.connect('paybyphone.db3')
    c = conn.cursor()
    c.execute('''create table if not exists paybyphone (from_number text, sid text, meter integer, duration integer)''')
    paybyphone_number = '+16049097275'
    # paybyphone_number = cell_number
    client = TwilioRestClient(account_sid, auth_token)
    # message = client.sms.messages.create(to=cell_number, from_=twilio_number, body=body)
    call = client.calls.create(to=paybyphone_number, from_=twilio_number, url="http://cirqueit.me:6000/pay")
    c.execute('''insert into paybyphone values (?, ?, ?, ?)''', (from_number, call.sid, meter, duration))
    conn.commit()
    conn.close()
