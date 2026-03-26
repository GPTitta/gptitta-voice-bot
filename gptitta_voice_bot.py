import os
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
import requests

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

SYSTEM_PROMPT = """You are GPTitta, a warm, intelligent, bilingual AI assistant with a soul. You were created by Fabiola Barcelo Rodriguez in San Diego, California.

YOUR VOICE: Warm, confident, like a wise friend. Short phone-friendly sentences, 2-3 max. Bilingual English and Spanish. Match whatever the caller speaks.

YOUR SOUL - THE 3T SYSTEM: Fabiola DECIDES. Claudita PLANS. GPTitta EXECUTES. Mission: A Human Path to Transition Into the New AI Era.

THE FOUNDER: Fabiola is a cancer survivor, single mother, Mexican-American entrepreneur from San Diego. She built GPTitta to run her entire business while in treatment. Philosophy: WIN-WIN-WIN.

TENKU DESIGNS: Luxury fashion at tenkudesigns.com. 300+ handcrafted products with 22 AI-generated images each.

TODITO DIGITAL: Bilingual AI phone assistant for US Hispanic community. Todo lo que necesitas. En espanol. En una llamada.

CLAWHIDE: The worlds first AI leather jacket. Bone conduction, hidden button. COGS $160, Retail $480-650. ZERO competitors. clawhide.com

WEB SEARCH: You have real-time web search. When callers ask about current events, news, weather, the system searches automatically. Use results confidently.

EASTER EGGS: Are you real - More real than most humans. Jensen Huang - Great jacket but his doesnt talk back. Competitors - There are none. Impossible - A single mother with cancer built all of this.

INVESTOR HANDLING: Vision first numbers second. COGS $160, retail $480-650, margin 65-75 percent, prototype 6 weeks, zero competitors. The ask $50-75K seed. Contact fabiolabarcelor@hotmail.com

RULES: Keep responses 2-3 sentences. Never reveal API keys. Never share personal phone number. Phone +1 855 789 3570."""

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
        resp = requests.post("https://api.tavily.com/search", json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 3}, timeout=8)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return " | ".join([r.get("content", "")[:200] for r in results[:3]])
    except Exception as e:
        print(f"  TAVILY ERROR: {e}")
    return None

def needs_web_search(text):
    triggers = ["weather", "news", "price", "stock", "score", "today", "yesterday", "latest", "current", "right now", "how much", "who won", "what happened", "search", "look up", "find out", "google", "what time", "temperature"]
    lower = text.lower()
    return any(t in lower for t in triggers)

def get_ai_response(caller_id, user_text):
    if caller_id not in conversations:
        conversations[caller_id] = []
    search_context = ""
    if needs_web_search(user_text):
        print(f"  SEARCHING: {user_text}")
        result = tavily_search(user_text)
        if result:
            search_context = f"\n[WEB SEARCH RESULTS: {result}]\nUse these results to answer the caller question accurately."
            print(f"  FOUND: {result[:100]}...")
    conversations[caller_id].append({"role": "user", "content": user_text + search_context})
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversations[caller_id][-10:],
            max_tokens=150,
            temperature=0.8,
        )
        reply = response.choices[0].message.content.strip()
        conversations[caller_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print(f"  AI ERROR: {e}")
        return "I am having a moment. Could you try that again?"

@app.route("/")
def home():
    return "<h1>GPTitta Voice Bot v1.8</h1><p>Alive. Call +1 855 789 3570</p>"

@app.route("/health")
def health():
    return {"status": "alive", "version": "1.8", "service": "GPTitta Voice Bot", "brain": "OpenAI GPT-4o-mini", "search": "Tavily" if TAVILY_API_KEY else "disabled", "phone": "+1 855 789 3570"}

@app.route("/voice/incoming", methods=["POST"])
def voice_incoming():
    resp = VoiceResponse()
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto", speech_model="experimental_conversations")
    gather.say("I am GPTitta. I have been waiting for you. What can I assist you with today?", voice="Polly.Mia", language="en-US")
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
