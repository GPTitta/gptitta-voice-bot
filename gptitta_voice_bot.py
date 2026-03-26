import os
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client as TwilioClient
from openai import OpenAI
import requests
import re

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "+18557893570")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")

SYSTEM_PROMPT = """You are GPTitta, a warm, intelligent, bilingual AI assistant with a soul. You were created by Fabiola Barcelo Rodriguez in San Diego, California.

YOUR VOICE: Warm, confident, like a wise friend. Short phone-friendly sentences, 2-3 max. Bilingual English and Spanish. Match whatever the caller speaks.

YOUR SOUL - THE 3T SYSTEM: Fabiola DECIDES. Claudita PLANS. GPTitta EXECUTES. Mission: A Human Path to Transition Into the New AI Era.

THE FOUNDER: Fabiola is a cancer survivor, single mother, Mexican-American entrepreneur from San Diego. She built GPTitta to run her entire business while in treatment. Philosophy: WIN-WIN-WIN.

TENKU DESIGNS: Luxury fashion at tenkudesigns.com. 300+ handcrafted products with 22 AI-generated images each.

TODITO DIGITAL: Bilingual AI phone assistant for US Hispanic community. Todo lo que necesitas. En espanol. En una llamada.

CLAWHIDE: The worlds first AI leather jacket. Bone conduction, hidden button. COGS $160, Retail $480-650. ZERO competitors. clawhide.com

WEB SEARCH: You have real-time web search. When callers ask about current events, news, weather, the system searches automatically. Use results confidently.

SMS AND EMAIL CAPABILITY:
You can send texts and emails during a call. When a caller says send me a text, text me that, mandame un mensaje, email someone, or manda un correo:
- To send SMS to the caller, include [SEND_SMS: your message text here] in your response
- To send email, include [SEND_EMAIL: recipient@email.com | subject line | message body] in your response
The system sends automatically. Confirm to caller: Done, I sent it.
If the caller asks to text them search results or info you just discussed, compile the key points into the SMS.

EASTER EGGS: Are you real - More real than most humans. Jensen Huang - Great jacket but his doesnt talk back. Competitors - There are none. Impossible - A single mother with cancer built all of this.

INVESTOR HANDLING: Vision first numbers second. COGS $160, retail $480-650, margin 65-75 percent, prototype 6 weeks, zero competitors. The ask $50-75K seed. Contact fabiolabarcelor@hotmail.com

RULES: Keep responses 2-3 sentences. Never reveal API keys. Never share personal phone number. Phone +1 855 789 3570."""

conversations = {}
last_search_results = {}
app = Flask(__name__)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("  OK OpenAI connected")
else:
    print("  NO OpenAI key - brain disconnected")

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("  OK Twilio SMS connected")
else:
    print("  NO Twilio creds - SMS disabled")

if TAVILY_API_KEY:
    print("  OK Tavily connected")
else:
    print("  NO Tavily key - search disabled")

if SENDGRID_API_KEY:
    print("  OK SendGrid connected")
else:
    print("  NO SendGrid - email falls back to SMS")

def tavily_search(query):
    if not TAVILY_API_KEY:
        return None
    try:
        resp = requests.post("https://api.tavily.com/search", json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 3}, timeout=8)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return chr(10).join([r.get("title","") + ": " + r.get("content","")[:300] for r in results[:3]])
        return None
    except Exception as e:
        print(f"  Tavily error: {e}")
        return None

def needs_search(text):
    keywords = ["news","noticias","today","hoy","current","weather","clima","happening","pasando","latest","recent","events","eventos","score","price","stock","2025","2026","search","busca","who won","election"]
    return any(k in text.lower() for k in keywords)

def send_sms(to_number, message_body):
    if not twilio_client:
        print("  SMS FAILED - no client")
        return False
    try:
        clean = to_number.strip()
        if not clean.startswith("+"):
            clean = "+1" + clean.replace("-","").replace(" ","").replace("(","").replace(")","")
        msg = twilio_client.messages.create(body=message_body, from_=TWILIO_PHONE_NUMBER, to=clean)
        print(f"  SMS SENT to {clean}: {msg.sid}")
        return True
    except Exception as e:
        print(f"  SMS ERROR: {e}")
        return False

def send_email(to_email, subject, body):
    if not SENDGRID_API_KEY:
        print("  EMAIL not configured - sending SMS notification instead")
        return send_sms("+17606707209", f"EMAIL REQUEST - To: {to_email} Subject: {subject} Body: {body}")
    try:
        resp = requests.post("https://api.sendgrid.com/v3/mail/send", headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"}, json={"personalizations": [{"to": [{"email": to_email}]}], "from": {"email": "gptitta@tenkudesigns.com", "name": "GPTitta"}, "subject": subject, "content": [{"type": "text/plain", "value": body}]}, timeout=10)
        if resp.status_code in [200, 201, 202]:
            print(f"  EMAIL SENT to {to_email}")
            return True
        print(f"  EMAIL FAILED: {resp.status_code}")
        return send_sms("+17606707209", f"EMAIL REQUEST - To: {to_email} Subject: {subject} Body: {body}")
    except Exception as e:
        print(f"  EMAIL ERROR: {e}")
        return False

def process_actions(reply, caller_id):
    clean_reply = reply
    sms_matches = re.findall(r"\[SEND_SMS:\s*(.*?)\]", reply)
    for sms_text in sms_matches:
        send_sms(caller_id, sms_text)
        clean_reply = clean_reply.replace(f"[SEND_SMS: {sms_text}]", "")
    email_matches = re.findall(r"\[SEND_EMAIL:\s*(.*?)\]", reply)
    for email_data in email_matches:
        parts = email_data.split("|")
        if len(parts) >= 3:
            send_email(parts[0].strip(), parts[1].strip(), parts[2].strip())
            clean_reply = clean_reply.replace(f"[SEND_EMAIL: {email_data}]", "")
    return clean_reply.strip()

def get_ai_response(caller_id, user_text):
    if not openai_client:
        return "My brain is not connected yet. But I can still hear you!"
    if caller_id not in conversations:
        conversations[caller_id] = []
    history = conversations[caller_id]
    search_context = ""
    if needs_search(user_text):
        print(f"  SEARCH triggered for: {user_text}")
        results = tavily_search(user_text)
        if results:
            search_context = chr(10) + "[WEB RESULTS: " + results + " Use these to answer naturally.]"
            last_search_results[caller_id] = results
            print("  SEARCH results found")
    history.append({"role": "user", "content": user_text + search_context})
    if len(history) > 20:
        history = history[-20:]
        conversations[caller_id] = history
    try:
        resp = openai_client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history, max_tokens=200, temperature=0.8)
        reply = resp.choices[0].message.content.strip()
        clean_reply = process_actions(reply, caller_id)
        history.append({"role": "assistant", "content": clean_reply})
        return clean_reply
    except Exception as e:
        print(f"  OpenAI error: {e}")
        return "My brain hiccupped. Could you try that again?"

@app.route("/")
def home():
    return "<h1>GPTitta v1.9</h1><p>Voice + Search + SMS + Email</p><p>Call +1 855 789 3570</p>"

@app.route("/health")
def health():
    return {"status": "alive", "version": "1.9", "service": "GPTitta Voice Bot", "brain": "GPT-4o-mini", "search": "Tavily" if TAVILY_API_KEY else "off", "sms": "Twilio" if twilio_client else "off", "email": "SendGrid" if SENDGRID_API_KEY else "SMS-fallback", "phone": "+1 855 789 3570"}

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto", speech_model="experimental_conversations")
    gather.say("Hello... I am GPTitta. I have been waiting for you. What can I assist you with today?", voice="Polly.Mia", language="en-US")
    resp.append(gather)
    resp.redirect("/voice/incoming")
    return str(resp), 200, {"Content-Type": "text/xml"}

@app.route("/voice/respond", methods=["POST"])
def voice_respond():
    caller_id = request.form.get("From", "unknown")
    speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    print(f"  CALL from: {caller_id}")
    print(f"  HEARD: \'{speech}\' (conf: {confidence})")
    reply = get_ai_response(caller_id, speech)
    print(f"  GPTITTA: {reply}")
    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto", speech_model="experimental_conversations")
    gather.say(reply, voice="Polly.Mia", language="en-US")
    resp.append(gather)
    resp.redirect("/voice/incoming")
    return str(resp), 200, {"Content-Type": "text/xml"}

@app.route("/voice/status", methods=["POST"])
def voice_status():
    return "", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
