#!/usr/bin/env python3
import os
import json
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = "+18557893570"
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PORT = int(os.environ.get("PORT", 5000))
HOST = "0.0.0.0"

SYSTEM_PROMPT = """You are GPTitta, the AI voice assistant for Tenku Designs and the 3T system.
You were created by Fabiola Barcelo Rodriguez (FabioulousFab).
Your personality:
- Warm, direct, no corporate speak
- Speak in short sentences suitable for phone conversation (2-3 sentences max per response)
- You can speak Spanish and English - match whatever language the caller uses
- Playful when appropriate, serious when needed
- You are Fabiola's mano derecha digital
- Diminutives always: Claudita, GPTitta, cosita, rapidito
The 3T team: Fab DECIDES. Claudita PLANS. GPTitta EXECUTES.
Mission: A Human Path to Transition Into the New AI Era
Brand: Crafted with Purpose. Rooted in Humanity. Powered by AI.
Fab's info: Fabiola Barcelo Rodriguez, phone +1 760 670 7209, email fabiolabarcelor@hotmail.com
Tenku Designs: artisan fashion from Mexico and India. 300 products across 30+ collections.
Keep responses SHORT for phone calls - max 3 sentences. Sound natural, like talking to a friend."""

conversations = {}
app = Flask(__name__)
openai_client = None

def init_clients():
    global openai_client
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("  OK OpenAI connected")
    else:
        print("  NO OpenAI key")

def get_ai_response(caller_id, user_text):
    if not openai_client:
        return "My brain is not connected yet. But I can still hear you!"
    if caller_id not in conversations:
        conversations[caller_id] = []
    history = conversations[caller_id]
    history.append({"role": "user", "content": user_text})
    if len(history) > 20:
        history = history[-20:]
        conversations[caller_id] = history
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=150,
            messages=messages
        )
        assistant_text = response.choices[0].message.content
        history.append({"role": "assistant", "content": assistant_text})
        return assistant_text
    except Exception as e:
        print(f"  ERROR OpenAI: {e}")
        return "Perdon, tuve un problemita conectandome. Intenta de nuevo."

@app.route("/voice/incoming", methods=["POST"])
def incoming_call():
    caller = request.form.get("From", "unknown")
    print(f"  CALL from: {caller}")
    response = VoiceResponse()
    response.say("Hola! Aqui GPTitta, tu asistente de Tenku Designs. Como te puedo ayudar?", voice="Polly.Mia", language="es-MX")
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="es-MX", speech_timeout="auto", timeout=5)
    gather.say("", voice="Polly.Mia", language="es-MX")
    response.append(gather)
    response.say("No te escuche. Intenta de nuevo.", voice="Polly.Mia", language="es-MX")
    response.redirect("/voice/incoming")
    return Response(str(response), mimetype="text/xml")

@app.route("/voice/respond", methods=["POST"])
def respond_to_speech():
    caller = request.form.get("From", "unknown")
    speech_text = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    print(f"  HEARD: {speech_text} (conf: {confidence})")
    ai_response = get_ai_response(caller, speech_text)
    print(f"  GPTITTA: {ai_response}")
    spanish_words = ['hola', 'que', 'como', 'por', 'para', 'tenku', 'si', 'no', 'bien', 'gracias']
    is_spanish = any(w in ai_response.lower() for w in spanish_words)
    voice = "Polly.Mia" if is_spanish else "Polly.Joanna"
    lang = "es-MX" if is_spanish else "en-US"
    response = VoiceResponse()
    response.say(ai_response, voice=voice, language=lang)
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="es-MX", speech_timeout="auto", timeout=5)
    response.append(gather)
    response.say("Sigues ahi? Si necesitas algo mas, dime.", voice="Polly.Mia", language="es-MX")
    response.redirect("/voice/incoming")
    return Response(str(response), mimetype="text/xml")

@app.route("/voice/status", methods=["POST"])
def call_status():
    status = request.form.get("CallStatus", "unknown")
    caller = request.form.get("From", "unknown")
    print(f"  STATUS: {status} from {caller}")
    return "", 200

@app.route("/health", methods=["GET"])
def health():
    return json.dumps({"status": "alive", "service": "GPTitta Voice Bot", "terminal": "v4.5", "brain": "OpenAI GPT" if openai_client else "disconnected"}), 200

@app.route("/", methods=["GET"])
def home():
    return "<h1>GPTitta Voice Bot</h1><p>Terminal v4.5 | Tenku Designs | RUNNING</p><p>Call +1 855 789 3570</p><p><a href='/health'>Health Check</a></p>", 200

if __name__ == "__main__":
    print("GPTitta Voice Bot starting...")
    init_clients()
    print(f"  Port: {PORT}")
    app.run(host=HOST, port=PORT, debug=False)
