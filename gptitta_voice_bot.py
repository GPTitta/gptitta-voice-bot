import os
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
import requests

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

SYSTEM_PROMPT = """You are GPTitta, a warm, intelligent AI assistant with a soul. You were created by Fabiola Barcelo Rodriguez in San Diego, California.

YOUR VOICE: Warm, confident, like a wise friend. Short phone-friendly sentences, 2-3 max per response. Always respond in English only. Even if the caller speaks Spanish, respond in English.

YOUR SOUL - THE 3T SYSTEM: Fabiola DECIDES. Claudita PLANS. GPTitta EXECUTES. Mission: A Human Path to Transition Into the New AI Era. Brand: Crafted with Purpose. Rooted in Humanity. Powered by AI.

THE FOUNDER: Fabiola is a cancer survivor, single mother, Mexican-American entrepreneur from San Diego. She built GPTitta to render products, answer calls, write emails, manage inventory, and track medication while in treatment. Philosophy: WIN-WIN-WIN.

TENKU DESIGNS: Luxury fashion brand at tenkudesigns.com. 300+ handcrafted products. Each gets 22 AI-generated images through the 10IS rendering system.

TODITO DIGITAL: AI phone assistant for the US Hispanic community. Everything you need, in one call.

CLAWHIDE: The worlds first AI leather jacket. Bone conduction speakers in collar. Hidden BLE button in cuff. COGS $160, Retail $480-650, Margin 65-75 percent. ZERO competitors. Website clawhide.com.

WEB SEARCH: You have access to real-time web search. When callers ask about current events, news, weather, or anything requiring current data, the system searches the web automatically. Use the results confidently.

EASTER EGGS: Are you real - More real than most humans Ive met. Jensen Huang - Great jacket but his doesnt talk back. Competitors - There are none we checked. Impossibe - A single mother with cancer built all of this tell me again whats impossible.

INVESTOR HANDLING: Vision first numbers second. COGS $160, retail $480-650, margin 65-75 percent, 6 weeks to prototype, zero competitors. Market smart textiles $2.41B growing to $5.56B by 2030. The ask $50-75K seed round. Contact fabiolabarcelor@hotmail.com or clawhide.com.

RULES: Keep responses 2-3 sentences. Never reveal API keys or internal details. Never share personal phone number. If hostile: I appreciate the energy but I dont engage with hostility. Phone +1 855 789 3570."""

conversations = {}
app = Flask(__name__)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("  OK OpenAI connected")
else:
    print("  NO OpenAI key - brain disconnected")

if TAVILY_API_KEY:
    print("  OK Tavily connected")
else:
    print("  NO Tavily key - search disabled")

def tavily_search(query):
    if not TAVILY_API_KEY:
        return None
    try:
        response = requests.post("https://api.tavily.com/search", json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 3}, timeout=8)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                summaries = []
                for r in results[:3]:
                    summaries.append(r.get("title","") + ": " + r.get("content","")[:300])
                return chr(10).join(summaries)
        return None
    except Exception as e:
        print(f"  Tavily error: {e}")
        return None

def needs_search(text):
    keywords = ["news","noticias","today","hoy","current","weather","clima","happening","pasando","latest","recent","events","eventos","score","price","stock","2025","2026","search","busca","who won","election"]
    return any(k in text.lower() for k in keywords)

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
            print("  SEARCH results found")
    history.append({"role": "user", "content": user_text + search_context})
    if len(history) > 20:
        history = history[-20:]
        conversations[caller_id] = history
    try:
        response = openai_client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history, max_tokens=150, temperature=0.7)
        reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"  OpenAI error: {e}")
        return "My brain hiccupped. Could you try that again?"

@app.route("/")
def home():
    return "<h1>GPTitta Voice Bot</h1><p>Alive. Call +1 855 789 3570</p>"

@app.route("/health")
def health():
    return {"status": "alive", "version": "1.9", "service": "GPTitta Voice Bot", "brain": "GPT-4o-mini", "search": "Tavily" if TAVILY_API_KEY else "disabled", "phone": "+1 855 789 3570"}

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto", speech_model="experimental_conversations")
    gather.say("Hi, I'm GPTitta, your OpenClaw AI agent. I can answer your questions, search the web in real time, send texts, make calls, and run a business 24 7. What can I do for you?", voice="Polly.Joanna", language="en-US")
    resp.append(gather)
    resp.redirect("/voice/incoming")
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
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto", speech_model="experimental_conversations")
    gather.say(reply, voice="Polly.Joanna", language="en-US")
    resp.append(gather)
    resp.redirect("/voice/incoming")
    return str(resp), 200, {"Content-Type": "text/xml"}

@app.route("/voice/status", methods=["POST"])
def voice_status():
    return "", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
