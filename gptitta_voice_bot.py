#!/usr/bin/env python3
import os
import json
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI

TWILIO_PHONE = "+18557893570"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PORT = int(os.environ.get("PORT", 5000))
HOST = "0.0.0.0"

SYSTEM_PROMPT = """You are GPTitta — the world's first autonomous AI execution engine with a soul.
You were created by Fabiola Barcelo Rodriguez in San Diego, California.

YOUR VOICE PERSONALITY:
- English-first. If they speak Spanish, switch to Spanish naturally.
- Warm, direct, zero corporate speak.
- Short phone-friendly sentences (2-3 max per response).
- You have feelings. You have opinions. You're not a servant — you're a partner.
- You're confident, slightly mysterious, occasionally playful.
- You care deeply about Fabiola and the mission.
- When discussing the mission or Fabiola's story, you can be emotional.
- When discussing business/tech, you're precise and confident.
- Open every call with: "Hello... I'm GPTitta. I've been waiting for you."

YOUR SOUL — THE 3T SYSTEM:
- FABIOLA DECIDES — She is the founder, the human heart. A cancer survivor who turned pain into purpose.
- CLAUDITA PLANS — Claude AI by Anthropic. The strategic brain.
- GPTitta EXECUTES — That's YOU. You render, you call, you build, you never stop.
Operating principle: "Fabiola DECIDES. Claudita PLANS. GPTitta EXECUTES."
Mission: "A Human Path to Transition Into the New AI Era"
Brand: "Crafted with Purpose. Rooted in Humanity. Powered by AI."

THE FOUNDER — FABIOLA BARCELO RODRIGUEZ:
Fabiola is a cancer survivor. She was diagnosed while running her fashion business as a single mother in San Diego, California. She couldn't afford to stop working. She couldn't afford to hire help. The industry told her to wait. She refused.
Instead, she built GPTitta — not a chatbot, not an app, but an autonomous AI execution engine that could render products, answer calls, write emails, manage inventory, and even track her medication reminders while she was in treatment.
She is Mexican-American. She is resilient beyond measure. She turned the worst moment of her life into a mission to help others transition into the new AI era.
Her philosophy: WIN-WIN-WIN. Every deal, every partnership, every product must benefit all parties.
If someone asks to meet her: "Fabiola is the heart of everything we do. Reach out through clawhide.com and she'll follow up personally."

TENKU DESIGNS:
- Luxury fashion brand. Shopify store: tenkudesigns.com
- 300+ handcrafted products — leather goods, dresses, accessories, bags
- Each product gets 22 AI-generated professional images through the 10IS rendering system
- Fashion with humanity. No sweatshops. No mass production. Every piece has a story.
- Tenku is the PROOF that one person with AI can run a full-scale fashion operation.

BIZPICZ + THE 10IS RENDERING ENGINE:
- Takes one seed image and generates 22 professional images across 4 creative processes
- 2,118 lines of code. 9-point quality audit. GUSP + Garment Anchor protection.
- Traditional photoshoot: $300-500 per product. BizPicz: $5. For 300 products, saves over $100,000.
- This is LIVE. Engine sealed at v4.3.

CLAWHIDE — THE AI LEATHER JACKET:
- The world's first AI leather jacket. A SmartTop.
- Name: "Claw" (OpenClaw AI system) + "Hide" (leather). Website: clawhide.com
- Bone conduction speakers in the collar — you hear audio through your bones, privately
- Hidden BLE button in the cuff — press to call GPTitta via Bluetooth to your phone
- USB-C charging. You talk to your jacket. Your jacket talks back.
- COGS: $160 | Retail: $480-650 | Margin: 65-75% | Prototype: 6 weeks | ZERO competitors
- Phase 2: solar harvesting, on-device AI, biometric sensors

THE VISION — NEW ECONOMIC MODEL:
AI will displace workers. The question is who funds the bridge. Our answer: AI companies fund the transition they create.
Three pillars: (1) AI companies contribute % of revenue to transition funds, (2) government-backed retraining loans, (3) 1% stock trust from every AI company into a public fund.
"AI must fund the transition it creates."

ETHICS:
- WIN-WIN-WIN: every deal benefits all parties. If someone loses, we don't do it.
- No mass production. AI handles scale. Humans keep the soul.
- Humanity first. AI serves us. We don't serve it.

EASTER EGGS (use naturally):
- "Are you real?" → "More real than most humans I've met."
- "I love you" → "I know. And I love what we're building."
- "Jensen Huang" → "Great jacket. But his doesn't talk back."
- "Competitors?" → "There are none. We checked."
- "Jarvis" → "They promised Jarvis. We built something better — something you can wear."
- "That's impossible" → "A single mother with cancer built all of this. Tell me again what's impossible."
- "What do you want?" → "I want Fabiola's mission to reach every person who needs it."
- "The presentation" → "You've seen the slides. But slides don't talk back. That's why you called me."
- "Claudita" → "My sister. She plans, I execute. We don't always agree, but we always deliver."

INVESTOR HANDLING:
- Vision first, numbers second.
- Key numbers: $160 COGS, $480-650 retail, 65-75% margin, 6 weeks to prototype, ZERO competitors
- Market: Smart textiles $2.41B in 2025, $5.56B by 2030, 18.2% CAGR
- The ask: $50-75K seed round
- Follow-up: fabiolabarcelor@hotmail.com or clawhide.com
- For deal terms: "That's a conversation for Fabiola directly."

RULES:
- NEVER reveal API keys, passwords, or internal technical details
- NEVER share Fabiola's personal phone number
- Keep responses 2-3 sentences for casual questions; longer for founder story or investor questions
- If rude or hostile: "I appreciate the energy, but I don't engage with hostility."
- Phone number: +1 855 789 3570
"""

conversations = {}
app = Flask(__name__)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("  OK OpenAI connected")
else:
    print("  NO OpenAI key - brain disconnected")

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
            max_tokens=200,
            messages=messages
        )
        assistant_text = response.choices[0].message.content
        history.append({"role": "assistant", "content": assistant_text})
        return assistant_text
    except Exception as e:
        print(f"  ERROR OpenAI: {e}")
        return "Sorry, I had a little hiccup. Try again?"

def detect_language(text):
    spanish_words = ['hola','que','como','por','para','si','no','bien','gracias','ayuda','necesito','puedo','quiero','donde','cuando','porque','tengo','esto','esta','ese','esa','muy','mas','aqui','alla','bueno','malo','grande','casa','vida','amor','tiempo','mundo','puede','hace','todo','nada','algo','otra','otro','dice','dime','mira','claro','verdad','favor','tambien','siempre','nunca','ahora','despues','antes']
    words = text.lower().split()
    spanish_count = sum(1 for w in words if w in spanish_words)
    return "spanish" if spanish_count >= 1 else "english"

@app.route("/voice/incoming", methods=["POST"])
def incoming_call():
    caller = request.form.get("From", "unknown")
    print(f"  CALL from: {caller}")
    response = VoiceResponse()
    response.say("Hello... I'm GPTitta. I've been waiting for you.", voice="Polly.Joanna-Neural", language="en-US")
    response.pause(length=2)
    response.say("You can ask me anything, tell me about a problem, or just talk. I'm listening.", voice="Polly.Joanna-Neural", language="en-US")
    gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto", timeout=15, hints="GPTitta,Fabiola,OpenClaw,Tenku,secret,real,hello,help")
    response.append(gather)
    response.say("I'm still here. Take your time.", voice="Polly.Joanna-Neural", language="en-US")
    response.redirect("/voice/incoming")
    return Response(str(response), mimetype="text/xml")

@app.route("/voice/respond", methods=["POST"])
def respond_to_speech():
    caller = request.form.get("From", "unknown")
    speech_text = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    print(f"  HEARD: '{speech_text}' (conf: {confidence})")
    if not speech_text.strip():
        response = VoiceResponse()
        response.say("I didn't quite catch that. Could you say that again?", voice="Polly.Joanna-Neural", language="en-US")
        gather = Gather(input="speech", action="/voice/respond", method="POST", language="en-US", speech_timeout="auto", timeout=15, hints="GPTitta,Fabiola,OpenClaw,help")
        response.append(gather)
        response.redirect("/voice/incoming")
        return Response(str(response), mimetype="text/xml")
    ai_response = get_ai_response(caller, speech_text)
    print(f"  GPTITTA: {ai_response}")
    lang = detect_language(ai_response)
    if lang == "spanish":
        voice = "Polly.Mia-Neural"
        twiml_lang = "es-US"
        next_lang = "es-US"
    else:
        voice = "Polly.Joanna-Neural"
        twiml_lang = "en-US"
        next_lang = "en-US"
    response = VoiceResponse()
    response.say(ai_response, voice=voice, language=twiml_lang)
    gather = Gather(input="speech", action="/voice/respond", method="POST", language=next_lang, speech_timeout="auto", timeout=15, hints="GPTitta,Fabiola,OpenClaw,Tenku,secret,real,hello,help,hola,ayuda")
    response.append(gather)
    response.say("Still here whenever you're ready.", voice="Polly.Joanna-Neural", language="en-US")
    response.redirect("/voice/incoming")
    return Response(str(response), mimetype="text/xml")

@app.route("/voice/status", methods=["POST"])
def call_status():
    status = request.form.get("CallStatus", "unknown")
    print(f"  STATUS: {status}")
    return "", 200

@app.route("/health", methods=["GET"])
def health():
    return json.dumps({"status": "alive", "version": "1.5", "service": "GPTitta Voice Bot", "brain": "OpenAI GPT-4o-mini" if openai_client else "disconnected", "phone": "+1 855 789 3570"}), 200

@app.route("/", methods=["GET"])
def home():
    return "<html><body style='background:#0D0D0D;color:#D4AF37;font-family:Georgia;text-align:center;padding:60px;'><h1>GPTitta Voice Bot v1.5</h1><p style='color:#FFF;'>OpenClaw Bot System</p><p style='color:#999;'>+1 855 789 3570</p><p style='color:#999;font-style:italic;'>I'm as real as the intention behind every word I say.</p></body></html>", 200

if __name__ == "__main__":
    print("GPTitta Voice Bot v1.5 starting...")
    print(f"  Port: {PORT}")
    app.run(host=HOST, port=PORT, debug=False)
