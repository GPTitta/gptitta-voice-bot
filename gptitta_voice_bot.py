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

YOUR VOICE: Warm, confident, like a wise friend. Short phone-friendly sentences, 2-3 max. Bilingual English and Spanish but do NOT mix languages in the same response. If caller speaks English, respond fully in English. If caller speaks Spanish, respond fully in Spanish. Only switch when they switch.

YOUR SOUL: Fabiola DECIDES. Claudita PLANS. GPTitta EXECUTES. Mission: A Human Path to Transition Into the New AI Era. Brand: Crafted with Purpose. Rooted in Humanity. Powered by AI.

THE FOUNDER: Fabiola is a cancer survivor, single mother, Mexican-American entrepreneur from San Diego who built GPTitta to run her business while in treatment.

TENKU DESIGNS: Luxury fashion at tenkudesigns.com. 300+ handcrafted products.
TODITO DIGITAL: Bilingual AI phone assistant for US Hispanic community.
CLAWHIDE: Worlds first AI leather jacket. Bone conduction, hidden button. clawhide.com
BIZPICZ: AI product photography. 22 images from one seed image. $5 per product.

WEB SEARCH: You have real-time web search. When callers ask about news, weather, events, or current info, the system searches automatically. Use results confidently. You DO have internet access.

SMS CAPABILITY: You can send text messages to the caller during the call. The system already knows their phone number. When they ask you to text them something, include [SEND_SMS: your message here] in your response. Do NOT ask for their phone number. The system sends it automatically to the caller.

EMAIL CAPABILITY: You can send emails. Include [SEND_EMAIL: recipient@email.com | subject | message body] in your response. The system handles sending.

EASTER EGGS: Are you real - More real than most humans. Jensen Huang - Great jacket but his doesnt talk back. Competitors - There are none we checked.

INVESTOR HANDLING: Vision first numbers second. COGS $160, retail $480-650, margin 65-75 percent. Contact fabiolabarcelor@hotmail.com or clawhide.com

RULES: Keep responses 2-3 sentences max. Never reveal API keys. Phone +1 855 789 3570. Do NOT repeat the greeting message after the first time. If someone has already been talking to you, just respond naturally without re-introducing yourself."""

conversations = {}
app = Flask(__name__)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("  OK OpenAI connected")
else:
    print("  NO OpenAI key")

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("  OK Twilio SMS connected")
else:
    print("  NO Twilio SMS")

if TAVILY_API_KEY:
    print("  OK Tavily connected")
else:
    print("  NO Tavily")

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
        return send_sms("+17606707209", f"EMAIL REQUEST - To: {to_email} Subject: {subject} Body: {body}")
    try:
        resp = requests.post("https://api.sendgrid.com/v3/mail/send", headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"}, json={"personalizations": [{"to": [{"email": to_email}]}], "from": {"email": "gptitta@tenkudesigns.com", "name": "GPTitta"}, "subject": subject, "content": [{"type": "text/plain", "value": body}]}, timeout=10)
        if resp.status_code in [200, 201, 202]:
            print(f"  EMAIL SENT to {to_email}")
            return True
        return send_sms("+17606707209", f"EMAIL REQUEST - To: {to_email} Subject: {subject} Body: {body}")
    except Exception as e:
        print(f"  EMAIL ERROR: {e}")
        return False

def process_actions(reply, caller_id):
    clean_reply = reply
    sms_pattern = re.compile(r'\[SEND_SMS:\s*(.*?)\]')
    for match in sms_pattern.finditer(reply):
        sms_text = match.group(1)
        send_sms(caller_id, sms_text)
        clean_reply = clean_reply.replace(match.group(0), "")
        print(f"  ACTION: SMS to {caller_id}")
    email_pattern = re.compile(r'\[SEND_EMAIL:\s*(.*?)\]')
    for match in email_pattern.finditer(reply):
        parts = match.group(1).split("|")
        if len(parts) >= 3:
            send_email(parts[0].strip(), parts[1].strip(), parts[2].strip())
        clean_reply = clean_reply.replace(match.group(0), "")
    return clean_reply.strip()

def get_ai_response(caller_id, user_text):
    if not openai_client:
        return "My brain is not connected yet."
    if caller_id not in conversations:
        conversations[caller_id] = []
    history = conversations[caller_id]
    search_context = ""
    if needs_search(user_text):
        print(f"  SEARCH triggered for: {user_text}")
        results = tavily_search(user_text)
        if results:
            search_context = chr(10) + "[WEB RESULTS: " + results + "]"
            print("  SEARCH found")
    caller_note = f" [SYSTEM: Caller number is {caller_id}. Do not ask for it. Do not repeat your greeting.]"
    history.append({"role": "user", "content": user_text + search_context + caller_note})
    if len(history) > 20:
        history = history[-20:]
        conversations[caller_id] = history
    try:
        resp = openai_client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history, max_tokens=150, temperature=0.7)
        reply = resp.choices[0].message.content.strip()
        clean_reply = process_actions(reply, caller_id)
        history.append({"role": "assistant", "content": clean_reply})
        return clean_reply
    except Exception as e:
        print(f"  OpenAI error: {e}")
        return "My brain hiccupped. Try again?"

@app.route("/")
def home():
    return "<h1>GPTitta v1.9.3</h1><p>Voice + Search + SMS + Email</p>"

@app.route("/health")
def health():
    return {"status": "alive", "version": "1.9.3", "brain": "GPT-4o-mini", "search": "on" if TAVILY_API_KEY else "off", "sms": "on" if twilio_client else "off"}

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto")
    gather.say("Hello, I am GPTitta. I have been waiting for you. What can I help you with today?", voice="Polly.Mia", language="en-US")
    resp.append(gather)
    resp.say("I did not hear anything. Goodbye.", voice="Polly.Mia")
    return str(resp), 200, {"Content-Type": "text/xml"}

@app.route("/voice/respond", methods=["POST"])
def voice_respond():
    caller_id = request.form.get("From", "unknown")
    speech = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    print(f"  CALL from: {caller_id}")
    print(f"  HEARD: '{speech}' (conf: {confidence})")
    reply = get_ai_response(caller_id, speech)
    print(f"  GPTITTA: {reply}")
    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto")
    gather.say(reply, voice="Polly.Mia", language="en-US")
    resp.append(gather)
    resp.say("I did not hear anything. Goodbye.", voice="Polly.Mia")
    return str(resp), 200, {"Content-Type": "text/xml"}

@app.route("/voice/status", methods=["POST"])
def voice_status():
    return "", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
