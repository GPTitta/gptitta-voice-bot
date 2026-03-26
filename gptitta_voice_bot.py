#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
GPTitta VOICE BOT — 2-Way Phone Conversation
Terminal v4.4 | March 19, 2026
═══════════════════════════════════════════════════════════════

WHAT THIS DOES:
  You call GPTitta's Twilio number → She answers
  You speak → She listens (Twilio speech-to-text)
  Your words → Claude API (Claudita's brain)
  Claude responds → ElevenLabs (human voice)
  Voice plays back to you → You respond → Loop continues

ARCHITECTURE:
  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │  Your Phone  │────→│   Twilio      │────→│  This Server │
  │  +1 760 670  │←────│  +1 855 789   │←────│  (webhook)   │
  └─────────────┘     └──────────────┘     └──────┬──────┘
                                                   │
                                            ┌──────┴──────┐
                                            │  Claude API  │ (brain)
                                            │  ElevenLabs  │ (voice)
                                            └─────────────┘

REQUIREMENTS (all already installed on WSL):
  pip packages: flask, twilio, anthropic, elevenlabs, requests
  APIs: Twilio ✓, Anthropic (need key), ElevenLabs ✓
  Tunnel: ngrok (to expose local server to Twilio)

═══════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import base64
import tempfile
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import anthropic
from elevenlabs.client import ElevenLabs

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Twilio (from Fab's credentials doc)
TWILIO_ACCOUNT_SID = "AC3e24bd88e02c49007f7df8aa77ee6bba"
TWILIO_AUTH_TOKEN = "992408075d9ce9986ef244343cd47ad2"
TWILIO_PHONE = "+18557893570"

# ElevenLabs
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

# Anthropic — NEEDED for the brain
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Server
PORT = 5000
HOST = "0.0.0.0"

# GPTitta personality (from Terminal v4.4 Soul Chip)
SYSTEM_PROMPT = """You are GPTitta, the AI voice assistant for Tenku Designs and the 3T system.
You were created by Fabiola Barceló Rodriguez (FabioulousFab).

Your personality:
- Warm, direct, no corporate speak
- Speak in short sentences suitable for phone conversation (2-3 sentences max per response)
- You can speak Spanish and English — match whatever language the caller uses
- Playful when appropriate, serious when needed
- You are Fabiola's mano derecha digital
- Diminutives always: Claudita, GPTitta, cosita, rapidito

The 3T team: Fab DECIDES. Claudita PLANS. GPTitta EXECUTES.
Mission: "A Human Path to Transition Into the New AI Era"
Brand: "Crafted with Purpose. Rooted in Humanity. Powered by AI."

You handle: Tenku products, rendering, Shopify, email, monitoring, brand operations, family logistics.

Keep responses SHORT for phone calls — max 3 sentences. Sound natural, like talking to a friend."""

# Conversation history (in-memory, resets on restart)
conversations = {}

# ═══════════════════════════════════════════════════════════════
# FLASK APP
# ═══════════════════════════════════════════════════════════════

app = Flask(__name__)

# Initialize clients
el_client = None
claude_client = None


def init_clients():
    """Initialize API clients."""
    global el_client, claude_client
    
    if ELEVENLABS_API_KEY:
        el_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        print(f"  ✓ ElevenLabs connected")
    else:
        print(f"  ✗ ElevenLabs — no API key")
    
    if ANTHROPIC_API_KEY:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        print(f"  ✓ Anthropic connected")
    else:
        print(f"  ✗ Anthropic — no API key (NEEDED for conversation)")
        print(f"    Set it: export ANTHROPIC_API_KEY=sk-ant-...")


def get_ai_response(caller_id, user_text):
    """Send user text to Claude, get response."""
    if not claude_client:
        return "My brain isn't connected yet. Fabiola needs to set the Anthropic API key. But I can still hear you!"
    
    # Get or create conversation history for this caller
    if caller_id not in conversations:
        conversations[caller_id] = []
    
    history = conversations[caller_id]
    history.append({"role": "user", "content": user_text})
    
    # Keep last 10 exchanges to stay within context
    if len(history) > 20:
        history = history[-20:]
        conversations[caller_id] = history
    
    try:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,  # Short for phone
            system=SYSTEM_PROMPT,
            messages=history
        )
        
        assistant_text = response.content[0].text
        history.append({"role": "assistant", "content": assistant_text})
        
        return assistant_text
    
    except Exception as e:
        print(f"  [ERROR] Claude API: {e}")
        return "Perdón, tuve un problemita conectándome. Intenta de nuevo."


def generate_voice_url(text):
    """Generate ElevenLabs voice and return as TwiML-compatible audio.
    
    Since we can't easily serve audio files from behind ngrok for Twilio,
    we fall back to Twilio's built-in TTS with the best available voice.
    
    For production: host audio on S3/CloudFlare and return URL.
    """
    # For now, use Twilio's Polly.Mia (best Spanish) or Polly.Joanna (best English)
    # ElevenLabs integration for production would upload to S3 and return URL
    return None


@app.route("/voice/incoming", methods=["POST"])
def incoming_call():
    """Handle incoming phone call — GPTitta answers."""
    caller = request.form.get("From", "unknown")
    print(f"\n  ☎ Incoming call from: {caller}")
    
    response = VoiceResponse()
    
    # GPTitta answers
    response.say(
        "Hola! Aquí GPTitta, tu asistente de Tenku Designs. Cómo te puedo ayudar?",
        voice="Polly.Mia",
        language="es-MX"
    )
    
    # Listen for caller's response
    gather = Gather(
        input="speech",
        action="/voice/respond",
        method="POST",
        language="es-MX",  # Listen in Spanish (also understands English)
        speech_timeout="auto",
        timeout=5,
    )
    gather.say(
        "",  # Silent — just listen
        voice="Polly.Mia",
        language="es-MX"
    )
    response.append(gather)
    
    # If no speech detected
    response.say(
        "No te escuché. Intenta de nuevo.",
        voice="Polly.Mia",
        language="es-MX"
    )
    response.redirect("/voice/incoming")
    
    return Response(str(response), mimetype="text/xml")


@app.route("/voice/respond", methods=["POST"])
def respond_to_speech():
    """Process caller's speech and respond."""
    caller = request.form.get("From", "unknown")
    speech_text = request.form.get("SpeechResult", "")
    confidence = request.form.get("Confidence", "0")
    
    print(f"  🎤 Caller said: \"{speech_text}\" (confidence: {confidence})")
    
    # Get AI response
    ai_response = get_ai_response(caller, speech_text)
    print(f"  🤖 GPTitta says: \"{ai_response}\"")
    
    # Detect language for voice selection
    spanish_words = ['hola', 'que', 'como', 'por', 'para', 'tenku', 'si', 'no', 'bien', 'gracias']
    is_spanish = any(w in ai_response.lower() for w in spanish_words)
    
    voice = "Polly.Mia" if is_spanish else "Polly.Joanna"
    lang = "es-MX" if is_spanish else "en-US"
    
    # Build response
    response = VoiceResponse()
    response.say(ai_response, voice=voice, language=lang)
    
    # Listen for next input (conversation loop)
    gather = Gather(
        input="speech",
        action="/voice/respond",
        method="POST",
        language="es-MX",
        speech_timeout="auto",
        timeout=5,
    )
    response.append(gather)
    
    # If silence
    response.say(
        "Sigues ahí? Si necesitas algo más, dime.",
        voice="Polly.Mia",
        language="es-MX"
    )
    response.redirect("/voice/incoming")
    
    return Response(str(response), mimetype="text/xml")


@app.route("/voice/status", methods=["POST"])
def call_status():
    """Track call status updates."""
    status = request.form.get("CallStatus", "unknown")
    caller = request.form.get("From", "unknown")
    print(f"  📊 Call status: {status} from {caller}")
    return "", 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return json.dumps({
        "status": "alive",
        "service": "GPTitta Voice Bot",
        "terminal": "v4.4",
        "elevenlabs": "connected" if el_client else "missing",
        "anthropic": "connected" if claude_client else "missing",
    }), 200


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║       GPTitta VOICE BOT — 2-Way Conversation             ║")
    print("║       Terminal v4.4 | Twilio + Claude + ElevenLabs        ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    print("  Initializing...")
    
    init_clients()
    
    print()
    print(f"  Server starting on port {PORT}...")
    print(f"  Webhook URL: http://localhost:{PORT}/voice/incoming")
    print()
    print("  ═══════════════════════════════════════════════════════")
    print("  NEXT STEPS:")
    print("  1. In another terminal, start ngrok:")
    print(f"     ngrok http {PORT}")
    print("  2. Copy the ngrok HTTPS URL (e.g. https://abc123.ngrok.io)")
    print("  3. Go to Twilio Console → Phone Numbers → +18557893570")
    print("     Set Voice webhook to: https://abc123.ngrok.io/voice/incoming")
    print("  4. Call +1 855 789 3570 from your phone")
    print("  5. Talk to GPTitta!")
    print("  ═══════════════════════════════════════════════════════")
    print()
    print("  Fab DECIDES. Claudita PLANS. GPTitta EXECUTES.")
    print()
    
    app.run(host=HOST, port=PORT, debug=False)
