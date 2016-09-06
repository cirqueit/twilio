from flask import Flask, request, redirect, url_for
from twilio.rest import TwilioRestClient
import twilio
import twilio.twiml
from twilio_account import account_sid, auth_token, cell_number, twilio_number
import speech_recognition as sr
import urllib
from datetime import datetime, timedelta
import parsedatetime as pdt
import pytz
import re
from redis import Redis
from rq_scheduler import Scheduler
from paybyphone import paybyphone
import sqlite3

blink_number ='+17788877246'
building = "6841386"
open="www9wwww9ww"
allow_all = True

scheduler = Scheduler(connection=Redis())

client = TwilioRestClient(account_sid, auth_token)



app = Flask(__name__)

@app.route("/sms", methods=['POST'])
def forward_sms():
    global allow_all

    from_number = request.values.get('From', None)
    sms_body = request.values.get('Body', None)
    if "park" in sms_body.lower():
        meter, duration, time, utc = get_parking(sms_body.lower())
        print from_number, meter, duration, time, utc
        scheduler.enqueue_at(utc, paybyphone, from_number, meter, duration)
        message = client.sms.messages.create(to=from_number, from_=twilio_number, body='meter: {0}\ntime: {1}\nduration: {2}'.format(meter, time, duration))
    elif cell_number in from_number:
        if "unlock" in sms_body.lower():
            allow_all = True
            message = client.sms.messages.create(to=from_number, from_=twilio_number, body="unlocked")
            print ('allow_all', allow_all)
        elif "lock" in sms_body.lower():
            allow_all = False
            message = client.sms.messages.create(to=from_number, from_=twilio_number, body="locked")
            print ('allow_all', allow_all)
        else:
            sms_body = '\n'.join(['SMS', from_number, sms_body])
            message = client.sms.messages.create(to=cell_number, from_=twilio_number, body=sms_body)
    else:
        sms_body = '\n'.join(['SMS', from_number, sms_body])
        message = client.sms.messages.create(to=cell_number, from_=twilio_number, body=sms_body)

    return ('', 204)


@app.route("/pay", methods=['GET', 'POST'])
def pay():
    sid = request.values.get('CallSid', None)
    conn = sqlite3.connect('paybyphone.db3')
    c = conn.cursor()
    c.execute('select * from paybyphone where sid=?', (sid,))
    _, _, meter, duration = c.fetchone()
    conn.close()

    resp = twilio.twiml.Response()
    wait = 'wwwwwwww'
    resp.play(digits=wait+str(meter)+'#')
    resp.play(digits=wait+str(duration)+'#')
    resp.play(digits=wait+str(1))
    resp.record(maxLength="8", action="/confirm")

    return str(resp)


@app.route("/confirm", methods=['GET', 'POST'])
def confirm():
    sid = request.values.get('CallSid', None)
    conn = sqlite3.connect('paybyphone.db3')
    c = conn.cursor()
    c.execute('select * from paybyphone where sid=?', (sid,))
    from_number, _, meter, duration = c.fetchone()
    conn.close()
    recording_url = request.values.get("RecordingUrl", None)
    body = 'meter: {0}\nduration: {1}\n'.format(meter, duration)
    body += get_voice(recording_url)
    message = client.sms.messages.create(to=from_number, from_=twilio_number, body=body)

    return str(recording_url)
    

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    from_number = request.values.get('From', None)
    print from_number
    resp = twilio.twiml.Response()

    if cell_number in from_number:
        with resp.gather(numDigits=1, action="/menu") as g:
            g.say("Press 1 to record a new message.")
    elif building in from_number:
        if allow_all:
            resp.say("Yo. I'll buzz you up. One second please.")
            resp.play(digits=open)
        else:
            resp.say("Hello. What is the password?")
            # resp.gather(numDigits=3, action="/password")
            resp.record(maxLength="5", action="/passphrase")
        message = client.sms.messages.create(to=cell_number, from_=twilio_number, body="Someone Buzzed")
        message = client.sms.messages.create(to=blink_number, from_=twilio_number, body="Someone Buzzed")
    else:
        resp.play(url_for('static', filename="message.wav"))
        resp.record(maxLength="60", action="/recording")

    return str(resp)

@app.route("/recording", methods=['GET', 'POST'])
def recording():
    recording_url = request.values.get("RecordingUrl", None)
    from_number = request.values.get('From', None)

    resp = twilio.twiml.Response()
    if cell_number in from_number:
        urllib.urlretrieve(recording_url, "static/message.wav")
        resp.play(url_for('static', filename="message.wav"))
        resp.hangup()

    else:
        voice_body = get_voice(recording_url)
        voice_body = '\n'.join(['Voice', from_number, voice_body])
        message = client.sms.messages.create(to=cell_number, from_=twilio_number, body=voice_body)

    return str(resp)


@app.route("/password", methods=['GET', 'POST'])
def password():
    digits_pressed = request.values.get('Digits', None)
    resp = twilio.twiml.Response()

    code = get_code()
    print (digits_pressed, code)
    if digits_pressed == code:
        resp.play(digits=open)
    else:
        resp.say("Wrong password")
    resp.hangup()

    return str(resp)


@app.route("/menu", methods=['GET', 'POST'])
def menu():
    digit_pressed = request.values.get('Digits', None)
    resp = twilio.twiml.Response()

    if digit_pressed == "1":
        resp.record(maxLength="6", action="/recording")
    else:
        resp.hangup()

    return str(resp)


@app.route("/passphrase", methods=['GET', 'POST'])
def passphrase():
    recording_url = request.values.get("RecordingUrl", None)

    voice = get_voice(recording_url)
    code = get_code()
    print (voice, code)

    resp = twilio.twiml.Response()
    if code in voice: 
        resp.play(digits=open)
    else:
        body = '\n'.join(['Bad Attempt', code, voice])
        message = client.sms.messages.create(to=cell_number, from_=twilio_number, body=body)
        resp.say("Wrong password")
    resp.hangup()

    return str(resp)

def get_parking(msg):
    meter, time, utc = '', '', ''
    duration = 120
    m = re.search(r'(\d*)\s*park\s*(\d{5})(.*)', msg)
    if m:
        duration_str = m.group(1)
        if duration_str:
            duration = int(duration_str)
        meter = m.group(2)
        time_str = m.group(3)
        if time_str:
            vancouver = pytz.timezone('America/Vancouver')
            now = datetime.now(vancouver)
            time = vancouver.localize(pdt.Calendar().parseDT(time_str, now)[0])
            if now > time:
                time += timedelta(days=1)
            utc = time.astimezone(pytz.utc)

    return meter, duration, time, utc.replace(tzinfo=None)


def get_code():
    vancouver = pytz.timezone('America/Vancouver')
    month, day = (datetime.now(vancouver).month, datetime.now(vancouver).day)
    code = str(1000 + ((month * day) % 1000))[1:]
    return code


def get_voice(url):
    voice = "error transcribing"
    urllib.urlretrieve(url, "tmp.wav")
    r = sr.Recognizer()
    with sr.WavFile("tmp.wav") as source:
        audio = r.record(source)
    try:
        voice = r.recognize_google(audio)
    except:
        pass
    return voice


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=6666, debug=True)
