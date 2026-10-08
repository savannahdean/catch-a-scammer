"""The Messenger: chat with the person who reported the case (the "client").

The client is not a chatbot. It is a small keyword engine over facts the
scenario wrote (case_client_facts) and a personality (client_profiles):

  1. classify()   turns the player's message into intents ("money", "when",
                  "pressure", ...) and finds facts whose own keywords appear.
  2. Each fact the message points at is answered in the personality's voice.
     Secrets follow the personality's disclosure rule:
        upfront  tells it as soon as you touch the topic
        asked    tells it when you ask about it directly, or ask twice
        pressed  dodges the first time; ask again directly, or push ("are you
                 leaving something out?"), and it comes out
        proof    lies, and keeps lying, until you SHOW them a record from your
                 investigation that proves it (an entity in the fact's `proof`)
  3. Anything the engine can't place gets a "what are you saying?" reply in
     that personality's voice, and costs patience.

Patience is the mood meter. Unclear messages, pinning things the client knows
are wrong, returned reports, and leaving a demanding client waiting (nags)
drain it. Revealing something useful and reassuring them restore a little.
At zero, from MEDIUM up, the client withdraws the case (status 'failed').

When a client finally tells a secret they also hand over the records it
mentions (`unlocks`): those are withheld from the CaseDesk exhibits until then.
"""
from __future__ import annotations

import random
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .cards import Ctx, card_for, ent_int
from .db import tx
from .guard import case_by_seq, rate_limit

router = APIRouter(prefix="/api")

# Kinds of record the client has seen with their own eyes, so they can say
# "that's the one" or "that's not it". They can't judge an IP or a certificate.
RECOGNIZABLE = {"persona", "social_post", "phone", "email_message", "email_address", "sms_message",
                "payment_account", "crypto_wallet", "image", "document", "audio_recording"}

# --------------------------------------------------------------------------- intents
# A pattern is a word, a phrase (has a space), or a prefix ending in '*'.
INTENTS: dict[str, list[str]] = {
    "greet": ["hi", "hello", "hey", "hiya", "howdy", "yo", "greetings", "good morning", "good afternoon",
              "good evening", "nice to meet", "how are you", "how's it going", "hows it going"],
    "ack": ["ok", "okay", "k", "got it", "i see", "understood", "alright", "all right", "cool", "noted",
            "makes sense", "yes", "yeah", "yep", "no", "nope", "sure", "hmm", "mhm"],
    "story": ["what happened", "happen*", "tell me", "explain", "describe", "walk me through", "from the beginning",
              "story", "what's going on", "whats going on", "what is going on", "details", "situation", "problem",
              "issue", "go on", "start over"],
    "when": ["when", "what time", "time", "date", "day", "how long ago", "timeline", "today", "yesterday",
             "last night", "morning", "night", "week"],
    "contact": ["email*", "e-mail", "mail", "text", "texts", "texted", "sms", "message*", "dm", "dms", "contact*",
                "reach*", "sender", "sent you", "who sent", "inbox", "chat*", "reply", "replied", "wrote"],
    "link": ["link*", "click*", "url", "website*", "site", "sites", "page", "open*", "browser", "browsing", "popup",
             "pop-up", "pop up", "visit*", "went to", "go to", "online"],
    "login": ["password*", "login", "log in", "logged", "sign in", "signed in", "signin", "credential*", "username",
              "2fa", "mfa", "code", "codes", "typed", "entered", "enter"],
    "money": ["pay", "paid", "paying", "payment*", "money", "wire*", "transfer*", "gift card*", "bitcoin", "crypto",
              "btc", "bank*", "card", "cards", "venmo", "fee*", "charge*", "deposit*", "invest*", "account number",
              "funds", "cash", "spent", "spend", "cost", "lose", "lost", "send", "sent", "ransom"],
    "amount": ["how much", "amount", "dollars", "$", "total", "sum", "price", "how many"],
    "device": ["download*", "install*", "file*", "attachment*", "zip", "remote", "computer", "laptop", "pc",
               "screen", "virus*", "malware", "software", "app", "apps", "program", "webcam", "camera",
               "device*", "access", "document*", "pdf"],
    "who": ["who", "name", "person", "guy", "girl", "man", "woman", "profile", "photo*", "picture*", "pics",
            "met", "boyfriend", "girlfriend", "partner", "friend", "boss", "account", "handle", "know them"],
    "phone": ["phone", "number", "call", "calls", "called", "calling", "voicemail*", "rang", "ring", "caller"],
    "pressure": ["anything else", "leave out", "left out", "leaving out", "missing", "hiding", "hide", "not telling",
                 "forgot", "forget", "is that all", "thats all", "that's all", "be honest", "honest*", "truth",
                 "lie", "lying", "lied", "come on", "omit*", "whole story", "full story", "all of it",
                 "something else", "else happen*", "not saying"],
    "reassure": ["working on", "investigating", "looking into", "hold on", "give me", "bear with", "almost",
                 "progress", "update", "on it", "be patient", "patience", "doing my best", "getting close",
                 "close to", "one moment", "one sec", "hang on", "soon", "making headway", "still here"],
    "apology": ["sorry", "apolog*", "my bad", "my mistake", "forgive"],
    "thanks": ["thank*", "thx", "ty", "appreciate*", "perfect", "helpful", "awesome", "great"],
    "bye": ["bye", "goodbye", "talk later", "ttyl", "good night", "see you", "talk soon"],
    "insult": ["stupid", "idiot", "dumb", "moron", "shut up", "pathetic", "stfu", "loser", "gullible", "fool"],
    "theory": ["who did", "who do you think", "suspect", "theory", "behind this", "responsible", "who's behind",
               "whos behind", "your guess", "any idea who", "think it was"],
    "advise": ["you should", "change your", "cancel your", "call your bank", "freeze", "don't pay", "do not pay",
               "dont pay", "don't send", "dont send", "stop sending", "block them", "report it", "contact your bank",
               "reset your"],
}
SOCIAL = {"greet", "ack", "reassure", "apology", "thanks", "bye", "insult", "theory", "advise"}
FACT_TOPICS = {"story", "when", "contact", "link", "login", "money", "amount", "device", "who", "phone"}


def _norm(text: str) -> str:
    t = text.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9$@'\-\s]", " ", t)
    return " " + re.sub(r"\s+", " ", t).strip() + " "


def _hits(norm: str, tokens: set[str], pattern: str) -> bool:
    if pattern.endswith("*"):
        stem = pattern[:-1]
        if " " in stem:
            return f" {stem}" in norm
        return any(tok.startswith(stem) for tok in tokens)
    if " " in pattern or not pattern.isalnum():
        return f" {pattern} " in norm or (not pattern.isalnum() and pattern in norm)
    return pattern in tokens


def classify(text: str) -> tuple[set[str], str, set[str]]:
    norm = _norm(text)
    tokens = set(norm.split())
    found = {name for name, pats in INTENTS.items() if any(_hits(norm, tokens, p) for p in pats)}
    return found, norm, tokens


def keyword_hit(norm: str, tokens: set[str], keywords: list[str]) -> bool:
    return any(_hits(norm, tokens, k) for k in keywords)


# --------------------------------------------------------------------------- voices
# Lines each personality uses. {label}, {theory}, {time} are filled in.
VOICE: dict[str, dict[str, list[str]]] = {
    "default": {
        "open": ["Hi. Thanks for taking my case."],
        "greet": ["Hi.", "Hello."],
        "ack": ["Okay.", "Alright."],
        "confused": ["Sorry, I don't understand the question.", "I'm not sure what you're asking."],
        "prefix": [""],
        "repeat": ["Like I said, "],
        "deflect": ["I don't think that matters.", "I'd rather not get into that."],
        "deny": ["I've told you everything."],
        "admit": ["...Okay. I should have said this before. "],
        "nothing_more": ["That's everything I know."],
        "no_fact": ["No, nothing like that.", "Not that I know of."],
        "confirm": ["Yes, that's the one.", "That's it."],
        "wrong_evidence": ["No, that's not it.", "That's not the one."],
        "unknown_evidence": ["I've never seen that before."],
        "technical": ["I don't know what that is. You're the expert."],
        "shown_no_proof": ["Okay? I don't see what that has to do with me."],
        "wrong_pin": ["Why is {label} in my case file? That has nothing to do with what happened to me."],
        "wrong_report": ["The report came back wrong? Please double-check before sending things in my name."],
        "reassure": ["Okay. Thanks for the update."],
        "apology": ["It's okay."],
        "thanks": ["Thank you, too."],
        "bye": ["Okay. Talk soon."],
        "insult": ["Excuse me? That's uncalled for."],
        "advise": ["Okay, I'll do that."],
        "theory": ["I have no idea who did it. That's why I came to you."],
        "nag": ["Hello? Any update?"],
        "low": ["I'm starting to lose confidence in this."],
        "fired": ["I'm done. I'm taking this to someone else."],
        "solved": ["Thank you for sorting this out."],
        "time_limit": [""],
        "tmi": [],
    },
    "sweet": {
        "no_fact": ["Hmm, no, I don't think so! Sorry!"],
        "open": ["Hi! Thank you so much for taking my case. I really appreciate it 💛",
                 "Hello! Oh, I'm so glad someone is looking into this. Thank you!"],
        "greet": ["Hi again! 😊", "Hello! How can I help?"],
        "ack": ["😊", "Okay!"],
        "confused": ["Sorry, I'm not sure I understand! Could you ask that another way?",
                     "Oh, I'm sorry, I don't follow. What would you like to know?"],
        "prefix": ["Of course! ", "Sure thing! ", "", "Happy to help! "],
        "repeat": ["Like I mentioned, ", "Just to repeat, "],
        "deflect": ["Hmm, I don't think so? But ask me anything!"],
        "deny": ["I've told you everything I can think of, I promise!"],
        "admit": ["Oh! You're right, I forgot to mention it. "],
        "nothing_more": ["I think that's everything! Let me know if you need anything else."],
        "confirm": ["Yes! That's the one.", "That's it, yes!"],
        "wrong_evidence": ["Hmm, no, I don't think that's it. Sorry!"],
        "unknown_evidence": ["I've never seen that before, sorry!"],
        "technical": ["That looks very technical! I trust you with that part 😊"],
        "wrong_pin": ["Oh, I don't think {label} has anything to do with it. That's not the one I dealt with!"],
        "wrong_report": ["Oh no, it came back wrong? That's okay, I know you'll figure it out!"],
        "reassure": ["Take your time, really! Thank you for working on this.", "No rush at all 💛"],
        "apology": ["Oh, don't apologize! You're doing great."],
        "thanks": ["No, thank YOU!", "Of course! Thank you for helping me."],
        "bye": ["Bye! Thanks again!"],
        "insult": ["Oh... okay. I'm sorry if I did something wrong."],
        "advise": ["Okay, I'll do that right away. Thank you!"],
        "theory": ["I really have no idea who would do this. That's why I came to you!"],
        "solved": ["You did it! Thank you SO much. I can't tell you how relieved I am 💛"],
    },
    "oversharer": {
        "no_fact": ["Nope! Well, not that I remember. My memory is like a sieve."],
        "open": ["Hi! Okay, I'm going to tell you EVERYTHING, because I'd rather you have too much than too little."],
        "greet": ["Hi hi! Ask me anything, I'm an open book."],
        "confused": ["I'm not sure what you mean, but I'm happy to keep talking! What do you want to know?"],
        "prefix": ["Oh, totally! ", "Great question. ", "Okay so, ", ""],
        "repeat": ["I think I said this, but just in case: "],
        "deflect": ["Hmm, not that I remember!"],
        "deny": ["Honestly I've told you everything, plus a lot you probably didn't need!"],
        "admit": ["OH. Right. I can't believe I left that out, of all things. "],
        "nothing_more": ["That's literally everything. Well, I could tell you about my weekend, but."],
        "confirm": ["YES. That's it exactly!"],
        "wrong_evidence": ["No, that's not it. Although it does look a bit similar!"],
        "technical": ["I have no idea what that is, but it looks impressive."],
        "wrong_pin": ["Hmm, {label}? That's not the one I dealt with. Just so you know!"],
        "reassure": ["No problem! Take all the time you need."],
        "thanks": ["Aw, of course!"],
        "insult": ["Oh. Well. That wasn't very nice."],
        "advise": ["Good idea! Doing it now. Well, after lunch."],
        "theory": ["Ooh, no idea. My sister thinks it's 'the Russians' but she thinks everything is."],
        "solved": ["Oh my gosh, thank you! I'm telling everyone about you."],
        "tmi": ["Also, not sure if it matters, but my neighbor's dog was barking all night before this happened.",
                "Oh, and I'd just switched to a new phone case that week. A blue one.",
                "I should mention I was eating cereal at the time. Probably not important.",
                "My sister says I'm too trusting. She's probably right.",
                "Also my Wi-Fi password is my cat's name. Is that bad? Her name is Biscuit.",
                "I'd also had about three coffees that day, so I was a bit jittery.",
                "Side note: my printer has been acting weird too, but it's always been weird."],
    },
    "confused": {
        "no_fact": ["Oh, no, I don't think so, dear."],
        "open": ["Hello? Is this the computer detective? My grandson said I should talk to you.",
                 "Hello, dear. I hope I'm doing this right. Is this where I type?"],
        "greet": ["Hello, dear.", "Oh, hello again."],
        "confused": ["I'm sorry, dear, I don't understand all these computer words. Can you ask me more simply?",
                     "Oh my. I'm not sure what you mean. Could you say that a different way?"],
        "prefix": ["Well, let me think... ", "Oh, yes. ", "Hmm. ", ""],
        "repeat": ["As I said, dear, "],
        "deflect": ["Oh, I don't think so. I'm not very good with these things.", "I'm not sure, dear. Is that important?"],
        "deny": ["I think I've told you all I remember."],
        "admit": ["Oh! Oh dear, I didn't think that mattered. "],
        "nothing_more": ["That's all I can remember, I'm afraid."],
        "confirm": ["Yes, I think that's the one.", "That looks like it, yes."],
        "wrong_evidence": ["No, I don't think so, dear."],
        "technical": ["That's all gibberish to me, I'm afraid. You're the expert."],
        "wrong_pin": ["Dear, I don't recognize {label} at all. Are you sure that's mine?"],
        "reassure": ["Thank you, dear. I'll wait."],
        "thanks": ["You're very kind."],
        "insult": ["Well! There's no need to be rude."],
        "advise": ["Oh, I'll have my grandson help me do that."],
        "theory": ["I couldn't say, dear. These computer people are all so clever."],
        "nag": ["Hello? Are you still there, dear?", "I haven't heard from you in a while. Is everything all right?"],
        "solved": ["Oh, thank you, dear. I'll tell everyone at church about you."],
    },
    "anxious": {
        "no_fact": ["No? I don't think so? Should there be??"],
        "open": ["Hi. Thank you for picking this up. I haven't slept. Please tell me this is fixable.",
                 "Hi, hi. Okay. Thank you. I'm really scared, so sorry if I ramble."],
        "greet": ["Hi. Sorry. Hi.", "Hey. Any news?"],
        "confused": ["Sorry, I'm so frazzled. What do you mean?", "I don't understand, sorry. Can you ask again?"],
        "prefix": ["Okay, okay. ", "Sorry, yes. ", ""],
        "repeat": ["Sorry, I think I already said, but "],
        "deflect": ["I... I don't think so? Why, is that bad?", "Um. I don't remember. Does it matter?"],
        "deny": ["I think that's everything. I'm sorry if I'm forgetting something, my head is a mess."],
        "admit": ["Oh no. I should have told you. I panicked. "],
        "nothing_more": ["I think that's everything. Is it bad? Be honest."],
        "confirm": ["Yes, that's it. Oh god."],
        "wrong_evidence": ["No, that's not it. Is that bad? Is someone else involved??"],
        "technical": ["I don't know what that is. Is it bad?"],
        "wrong_pin": ["Wait, why is {label} in my file? That's not the one. Are you sure you're on the right track??"],
        "wrong_report": ["It came back WRONG? Oh no. Oh no oh no. What happens now?"],
        "reassure": ["Okay. Okay, thank you. Please keep me posted.", "Thank you. Sorry for being like this."],
        "apology": ["No, I'm sorry, I'm just stressed."],
        "thanks": ["Thank you. Really."],
        "insult": ["...okay. I'm sorry."],
        "advise": ["Okay, doing it right now. Should I do anything else??"],
        "theory": ["I don't know! Do you think it's someone I know?? Oh god."],
        "nag": ["Hey, are you still there?", "Sorry to bother you, I'm just really worried.",
                "Should I cancel my cards?? I don't know what to do.", "Did you find anything yet? Anything at all?",
                "Sorry. Me again.", "Is it bad that you're quiet? It's bad, isn't it."],
        "low": ["I don't know if this is working. Maybe I should go to someone else."],
        "fired": ["I'm sorry. I can't keep waiting like this. I'm going to find someone else."],
        "solved": ["Oh thank god. Thank you. Thank you so much. I can finally sleep."],
    },
    "busy": {
        "no_fact": ["No."],
        "open": ["I have ten minutes between meetings. What do you need?", "Make it quick. What do you need from me?"],
        "greet": ["Yes?", "Go ahead."],
        "ack": ["Good.", "Fine."],
        "confused": ["I don't have time to decode that. Be specific.", "Not following. What exactly do you need?"],
        "prefix": ["Short version: ", "Quickly: ", ""],
        "repeat": ["As I said: "],
        "deflect": ["Not relevant. Next question.", "I don't see how that matters."],
        "deny": ["That's everything. Let's move on."],
        "admit": ["Fine. For the record: "],
        "nothing_more": ["That's all I have. Anything else?"],
        "confirm": ["Yes. That one."],
        "wrong_evidence": ["No."],
        "technical": ["No idea. Your department."],
        "wrong_pin": ["{label} isn't part of this. Focus."],
        "wrong_report": ["Wrong? I need this done right the first time."],
        "reassure": ["Fine. Keep me updated.", "Noted."],
        "apology": ["Just get it done."],
        "thanks": ["Sure."],
        "insult": ["Watch your tone."],
        "advise": ["Fine. I'll have my assistant handle it."],
        "theory": ["Not my job to guess. Yours."],
        "nag": ["Status?", "Any update? I need something for my three o'clock.", "I haven't heard from you. Where are we?"],
        "low": ["I'm close to escalating this to your manager."],
        "fired": ["We're done here. I'll get another firm on it."],
        "solved": ["Good. Send me the summary."],
    },
    "skeptic": {
        "no_fact": ["No. Irrelevant."],
        "open": ["Look, I already know who did this. I just need you to confirm it."],
        "greet": ["Yes, hello. Have you confirmed it yet?"],
        "confused": ["That's not a real question. Ask me something useful.", "What? No. Try again."],
        "prefix": ["Obviously, ", "As I've been saying, ", ""],
        "repeat": ["I already told you: "],
        "deflect": ["That's irrelevant. Focus on who did it.", "That doesn't matter. I know who did this."],
        "deny": ["I've told you everything you need. The rest is a waste of time."],
        "admit": ["Fine, fine. If it helps. "],
        "nothing_more": ["That's everything. Now go confirm what I told you."],
        "confirm": ["Yes, that's it. Obviously."],
        "wrong_evidence": ["No. Wrong. That's not it."],
        "technical": ["I don't need to understand it to know who did this."],
        "wrong_pin": ["{label}? No. I told you who did this. Why are you chasing that?"],
        "wrong_report": ["Wrong? Did you put down who I told you? No? There you go."],
        "reassure": ["Take as long as you like. It'll still be who I said."],
        "thanks": ["Mm-hm."],
        "insult": ["Don't take that tone with me."],
        "advise": ["I was going to do that anyway."],
        "theory": ["It's obviously {theory}. I read about them online. It's exactly their style.",
                   "I'm telling you: {theory}. Why are we even looking at anything else?"],
        "nag": ["Well? Have you confirmed it yet?", "I'm still waiting for you to confirm what I told you."],
        "low": ["Clearly you're not listening to me."],
        "fired": ["You won't listen. I'm going to someone who will."],
        "solved": ["Hm. Well. Not who I thought. Thank you."],
    },
    "evasive": {
        "no_fact": ["No."],
        "open": ["Hi. Um, I guess I should explain what happened. It's kind of embarrassing.",
                 "Hey. Thanks. This is a bit awkward to talk about."],
        "greet": ["Hi.", "Hey."],
        "confused": ["Sorry, what do you mean?", "I'm not sure what you're asking."],
        "prefix": ["Um, ", "So, ", ""],
        "repeat": ["Like I said, "],
        "deflect": ["I'd rather not get into that. It's not important.", "Why does that matter? Can we focus on the scammer?",
                    "Um. Let's move on."],
        "deny": ["That's... that's everything. Mostly. Can we move on?"],
        "admit": ["...Okay. Fine. I didn't want to say this. ", "Ugh. Okay, I'll be honest. "],
        "nothing_more": ["That's all. Really."],
        "confirm": ["Yeah. That's it."],
        "wrong_evidence": ["No, that's not it."],
        "technical": ["I don't know what that is."],
        "wrong_pin": ["Wait, why is {label} in there? That's not related to me."],
        "reassure": ["Okay. Thanks."],
        "thanks": ["Thanks."],
        "insult": ["Wow. Okay."],
        "advise": ["Okay. I'll do that."],
        "theory": ["No idea. Can you just find out?"],
        "nag": ["Hey, any news?", "Is everything okay? You went quiet."],
        "solved": ["Thank you. And thanks for not making it weird."],
    },
    "liar": {
        "no_fact": ["No.", "Nope."],
        "open": ["Hi. Thanks for taking this. It's pretty straightforward, honestly.",
                 "Hey. It's a simple case, I think. I'll tell you what happened."],
        "greet": ["Hey.", "Hi there."],
        "confused": ["Not sure what you mean.", "What are you asking, exactly?"],
        "prefix": ["Sure. ", "", "Yeah, "],
        "repeat": ["Like I told you, "],
        "deflect": ["No. Nothing like that.", "Nope."],
        "deny": ["I've told you everything. Why would I lie to the person helping me?",
                 "That's all there is to it. Seriously.", "I already answered that."],
        "admit": ["...Where did you get that? Okay. Okay, fine. ", "...I didn't think you'd find that. Alright. "],
        "nothing_more": ["That's the whole story."],
        "confirm": ["Yeah, that's it."],
        "wrong_evidence": ["Never seen it."],
        "technical": ["No idea what that is."],
        "shown_no_proof": ["So? That doesn't change anything I told you.", "Okay. And?"],
        "wrong_pin": ["Why's {label} in my file? That's not mine."],
        "reassure": ["Cool. Let me know."],
        "thanks": ["Sure."],
        "insult": ["Wow. Rude."],
        "advise": ["Yeah, I'll do that."],
        "theory": ["Some scammer overseas, probably. Does it matter?"],
        "nag": ["So? Any news?", "Hello? You there?"],
        "low": ["You know what, I don't like how this is going."],
        "fired": ["Forget it. I'll handle it myself."],
        "solved": ["...Thanks. And sorry I wasn't straight with you at first."],
    },
    "rude": {
        "no_fact": ["no. next question.", "no. what else."],
        "open": ["Finally. Took you people long enough. Somebody scammed me and I want it fixed. Today.",
                 "Oh good, someone finally picked this up. Don't waste my time."],
        "greet": ["what.", "yeah yeah, hi. what do you want."],
        "ack": ["...", "ok and?", "great. so?"],
        "confused": ["what the hell are you saying", "what? that makes zero sense. try again",
                     "are you even reading what you type?", "speak english. what do you actually want to know"],
        "prefix": ["fine. ", "ugh. ", "", "if you must know, "],
        "repeat": ["i ALREADY told you. "],
        "deflect": ["none of your business. find the scammer.", "why the hell does that matter",
                    "i'm not answering that. do your job."],
        "deny": ["i told you everything. stop asking.", "are you calling me a liar?"],
        "admit": ["...fine. FINE. ", "ugh. okay. happy now? "],
        "nothing_more": ["that's it. now go do something with it."],
        "confirm": ["yes. that one. obviously."],
        "wrong_evidence": ["no. that's not it. pay attention."],
        "unknown_evidence": ["never seen that in my life."],
        "technical": ["how should i know what that is. that's YOUR job."],
        "wrong_pin": ["why are you looking at {label}?? that's got nothing to do with me. you're wasting my time."],
        "wrong_report": ["you got it WRONG? are you kidding me?"],
        "reassure": ["you'd better be.", "working on it. sure. i'll believe it when i see it."],
        "apology": ["whatever. just fix it.", "yeah, you should be sorry."],
        "thanks": ["don't thank me, fix it."],
        "bye": ["don't you dare disappear on me."],
        "insult": ["excuse me?? who do you think you're talking to", "wow. real professional."],
        "advise": ["already did that. i'm not an idiot."],
        "theory": ["how would i know? figure it out."],
        "nag": ["hello??", "HELLO", "are you even working on this", "i'm still waiting", "this is ridiculous",
                "answer me", "do you have ANY update", "unbelievable"],
        "low": ["i'm about two seconds from finding someone else to do this.", "last chance. i mean it."],
        "fired": ["that's it. i'm done. i'm taking this to someone who actually knows what they're doing."],
        "solved": ["about time. ...thanks, i guess."],
        "time_limit": ["you've got {time} to come back to me with something. i'm not waiting around."],
    },
}


def line(personality: str, key: str, rng: random.Random, **fmt) -> str:
    pool = VOICE.get(personality, {}).get(key) or VOICE["default"].get(key) or [""]
    return rng.choice(pool).format(**fmt) if pool else ""


def say_fact(personality: str, body: str, rng: random.Random, opening: bool = False) -> str:
    """A fact in the personality's voice. In the opening statement there is no
    "Sure." in front: nobody has asked anything yet."""
    pre = "" if opening else line(personality, "prefix", rng)
    text = pre + (body[0].lower() + body[1:] if pre and personality == "rude" and body else body)
    if personality == "rude":
        text = text.rstrip(".") + rng.choice([".", "", ". happy?", ". obviously."])
    if personality == "busy" and len(text) > 160:
        text = text.split(". ")[0].rstrip(".") + ". " + ". ".join(text.split(". ")[1:2]).rstrip(".") + "."
    return text


# --------------------------------------------------------------------------- state
def case_uuid(conn, n: int) -> UUID:
    """The case with this number, if the request carries its X-Case-Key (server/guard.py)."""
    return case_by_seq(conn, n)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(conn, cid: UUID, lock: bool = True) -> Optional[dict]:
    row = conn.execute(f"""select cc.*, p.label, p.summary, p.confused_cost, p.wrong_pin_cost, p.wrong_report_cost,
                                  p.pressure_cost, p.nag_after_s, p.nag_cost, p.nag_burst, p.disclosure, p.volunteers,
                                  p.has_theory, c.status, c.difficulty, c.victim_name, c.victim_role, c.case_code,
                                  d.client_can_fire
                           from case_client cc join client_profiles p on p.key=cc.personality
                           join cases c on c.id=cc.case_id join difficulty_profiles d on d.level=c.difficulty
                           where cc.case_id=%s {'for update of cc' if lock else ''}""", (cid,)).fetchone()
    return row


def _facts(conn, cid: UUID) -> list[dict]:
    return conn.execute("select * from case_client_facts where case_id=%s order by ord", (cid,)).fetchall()


def _rng(conn, cid: UUID) -> random.Random:
    n = conn.execute("select count(*) n from client_messages where case_id=%s", (cid,)).fetchone()["n"]
    return random.Random(f"{cid}:{n}")


def _post(conn, cid: UUID, sender: str, body: str, patience: Optional[int], *, intents=(), evidence=None,
          cards=None) -> None:
    from psycopg.types.json import Jsonb
    conn.execute("""insert into client_messages(case_id, sender, body, intents, evidence_id, cards, patience)
                    values (%s,%s,%s,%s,%s,%s,%s)""",
                 (cid, sender, body, list(intents), evidence, Jsonb(cards or []), patience))


def mood(patience: int, top: int) -> str:
    r = patience / max(1, top)
    return "calm" if r > 0.66 else "annoyed" if r > 0.4 else "angry" if r > 0.15 else "furious"


def _theory(conn, cid: UUID) -> Optional[str]:
    """The skeptic's wrong idea: a decoy actor, a look-alike account, or a red-herring domain."""
    for kind, fmt in (("threat_actor", "{v}"), ("persona", "that @{v} account"), ("domain", "whoever runs {v}")):
        row = conn.execute("""select coalesce(t.primary_alias, p.handle::text, e.value::text) v
                              from case_entities ce join entities e on e.id=ce.entity_id
                              left join threat_actors t on t.entity_id=e.id left join personas p on p.entity_id=e.id
                              where ce.case_id=%s and ce.role in ('false_flag','red_herring') and e.kind=%s
                              order by ce.role, e.value limit 1""", (cid, kind)).fetchone()
        if row:
            return fmt.format(v=row["v"])
    return None


def _fmt_secs(s: int) -> str:
    return f"{s // 60} minute{'s' if s // 60 != 1 else ''}" if s >= 120 else f"{s} seconds"


# --------------------------------------------------------------------------- lifecycle
def personalities(conn) -> list[dict]:
    return conn.execute("""select key, label, summary, patience, disclosure, nag_after_s, difficulties::text[] difficulties
                           from client_profiles order by patience desc, key""").fetchall()


def pick_personality(conn, difficulty: str, wanted: Optional[str]) -> str:
    if wanted and wanted != "random":
        if not conn.execute("select 1 from client_profiles where key=%s", (wanted,)).fetchone():
            raise HTTPException(400, f"unknown client personality '{wanted}'")
        return wanted
    keys = [r["key"] for r in conn.execute("select key from client_profiles where %s = any(difficulties)",
                                           (difficulty,)).fetchall()]
    return random.choice(keys or ["sweet"])


def init_client(conn, cid: UUID, personality: str) -> None:
    """Called when a case is created: the client's opening messages."""
    prof = conn.execute("select * from client_profiles where key=%s", (personality,)).fetchone()
    theory = _theory(conn, cid) if prof["has_theory"] else None
    now = _now()
    conn.execute("""insert into case_client(case_id, personality, patience, max_patience, theory, started_at,
                    last_activity_at) values (%s,%s,%s,%s,%s,%s,%s)""",
                 (cid, personality, prof["patience"], prof["patience"], theory, now, now))
    rng = random.Random(str(cid))
    p, top = personality, prof["patience"]
    _post(conn, cid, "system", f"Connected to the reporting party. Client profile from intake: {prof['label']}. "
                               f"{prof['summary']}", top)
    _post(conn, cid, "client", line(p, "open", rng), top)
    facts = _facts(conn, cid)
    told = []
    if prof["volunteers"]:
        told = [f for f in facts if f["volunteer"]][:4]
    elif personality != "rude":
        told = [f for f in facts if f["key"] == "story"]
    for f in told:
        _post(conn, cid, "client", say_fact(p, f["body"], rng, opening=True), top)
        conn.execute("update case_client_facts set revealed_at=%s where case_id=%s and key=%s", (now, cid, f["key"]))
    if personality == "oversharer":
        _post(conn, cid, "client", line(p, "tmi", rng), top)
    if theory:
        _post(conn, cid, "client", line(p, "theory", rng, theory=theory), top)
    if prof["nag_after_s"] and prof["nag_after_s"] <= 120:
        _post(conn, cid, "client", line(p, "time_limit", rng, time=_fmt_secs(prof["nag_after_s"])), top)


def _apply(conn, st: dict, delta: int, rng: random.Random, replies: list) -> int:
    """Change patience; warn when it runs low; fire the player at zero (from MEDIUM up)."""
    before = st["patience"]
    after = max(0, min(st["max_patience"], before + delta))
    conn.execute("update case_client set patience=%s where case_id=%s", (after, st["case_id"]))
    st["patience"] = after
    low = int(st["max_patience"] * 0.3)
    if after <= low < before and after > 0:
        replies.append((line(st["personality"], "low", rng), None))
    if after == 0 and st["client_can_fire"] and not st["fired_at"]:
        replies.append((line(st["personality"], "fired", rng), None))
        st["fire_now"] = True
    return after


def _fire(conn, st: dict) -> None:
    cid = st["case_id"]
    now = _now()
    conn.execute("update case_client set fired_at=%s where case_id=%s", (now, cid))
    conn.execute("update cases set status='failed', closed_at=%s where id=%s and status='open'", (now, cid))
    _post(conn, cid, "system", "The client has withdrawn the case. It is closed as FAILED; the full story is now "
                               "available in CaseDesk.", 0)
    st["fired_at"] = now
    st["status"] = "failed"


def _flush(conn, st: dict, replies: list) -> None:
    for text, cards in replies:
        if text:
            _post(conn, st["case_id"], "client", text, st["patience"], cards=cards)
    if st.pop("fire_now", False):
        _fire(conn, st)


def process_nags(conn, st: dict) -> None:
    """A demanding client chases you if you leave them waiting. Lazy: runs whenever the chat is read."""
    if st["status"] != "open" or not st["nag_after_s"] or st["fired_at"]:
        return
    now = _now()
    ref = st["last_activity_at"] or st["started_at"] or now
    due = int((now - ref).total_seconds() // st["nag_after_s"])
    if due <= 0:
        return
    rng = _rng(conn, st["case_id"])
    for _ in range(min(due, 3)):
        replies = []
        st["nags"] += 1
        for _ in range(st["nag_burst"]):
            replies.append((line(st["personality"], "nag", rng), None))
        _apply(conn, st, -st["nag_cost"], rng, replies)
        _flush(conn, st, replies)
        if st["fired_at"]:
            break
    conn.execute("update case_client set nags=%s, last_activity_at=%s where case_id=%s", (st["nags"], now, st["case_id"]))
    st["last_activity_at"] = now


def handover(conn, cid: UUID, eids: list[UUID]) -> list[dict]:
    """Records the client hands over: discovered now, shown as cards in the chat."""
    from .compat import RECORD          # legacy record shapes (domain, ip, ...); imported here to avoid a cycle
    ctx = Ctx(conn, cid, "messenger")
    out = []
    for eid in eids:
        kind = conn.execute("select kind::text k from entities where id=%s", (eid,)).fetchone()["k"]
        rec = RECORD[kind](ctx, eid) if kind in RECORD else card_for(ctx, eid)
        ctx.seen(eid)
        if rec:
            out.append(rec)
    return out


def _reveal(conn, st: dict, f: dict, text: str, replies: list) -> None:
    conn.execute("update case_client_facts set revealed_at=%s where case_id=%s and key=%s", (_now(), st["case_id"], f["key"]))
    f["revealed_at"] = _now()
    cards = handover(conn, st["case_id"], list(f["unlocks"])) if f["unlocks"] else None
    replies.append((text, cards))


# --------------------------------------------------------------------------- the conversation
def player_message(conn, cid: UUID, text: str, evidence: Optional[UUID]) -> None:
    st = _load(conn, cid)
    if not st:
        raise HTTPException(404, "this case has no client")
    if st["status"] != "open":
        raise HTTPException(409, "the case is closed; the client isn't answering")
    process_nags(conn, st)
    if st["status"] != "open":
        return
    text = (text or "").strip()[:600]
    intents, norm, tokens = classify(text)
    _post(conn, cid, "player", text or "(shared a record)", None, intents=sorted(intents), evidence=evidence)
    rng = _rng(conn, cid)
    p = st["personality"]
    facts = _facts(conn, cid)
    replies: list[tuple[str, Optional[list]]] = []
    delta = 0
    answered_secret = False

    # --- a record shown to the client
    if evidence:
        r, d, answered_secret = _evidence(conn, st, facts, evidence, rng)
        replies += r
        delta += d

    if "insult" in intents:
        replies.append((line(p, "insult", rng), None))
        delta -= max(3, st["confused_cost"])

    # --- facts the message points at
    topical = intents & FACT_TOPICS
    hit = []
    for f in facts:
        strong = bool(f["keywords"]) and keyword_hit(norm, tokens, f["keywords"])
        weak = bool(set(f["topics"]) & topical)
        if strong or weak:
            hit.append((f, strong))
    pressure = "pressure" in intents
    fresh = 0
    repeats = []
    for f, strong in hit:
        if not f["secret"]:
            if f["revealed_at"]:
                repeats.append(f)
                continue
            if fresh < 3:
                _reveal(conn, st, f, say_fact(p, f["body"], rng), replies)
                fresh += 1
                delta += 1
        else:
            out, d = _secret(conn, st, f, strong, pressure, rng, replies)
            answered_secret = answered_secret or out
            delta += d
    if hit and not fresh and repeats and not answered_secret and not any(f["secret"] for f, _ in hit):
        replies.append((line(p, "repeat", rng) + repeats[0]["body"], None))
    if topical and not hit and not answered_secret:
        replies.append((line(p, "no_fact", rng), None))     # understood, but nothing like that happened

    # --- "are you leaving something out?" with no topic attached
    if pressure and not any(f["secret"] for f, _ in hit) and not answered_secret:
        pending = [f for f in facts if f["secret"] and not f["revealed_at"]]
        if not pending:
            replies.append((line(p, "nothing_more", rng), None))
        else:
            f = pending[0]
            _, d = _secret(conn, st, f, False, True, rng, replies, bare_pressure=True)
            delta += d

    # --- the social side of the conversation
    if "theory" in intents:
        if st["theory"]:
            replies.append((line(p, "theory", rng, theory=st["theory"]), None))
        else:
            replies.append((line(p, "theory", rng, theory="someone"), None))
    if "reassure" in intents:
        recent = st["last_reassure_at"] and (_now() - st["last_reassure_at"]).total_seconds() < 60
        replies.append((line(p, "reassure", rng), None))
        if not recent:
            delta += 0 if p == "rude" else 2
        conn.execute("update case_client set last_reassure_at=%s where case_id=%s", (_now(), cid))
    if "apology" in intents and "insult" not in intents:
        replies.append((line(p, "apology", rng), None))
        delta += 1
    if "advise" in intents:
        replies.append((line(p, "advise", rng), None))
    if "thanks" in intents and not replies:
        replies.append((line(p, "thanks", rng), None))
    if "greet" in intents and not replies:
        replies.append((line(p, "greet", rng), None))
    if "bye" in intents and not replies:
        replies.append((line(p, "bye", rng), None))
    if "ack" in intents and not replies:
        replies.append((line(p, "ack", rng), None))

    if p == "oversharer" and fresh and rng.random() < 0.5:
        replies.append((line(p, "tmi", rng), None))

    # --- nothing the engine could place
    if not replies:
        replies.append((line(p, "confused", rng), None))
        delta -= st["confused_cost"]

    conn.execute("update case_client set last_activity_at=%s where case_id=%s", (_now(), cid))
    _apply(conn, st, delta, rng, replies)
    _flush(conn, st, replies)


def _secret(conn, st: dict, f: dict, strong: bool, pressure: bool, rng: random.Random, replies: list,
            bare_pressure: bool = False) -> tuple[bool, int]:
    """Apply the personality's disclosure rule to one secret. Returns (revealed, patience delta)."""
    p, mode = st["personality"], st["disclosure"]
    if f["revealed_at"]:
        if not bare_pressure:
            replies.append((line(p, "repeat", rng) + f["body"].lstrip("."), None))
        return False, 0
    asks = f["ask_count"] + 1
    conn.execute("update case_client_facts set ask_count=%s where case_id=%s and key=%s", (asks, st["case_id"], f["key"]))
    f["ask_count"] = asks
    tell = (mode == "upfront"
            or (mode == "asked" and (strong or pressure or asks >= 2))
            or (mode == "pressed" and asks >= 2 and (strong or pressure)))
    if tell:
        prefix = line(p, "admit", rng) if mode != "upfront" else line(p, "prefix", rng)
        _reveal(conn, st, f, prefix + f["body"].lstrip("."), replies)
        return True, 3
    if mode == "proof":
        if bare_pressure or asks > 2:
            replies.append((line(p, "deny", rng), None))
            return False, -st["pressure_cost"]
        replies.append((f["lie"] or line(p, "deflect", rng), None))
        return False, 0
    replies.append((line(p, "deflect", rng), None))
    return False, -(st["pressure_cost"] if bare_pressure and p == "rude" else 0)


def _evidence(conn, st: dict, facts: list[dict], eid: UUID, rng: random.Random) -> tuple[list, int, bool]:
    """The player shows the client a record. Proof breaks a secret; otherwise they say what they recognize."""
    p, cid = st["personality"], st["case_id"]
    e = conn.execute("""select e.kind::text kind, coalesce(e.label, e.value::text) label, ce.role::text role
                        from entities e left join case_entities ce on ce.entity_id=e.id and ce.case_id=%s
                        where e.id=%s""", (cid, eid)).fetchone()
    replies: list = []
    cracked = [f for f in facts if f["secret"] and not f["revealed_at"] and eid in (f["proof"] or [])]
    if cracked:
        for f in cracked:
            _reveal(conn, st, f, line(p, "admit", rng) + f["body"].lstrip("."), replies)
        return replies, 2, True
    if e["kind"] in RECOGNIZABLE:
        if e["role"] in ("initial_clue", "chain", "supporting"):
            replies.append((line(p, "confirm", rng), None))
        elif e["role"] in ("red_herring", "false_flag"):
            replies.append((line(p, "wrong_evidence", rng), None))
        else:
            replies.append((line(p, "unknown_evidence", rng), None))
    else:
        replies.append((line(p, "shown_no_proof" if st["disclosure"] == "proof" else "technical", rng), None))
    return replies, 0, False


# --------------------------------------------------------------------------- hooks from the other tools
def on_pin(conn, cid: UUID, eid: UUID) -> None:
    """Pinning something the client knows is wrong: they see the case file, and they push back."""
    st = _load(conn, cid)
    if not st or st["status"] != "open":
        return
    e = conn.execute("""select e.kind::text kind, coalesce(e.label, e.value::text) label, ce.role::text role
                        from entities e left join case_entities ce on ce.entity_id=e.id and ce.case_id=%s
                        where e.id=%s""", (cid, eid)).fetchone()
    if not e or e["kind"] not in RECOGNIZABLE or e["role"] not in ("red_herring", "false_flag"):
        return
    if conn.execute("""select 1 from client_messages where case_id=%s and sender='client' and evidence_id=%s""",
                    (cid, eid)).fetchone():
        return
    rng = _rng(conn, cid)
    label = e["label"] if len(e["label"]) <= 48 else e["label"][:45] + "..."
    replies = [(line(st["personality"], "wrong_pin", rng, label=label), None)]
    _apply(conn, st, -st["wrong_pin_cost"], rng, replies)
    for text, cards in replies:
        conn.execute("""insert into client_messages(case_id, sender, body, evidence_id, patience)
                        values (%s,'client',%s,%s,%s)""", (cid, text, eid, st["patience"]))
    if st.pop("fire_now", False):
        _fire(conn, st)


def on_report(conn, cid: UUID, correct: bool) -> None:
    st = _load(conn, cid)
    if not st:
        return
    rng = _rng(conn, cid)
    if correct:
        _post(conn, cid, "client", line(st["personality"], "solved", rng), st["patience"])
        return
    replies = [(line(st["personality"], "wrong_report", rng, theory=st["theory"] or "who I said"), None)]
    _apply(conn, st, -st["wrong_report_cost"], rng, replies)
    _flush(conn, st, replies)


def withheld(conn, cid: UUID) -> set[UUID]:
    """Records the client hasn't handed over yet (kept out of the CaseDesk exhibits)."""
    if not conn.execute("select 1 from case_client where case_id=%s", (cid,)).fetchone():
        return set()          # a case made through the UUID API has no client to ask
    rows = conn.execute("""select unnest(unlocks) u from case_client_facts
                           where case_id=%s and revealed_at is null""", (cid,)).fetchall()
    return {r["u"] for r in rows}


# --------------------------------------------------------------------------- API
def state(conn, cid: UUID) -> dict:
    st = _load(conn, cid)
    if not st:
        raise HTTPException(404, "this case has no client")
    process_nags(conn, st)
    now = _now()
    next_nag = None
    if st["nag_after_s"] and st["status"] == "open":
        ref = st["last_activity_at"] or now
        next_nag = max(0, int(st["nag_after_s"] - (now - ref).total_seconds()))
    msgs = conn.execute("""select m.id, m.sender, m.body, m.created_at, m.cards, m.patience,
                                  coalesce(e.label, e.value::text) ev_label
                           from client_messages m left join entities e on e.id=m.evidence_id
                           where m.case_id=%s order by m.id""", (cid,)).fetchall()
    closed = st["status"] != "open"
    secrets = None
    if closed:
        secrets = [{"text": f["body"].lstrip(". "), "uncovered": f["revealed_at"] is not None}
                   for f in _facts(conn, cid) if f["secret"]]
    return {
        "client": {"name": st["victim_name"], "role": st["victim_role"], "personality": st["personality"],
                   "label": st["label"], "summary": st["summary"], "patience": st["patience"],
                   "max_patience": st["max_patience"], "mood": mood(st["patience"], st["max_patience"]),
                   "can_fire": st["client_can_fire"], "fired": st["fired_at"] is not None,
                   "next_nag_in": next_nag, "chases": bool(st["nag_after_s"]), "case_status": st["status"]},
        "messages": [{"id": m["id"], "from": m["sender"], "text": m["body"], "at": m["created_at"].isoformat(),
                      "evidence": (m["ev_label"] if m["sender"] == "player" else None), "cards": m["cards"] or [],
                      "patience": m["patience"]} for m in msgs],
        "secrets": secrets,
    }


@router.get("/personalities")
def list_personalities():
    with tx() as conn:
        return personalities(conn)


@router.get("/cases/{n}/messenger")
def get_messenger(n: int):
    with tx() as conn:
        return state(conn, case_uuid(conn, n))


class MessageIn(BaseModel):
    text: str = ""
    evidence_id: Optional[int] = None     # an entity (integer id) the player shows the client


@router.post("/cases/{n}/messenger", dependencies=[Depends(rate_limit("message", "40/60"))])
def send(n: int, body: MessageIn):
    with tx() as conn:
        cid = case_uuid(conn, n)
        eid = None
        if body.evidence_id is not None:
            row = conn.execute("""select e.id from entities e join case_discoveries d on d.entity_id=e.id and d.case_id=%s
                                  where e.seq=%s""", (cid, body.evidence_id)).fetchone()
            if not row:
                raise HTTPException(409, "you can only show the client records you have found")
            eid = row["id"]
        if not body.text.strip() and not eid:
            raise HTTPException(422, "empty message")
        player_message(conn, cid, body.text, eid)
        return state(conn, cid)
