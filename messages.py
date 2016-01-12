from flask import Flask, request, redirect, url_for
from twilio.rest import TwilioRestClient
import twilio
import twilio.twiml
from twilio_account import account_sid, auth_token, cell_number, twilio_number
import speech_recognition as sr
import urllib
from datetime import datetime
import pytz

blink_number ='+17788877246'
building = "6841386"
open="www9wwww9ww"
allow_all = True

client = TwilioRestClient(account_sid, auth_token)

app = Flask(__name__)

@app.route("/sms", methods=['POST'])
def forward_sms():
    global allow_all

    from_number = request.values.get('From', None)
    sms_body = request.values.get('Body', None)
    if cell_number in from_number or blink_number in from_number:
        if "unlock" in sms_body.lower():
            allow_all = True
            message = client.sms.messages.create(to=from_number, from_=twilio_number, body="unlocked")
        else:
            allow_all = False
            message = client.sms.messages.create(to=from_number, from_=twilio_number, body="locked")
        print ('allow_all', allow_all)
    else:
        sms_body = '\n'.join(['SMS', from_number, sms_body])
        message = client.sms.messages.create(to=cell_number, from_=twilio_number, body=sms_body)

    return ('', 204)


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
            resp.say("Hello. Who is at my door?")
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


def get_code():
    vancouver = pytz.timezone('America/Vancouver')
    month, day = (datetime.now(vancouver).month, datetime.now(vancouver).day)
    code = str(1000 + ((month * day) % 1000))[1:]
    return code


def get_voice(url):
    urllib.urlretrieve(url, "tmp.wav")
    r = sr.Recognizer()
    with sr.WavFile("tmp.wav") as source:
        audio = r.record(source)
    try:
        voice = r.recognize_google(audio)
    except LookupError:
        voice = ""
    return voice


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=6000, debug=True)
