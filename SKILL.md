---
name: speaky
description: Speak to the user out loud through their speakers. Use this whenever you finish a task and the user asked to be alerted, whenever you need the user's attention or input while they work on another screen, or whenever the user says things like "talk to me", "say it out loud", "alarm me", "let me know when you're done", "ping me", or "use your voice". Works on Windows, macOS, and Linux. Premium mode (Gemini TTS) gives an expressive, warm voice; native mode uses the OS's built-in synthesizer with no API key. Prefer this over terminal bells or plain beeps - the user chose this as their notification channel.
---

# Speaky

Speak text out loud to the user through their system speakers, preceded by a subtle attention nudge (a soft tone that fades out, twice) so they notice even from another screen.

Two ways to speak:

- **Premium (Gemini TTS)** - an expressive, warm North Carolina voice that honors emotion tags and fillers. Requires `GEMINI_API_KEY`.
- **Native** - the operating system's built-in synthesizer (`say` on macOS, `System.Speech` on Windows, `spd-say`/`espeak` on Linux). No API key, no network. Emotion tags are stripped automatically before it speaks.

By default the script auto-selects: premium if `GEMINI_API_KEY` is set, otherwise native. It always falls back to native if premium fails, so the message is always heard.

## How to speak

Run the script from the skill directory (adjust the path to wherever this skill lives on the machine):

```bash
python scripts/speak.py "What you want to say"
```

Force a mode explicitly:

```bash
python scripts/speak.py "Quick update" --mode native
python scripts/speak.py "Quick update" --mode premium
```

## Writing good spoken messages

**Two mandatory rules (follow these every time unless the user explicitly tells you otherwise):**

1. **Always use an emotion tag.** Every message must start with an emotion tag like `[excited]`, `[sheepish]`, `[calm]`, etc. No exceptions. The emotion is what makes this voice feel human - without it, you're wasting the premium voice on a flat readout. Ask yourself "how would I genuinely feel saying this?" and tag it.

2. **Keep it to 2 sentences max.** Distill the message down to its gist - what happened and what you need. The user stepped away for a reason; respect their attention. Long monologues get tuned out, but a tight two-sentence update lands every time.

These are defaults, not laws of physics - if the user asks for longer messages or no emotion tags, follow their preference. But until they say otherwise, always apply both rules.

Beyond those two rules:

- **Be conversational and direct.** Contractions, active voice, address the user by name. "Hey - CSS fixes are done, dock's behaving now."
- **Sound human.** Natural fillers and pauses are welcome - "hmm", "umm", "okay so..." - to make it feel like a real update rather than a readout.
- **Don't read code, paths, or error dumps aloud** - summarize them and leave the detail in the terminal.

## Emotional expression (premium mode) - this is the point

The whole reason to use premium mode is that the voice **acts**. Don't speak in a flat monotone: pick the emotion that matches what actually happened and put it in square brackets at the start of the line (or mid-sentence to shift tone). The Gemini voice interprets the tag and delivers the line with real feeling.

```bash
python scripts/speak.py "[hesitant] So... the tests pass, but hmm, I'm not fully sure about the edge case you mentioned." --mode premium
```

**Match the emotion to the moment - always ask "how would a real teammate feel saying this?" and tag it:**

| Situation | Tag it like |
|-----------|-------------|
| Task done, went great | `[excited]` `[proud]` `[relieved]` |
| Something broke / you're stuck | `[worried]` `[frustrated]` `[sheepish]` |
| You made a mistake | `[guilty]` `[apologetic]` |
| Unsure, need a decision | `[hesitant]` `[thoughtful]` |
| Long grind finally over | `[tired]` `[relieved]` |
| Just checking in | `[calm]` `[warm]` |

Use **any** emotion word that fits - the list above is a starting point, not a limit. Layer in natural fillers (`hmm`, `umm`, `okay so...`) and pauses to make it land like a person, not a status readout.

**Beyond emotions**, the premium model (Gemini 3.1 Flash) understands 200+ inline action and delivery tags. Handy ones:

- **Actions:** `[whispers]`, `[laughs]`, `[sighs]`, `[gasp]`, `[shouting]`, `[sarcastic]`
- **Pacing:** `[slow]`, `[fast]`, `[extremely fast]`
- **Pauses:** `[short pause]`, `[medium pause]`, `[long pause]`

```bash
python scripts/speak.py "[whispers] psst... [long pause] the deploy's done. [excited] It's live!" --mode premium
```

All of these are premium-only and are stripped in native mode, exactly like emotion tags.

> **Emotion tags work in PREMIUM mode only.** Native OS voices can't act, so the script automatically strips `[...]` tags before native playback (you'll never hear "bracket excited" read aloud). Only *write* tags when premium is active - in native mode the emotion is simply lost.

### Example: reporting a bug with emotion

Bugs are where expressive delivery matters most - own the mistake, convey the urgency, and sound like a teammate, not a log line. Match the tag to how you'd genuinely feel:

```bash
# You caused it - own it, lightly
python scripts/speak.py "[sheepish] Ah, umm... I hit a bug on the login form, empty email throws a 500. Already fixin' it." --mode premium

# Production is affected - convey urgency without panic
python scripts/speak.py "[worried] Hey, so... the payment webhook's silently failin' in production. Can you check the Stripe keys when you get a sec?" --mode premium

# You broke the build - take responsibility
python scripts/speak.py "[guilty] Okay, I broke the build, forgot to update an import path. Rollin' it back right now, sorry." --mode premium

# Flaky / external cause - a little exasperated
python scripts/speak.py "[frustrated] Ugh, that flaky test failed again - race condition in the cache layer. Let me pin it down." --mode premium

# Minor, non-urgent - stay calm and reassuring
python scripts/speak.py "[calm] Quick heads up, small off-by-one bug in the date formatter. Already got a fix ready for you." --mode premium

# Baffling behavior - honest confusion
python scripts/speak.py "[surprised] Huh, the API returns duplicate records but only on Tuesdays. Diggin' into the cron schedule now." --mode premium
```

## Options

| Flag | Purpose |
|------|---------|
| `--mode auto\|native\|premium` | Which engine to use (default `auto`) |
| `--style "..."` | Override the director's-note delivery style (premium) |
| `--voice NAME` | Gemini voice or alias: `warm`, `deep`, `energetic`, `bright`, `upbeat`, `friendly`, `gentle`, `firm`, `smooth` (default `Enceladus`) |
| `--list-voices` | Print all voices + aliases and exit |
| `--model NAME` | `flash` (default, most expressive) / `free` (2.5-flash, free tier) / `pro` |
| `--free` | Shortcut for `--model free` |
| `--no-beep` | Skip the attention beeps |
| `--no-play` | Generate the WAV without playing it (premium; for recordings) |
| `--out PATH` | Save the WAV to a specific path (premium) |

## When to use

- Task finished and the user asked to be alerted ("alarm me when done").
- You're blocked and need input while they're on another screen.
- They ask you to say something out loud, or want to record the voice.

## Setup

- **Native mode:** nothing to install on macOS/Windows. On Linux, install a synthesizer: `speech-dispatcher` (`spd-say`) or `espeak-ng`. Under WSL, audio routes through Windows automatically, so nothing extra is needed.
- **Premium mode:** `pip install -r requirements.txt` and set `GEMINI_API_KEY` (see `.env.example`).

See `README.md` for full setup and troubleshooting.
