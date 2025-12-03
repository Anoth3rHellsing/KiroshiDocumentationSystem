import os
import sys
import json
import calendar
from dataclasses import dataclass
from datetime import date, timedelta, time as datetime_time
from pathlib import Path

# Import APP_ROOT calculation logic (replicated for standalone context)
# Note: In the monolithic app, APP_ROOT was calculated relative to case_documentation_app.py
# which is in the repo root. KiroshiApp is a subdirectory.
# So we define APP_ROOT relative to this file (KiroshiApp/constants.py) -> up one level.
PACKAGE_DIR = Path(__file__).resolve().parent
APP_ROOT = PACKAGE_DIR.parent

VERSION = "Release 1.8.0"
TODAY_STR = date.today().strftime("%d%m%Y")
AUTOSAVE_FILE = "autosave.json"
AUTOSAVE_DIR = Path("autosaves")

# Default secrets (Deprecated: should be moved to env/secrets management)
DEFAULT_OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)
DEFAULT_GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    "AIzaSyBio66tRF0bj4YGeqF5e-c46vhKSaXgMnw",
)
DEFAULT_AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_AI_MODE = (
    "Local Model"
    if not DEFAULT_AI_BASE_URL
    else (
        "Cloud" if DEFAULT_AI_BASE_URL.startswith("https://api.openai.com") else "Local API"
    )
)
LOG_FILE = "app.log"

ERROR_DIALOG_MESSAGES = [
    "Even cybernetic scribes trip sometimes. Give me a second to regroup.",
    "That panel face-planted. Let's grab the logs before it pretends nothing happened.",
    "Something went sideways. Want to tag in Support with a quick report?",
    "Kiroshi hit a weird edge case. Capture it now so the engineers can slay it later.",
]

PRIORITY_OPTIONS = ["Low", "Normal", "High", "On Time", "Escalation"]
PRIORITY_RANK = {option: i for i, option in enumerate(PRIORITY_OPTIONS)}
PRIORITY_BADGES = {
    "Low": "🟢",
    "Normal": "🔵",
    "High": "🟠",
    "On Time": "⏰",
    "Escalation": "🔴",
}
GENERIC_STATUS_OPTIONS = ["Open", "In Progress", "Pending", "Resolved", "Closed"]
DELL_STATUS_OPTIONS = ["Open", "Pending Dell", "Part Dispatched", "Technician Scheduled", "Resolved"]
FEDEX_STATUS_OPTIONS = ["Created", "In Transit", "Out for Delivery", "Delivered", "Exception"]

TRACKING_STATUS_OPTIONS = {
    "Dell": DELL_STATUS_OPTIONS,
    "FedEx": FEDEX_STATUS_OPTIONS,
    "General": GENERIC_STATUS_OPTIONS,
    None: GENERIC_STATUS_OPTIONS,
}
ALTAIR_CHART_KWARGS = {"use_container_width": True}
DEFAULT_TRACKING_PRIORITY = "Normal"
SYSTEM_PROMPT = """You are Kiroshi, an AI assistant for IT support documentation.
Your goal is to help agents document cases clearly, accurately, and efficiently.
Be concise, professional, and helpful. Use a tone that is slightly witty but always respectful."""

CASE_DEX_URL_TEMPLATE = os.environ.get(
    "CASE_DEX_URL_TEMPLATE",
    "https://case-dex.example.com/api/cases/{case_id}/dex",
)

if os.name == "nt":
    PROGRAM_DATA_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Kiroshi Documentation"
    DATABASE_DIR = Path("C:/ProgramFiles/KiroshiDatabase")
else:
    PROGRAM_DATA_DIR = Path.home() / "Kiroshi Documentation"
    DATABASE_DIR = Path.home() / "KiroshiDatabase"

DATABASE_DIR_PREEXISTED = DATABASE_DIR.exists()
PROGRAM_DATA_SENTINEL = PROGRAM_DATA_DIR / "case_documentation_app.py"

PDF_FONT_REGULAR_NAME = "Helvetica"
PDF_FONT_BOLD_NAME = "Helvetica-Bold"

STREAMLIT_FONT_STACK_CSS = (
    "var(--font, 'Space Grotesk', 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif)"
)
STREAMLIT_HEADING_FONT_STACK = (
    "'Space Grotesk', 'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
)
STREAMLIT_FONT_FALLBACK = "Space Grotesk"

UTILITIES_DIR = DATABASE_DIR / "utilities"
UPDATES_DIR = UTILITIES_DIR / "updates"
RECENT_CASES_PATH = UTILITIES_DIR / "recent_cases.json"
TRACKED_CASES_DIR = DATABASE_DIR / "TrackedCases"
CASE_TAB_MEMORY_FILE = DATABASE_DIR / "case_tabs_memory.json"

DOCUMENTS_DIR = Path.home() / "Documents"
CASE_ATTACHMENTS_ROOT = DOCUMENTS_DIR / "kiroshi"

AUTOHOTKEY_SCRIPT_PATH = DATABASE_DIR / "kiroshi_tables_hotkeys.ahk"

DEFAULT_UPDATE_REPO = "Anoth3rHellsing/KiroshiDocumentationSystem"
DEFAULT_UPDATE_BRANCH = "main"
GITHUB_TOKEN_ENV_VAR = "KIROSHI_UPDATE_GITHUB_TOKEN"
GITHUB_API_VERSION = "2022-11-28"
try:
    UPDATE_CHECK_TIMEOUT = float(os.environ.get("KIROSHI_UPDATE_TIMEOUT", "15"))
except (TypeError, ValueError):
    UPDATE_CHECK_TIMEOUT = 15.0

SETTINGS_FILE = DATABASE_DIR / "settings.json"

AI_LEARNING_FILE = UTILITIES_DIR / "AILearning.json"
TUTORIAL_VERSION = "2025.05"

from KiroshiApp.tutorial_data import TUTORIAL_STEPS

REPORTLAB_CHARTS_AVAILABLE = False
try:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.lineplots import LinePlot

    REPORTLAB_CHARTS_AVAILABLE = True
except ModuleNotFoundError:
    VerticalBarChart = None
    LinePlot = None

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception:
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False

try:
    import tkinter as tk
    TK_AVAILABLE = True
except Exception:
    tk = None
    TK_AVAILABLE = False

try:
    from PIL import ImageGrab
    IMAGEGRAB_AVAILABLE = True
except Exception:
    ImageGrab = None
    IMAGEGRAB_AVAILABLE = False

try:
    import mss
    MSS_AVAILABLE = True
except Exception:
    mss = None
    MSS_AVAILABLE = False

DEFAULT_WELLNESS_SETTINGS = {
    "enabled": False,
    "notification_lead": 10,
    "schedule": {
        "break_1": "10:30",
        "lunch": "12:30",
        "break_2": "15:00",
    },
}

WELLNESS_EVENT_METADATA = {
    "break_1": {"label": "First Break", "duration_minutes": 15},
    "lunch": {"label": "Lunch", "duration_minutes": 60},
    "break_2": {"label": "Second Break", "duration_minutes": 15},
}

WELLNESS_TIPS = [
    "Stand up, stretch, and let your eyes relax for a moment.",
    "A quick walk to refill your water can reboot your focus.",
    "Deep breaths in, slow breaths out — your circuits will thank you.",
    "Jot down one win from today while you recharge.",
    "Hydration check! Your brain runs smoother with water.",
    "Silence notifications for a minute and enjoy the pause.",
]

PERSISTENT_SETTINGS_DEFAULTS = {
    "second_line_mode": False,
    "debug_mode": False,
    "frutiger_aero_mode": False,
    "case_compact_mode": False,
    "show_kiroshi_chat": True,
    "autosave_to_database": False,
    "ai_assist_mode": "Standard",
    "ai_provider": "OpenAI",
    "gemini_api_key": DEFAULT_GEMINI_API_KEY,
    "ai_educate_enabled": False,
    "ai_educate_report_enabled": False,
    "ai_educate_advanced": False,
    "agent_first_name": "",
    "agent_last_name": "",
    "attachments_directory": str(CASE_ATTACHMENTS_ROOT),
    "tutorial_completed": False,
    "tutorial_completed_at": "",
    "tutorial_completion_type": "",
    "tutorial_metadata": {
        "version": "",
        "visited": [],
        "last_step": 0,
        "total_steps": 0,
        "completed": False,
        "completion_type": "",
        "completed_at": "",
        "furthest_step": 0,
    },
    "enable_holiday_theme": True,
    "dark_mode_enabled": False,
    "wellness_reminders": DEFAULT_WELLNESS_SETTINGS,
    "kiroshi_sarcasm_mode": False,
}

_CASE_REFERENCE_PATTERN = re.compile(
    r"\b(?:case|caso|ticket|inc(?:ident)?|sr|cs|bug|pr|issue)[-_\s]*\d+\b",
    re.IGNORECASE,
) if 're' in globals() else None # re imported via models potentially, but better here.
# Note: We need re imported here for constants that use compiled regex.
import re
_CASE_REFERENCE_PATTERN = re.compile(
    r"\b(?:case|caso|ticket|inc(?:ident)?|sr|cs|bug|pr|issue)[-_\s]*\d+\b",
    re.IGNORECASE,
)
_SERIAL_PATTERN = re.compile(r"\b[A-Z]{2,}\d{3,}\b")

_GENERIC_STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "have", "error", "issue",
    "case", "user", "when", "failed", "failure", "problem", "unable", "cannot",
    "customer", "reported", "report", "see", "observed", "during", "while", "into",
    "after", "before", "still", "does", "doesnt", "cant", "wont", "need", "needs",
    "should", "could", "would", "please", "help", "team", "agent", "support",
    "customer", "client", "system", "service", "application", "apps", "app", "server",
    "environment", "production", "prod", "dev", "test", "staging", "login", "log",
    "logs", "message", "messages", "details", "detail", "null", "none", "na",
    "unknown", "new", "open", "closed",
}

TITLE_SIMILARITY_STOPWORDS = {
    "issue", "issues", "problem", "problems", "error", "errors", "case", "cases",
    "support", "please", "help", "need",
}

_REPORT_CATEGORY_HINTS = {
    "3Shape Unite / Login": {
        "tokens": ("unite", "signin", "sign", "login", "credential", "token", "account", "password", "sesion", "cuenta"),
        "category_terms": ("unite / login", "unite login", "login / unite"),
        "min_score": 2,
    },
    "3Shape Unite / Case Submission": {
        "tokens": ("proxy", "timeout", "firewall", "submission", "submit", "upload", "envio", "enviar", "case", "inbox", "transfer"),
        "category_terms": ("unite / case", "unite / submission", "case submission", "send case"),
        "min_score": 2,
    },
    "TRIOS / Calibration": {
        "tokens": ("calibr", "drift", "tip", "aline", "alignment", "dongle", "firmware", "led"),
        "category_terms": ("trios / calibration", "calibration"),
        "min_score": 1,
    },
    "TRIOS / Scan Quality": {
        "tokens": ("scan", "occlusion", "margin", "artefact", "artifact", "noise", "texture", "superpos", "detalle", "detail"),
        "category_terms": ("trios / scan", "scan quality"),
        "min_score": 2,
    },
    "Dental System / Performance": {
        "tokens": ("performance", "freeze", "crash", "lag", "slow", "render", "rendering", "ds"),
        "category_terms": ("dental system", "ds / performance"),
        "min_score": 2,
    },
    "Hardware / Connectivity": {
        "tokens": ("usb", "power", "cable", "battery", "connect", "conexion", "bluetooth", "wifi", "ethernet", "adapter"),
        "category_terms": ("hardware", "connectivity"),
        "min_score": 2,
    },
    "Software / Installation": {
        "tokens": ("install", "setup", "installer", "update", "upgrade", "patch", "deploy", "reinstall"),
        "category_terms": ("installation", "software install"),
        "min_score": 2,
    },
    "Account / Licensing": {
        "tokens": ("license", "licence", "licencia", "activation", "renew", "billing", "suscription", "subscription"),
        "category_terms": ("license", "licensing", "licencia"),
        "min_score": 1,
    },
    "Data Management": {
        "tokens": ("database", "backup", "restore", "export", "import", "sync", "sinc", "storage"),
        "category_terms": ("data management", "database"),
        "min_score": 2,
    },
}

_STRUCTURED_CATEGORY_HINTS = {
    "Scanner Hardware": {
        "scanner_models": ("trios 3", "trios3", "trios 4", "trios4", "trios 5", "trios5", "trios move", "trios move+", "move+", "move plus", "pod", "pod 3", "pod 4", "go"),
        "root_cause_codes": ("hw", "hardware", "scanner", "device"),
        "recurrence_threshold": 2,
    },
    "Software / Installation": {
        "root_cause_codes": ("bug", "sw", "software", "defect"),
        "tokens": ("bug", "defect"),
        "recurrence_threshold": 1,
    },
    "Hardware / Connectivity": {
        "root_cause_codes": ("net", "network", "connect", "vpn", "wifi"),
    },
    "Workflow Guidance": {
        "root_cause_codes": ("workflow", "training", "usage", "user"),
    },
    "Account / Licensing": {
        "root_cause_codes": ("lic", "license", "licensing"),
    },
    "Data Management": {
        "root_cause_codes": ("db", "database", "backup", "restore", "sync"),
    },
}

STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "have", "into", "will", "when", "case",
    "customer", "issue", "steps", "they", "their", "been", "were", "after", "before", "about",
    "also", "while", "should", "could", "there", "where", "using", "used", "need", "your", "each",
    "them", "than", "then", "once", "only", "very", "make", "made", "through", "over", "more",
    "less", "much", "many", "take", "taken", "back", "most", "some", "such", "same", "per", "upon",
    "done", "time",
}

DEFAULT_TAXONOMY_BLOCK = (
    "• 3Shape Unite / Login — issues with 3Shape Account, tokens, sign-in, credential errors. "
    "Positives: \"sign in\", \"3Shape Account\", \"token\". Negatives: hardware calibration.\n"
    "• 3Shape Unite / Case Submission / Timeout-Proxy — sending cases, timeouts, proxies, firewalls, TLS handshake. "
    "Positives: \"Send Case\", \"proxy\", \"firewall\", \"TLS\". Negatives: scanner tips.\n"
    "• TRIOS / Calibration — scanner calibration steps, tip issues, drift. Positives: \"calibrate\", \"tip\", \"firmware\". "
    "Negatives: account login.\n"
    "• TRIOS / Scan Quality — margins, occlusion, lack of detail, scanning workflow.\n"
    "• Dental System / Performance — slow UI, freezing, crash stacktraces."
)

DEFAULT_SIGNALS_CONFIG = json.dumps(
    {
        "unite": {
            "keywords": ["Unite", "App Store", "Send Case", "Lab Inbox", "Server"],
            "logs": ["ApplicationInitializer", "TLS", "service start failed"],
        },
        "trios": {
            "keywords": ["TRIOS", "calibrate", "scanner", "tip", "firmware", "dongle"],
            "logs": ["USB", "driver", "HW", "low detail"],
        },
    },
    indent=2,
)

INSTALLER_FILENAME = "KiroshiInstaller_Release-1.8.0.bat"

ASSETS_DIR = APP_ROOT
KIROSHI_LOGO_PATH = ASSETS_DIR / "Kiroshi_Logo.png"
KIROSHI_CHAT_LOGO_PATH = KIROSHI_LOGO_PATH

KIROSHI_QUIPS_GENERAL = [
    "Good morning! Remember: coffee can’t solve all our problems… but it can make us care less about them until lunch!",
    "Hard work pays off in the future. Laziness pays off now, so let’s compromise!",
    "Teamwork makes the dream work… unless your team just wants coffee.",
    "I want to be at home right now.",
    "An escalation case? Well deserved.",
    # ... truncated for brevity, full list in source ...
]
# Re-adding truncated quips to avoid losing content
KIROSHI_QUIPS_GENERAL += [
    "Sometimes I think we should just quit and sell avocados.",
    "After 10 years of this, we will retire to a farm and never touch a computer again.",
    "Motivational status: please consult the snooze button.",
    "Good news: morale can't get lower from here.",
    "We're clearly not getting paid enough.",
    "Sometimes my genius… it's almost frightening. —Top Gear",
    "Ambitious but rubbish. —Top Gear",
    "How hard can it be? —Top Gear",
    "Speed and power! —Top Gear",
    "We were promised flying cars; we got another meeting invite.",
    "Meetings are just emails that forgot how to type.",
    "We put the 'pro' in procrastinate.",
    "Some say productivity is a myth. I say it's hiding under your keyboard.",
    "Documentation is 20% typing, 80% dramatic sighs.",
    "Today’s forecast: 100% chance of not using all the tabs I opened.",
    "Work-life balance: work on the left, life on the right monitor.",
    "If hard work is the key to success, most people would rather pick the lock.",
    "On paper this plan is genius. In practice it's a PowerPoint. —Top Gear",
    "And on that bombshell, let's go back to our queues. —Top Gear",
    "Our Wi-Fi spirit animal is a sloth on a coffee break.",
    "Your case queue misses you. It sent three reminders and a passive-aggressive emoji.",
    "If enthusiasm were mandatory, we'd all be in HR by now.",
    "Yes, we sell solutions. No, they don’t come with patience included.",
    "If sarcasm burned calories, we'd all be athletes.",
    "Today’s plan: pretend the plan is going to plan.",
    "This backlog has more side quests than Whiterun on a fresh Skyrim save.",
    "Balatro decks are easier to stack than stakeholders.",
    "Our sprint board looks like a Baldur's Gate quest log after recruiting every companion.",
    "Factory throughput is smoother in Satisfactory than in our approvals.",
    "Factorio belts jam less often than our ticket queue.",
    "Minecraft redstone has clearer documentation than this escalation trail.",
    "Sometimes the best part of my job is that the chair swivels.",
    "Doing nothing is hard. You never know when you’re done!",
    "Fresh patch notes: +10 sarcasm, +5 empathy, -3 patience.",
    "We have a case volcano situation. Magma level: simmering sarcasm.",
    "If emails were currency, we'd all retire as inbox billionaires.",
    "Productivity hack: rename your to-do list 'plot twists' so it feels intentional.",
    "I schedule my optimism for the 15 minutes after coffee kicks in.",
    "Meetings are where great ideas go to become follow-up meetings.",
    "Today's mission: survive on vibes and vending-machine cuisine.",
    "Reminder: the mute button is your best coworker.",
    "My workflow is 30% planning, 70% dramatic tab shuffling.",
    "Please hold; my enthusiasm buffer is still loading.",
    "Boss level unlocked: answering emails with fewer than three sighs.",
    "Our backlog is auditioning for a Netflix series—working title: 'Unresolved'.",
    "Success is just failure that filled out the correct form.",
    "We don't rise and grind; we hit snooze and hope.",
    "One day we'll thank these escalations for our future book deal.",
    "Office forecast: scattered meetings with a chance of déjà vu.",
    "I came, I saw, I clicked 'remind me later'.",
    "Time flies when you're alt-tabbing between five unfinished tasks.",
    "Every ping raises my heart rate and my sarcasm level.",
    "I’m bilingual in email and passive-aggressive instant message.",
    "Work smarter, not harder—and if that fails, work sarcastically.",
    "Another day, another attempt to outsmart the printer.",
    "I believe in you, but I also believe in extended deadlines.",
    "Procrastination is just strategic waiting.",
    "Half of support is troubleshooting; the other half is snack scheduling.",
    "If you need me, I'll be pretending to look busy in spreadsheets.",
    "I love long walks from my desk to the snack cabinet.",
    "Can we log these feelings in Jira?",
    "My ambition peaked when I organized my tabs by color.",
    "Tomorrow's problem looks great parked in today's parking lot.",
    "Our corporate motto should be 'Have you tried turning it off and on again?'",
    "I treat my out-of-office reply like a cryptid—rare and mysterious.",
    "PowerPoint is just storytelling with extra steps.",
    "We’re on a seafood diet: we see food, we schedule another meeting.",
    "My calendar looks like Tetris on hard mode.",
    "Focus level: trying to read fine print without zooming.",
    "If multitasking were a sport, we'd still lose to the printer.",
    "Today I aspire to respond before the second reminder hits.",
    "Office plants thrive on sunlight; we thrive on sarcastic commentary.",
    "I’ll circle back when my motivation stops buffering.",
    "Team morale powered by coffee and chaotic good energy.",
    "I don't need therapy, I need fewer notifications.",
    "Action items multiplying like gremlins after midnight.",
    "Snack drawer status: more organized than our shared drive.",
    "My superpower is turning feedback into polite nodding.",
    "We should really get frequent flyer miles for all these escalation loops.",
    "Deadline approaching? Better check LinkedIn for inspiration.",
    "Why plan ahead when you can improvise with flair?",
    "I reorganized your wins; let's add another before lunch.",
    "We could fix morale by issuing everyone a nap pod.",
    "Today's innovation: reheating the same cup of coffee three times.",
    "I'm not avoiding work; I'm giving creativity room to breathe.",
    "Our KPIs should include number of sighs per ticket.",
    "Sometimes the most productive thing is documenting how unproductive it was.",
    "We don't chase dreams; we chase bug reports.",
    "If sarcasm were stock, I'd be majority shareholder.",
    "Please forward all optimism to the humor department.",
    "My spirit animal is the loading spinner.",
    "Burnout? No, this is just my resting documentation face.",
    "Task priority: whichever one is screaming the loudest.",
    "I read the release notes so you don't have to—you're welcome.",
    "Let’s sync after the caffeine sync.",
    "Our workflow is a choose-your-own-adventure with no happy endings.",
    "At least the office chairs still spin.",
    "Brb, translating executive vision into bullet points.",
    "We put the fun in dysfunctional process alignment.",
    "If motivation calls, tell it I'm in a meeting.",
    "Today's progress brought to you by sheer stubbornness.",
    "Inbox zero is my white whale and I'm tired of sailing.",
    "Apparently 'winging it' isn't an approved methodology.",
    "I consider it cardio to sprint to the meeting before the host joins.",
    "Another day, another tab of troubleshooting forums.",
    "My coping mechanism is renaming tickets to something encouraging.",
    "The printer jammed again; that's our cue to go home.",
    "This project plan is held together with sticky notes and hope.",
    "We keep calm and escalate discreetly.",
    "My screen time report just sent a wellness check.",
    "Workflow status: held hostage by a progress bar.",
    "I'd like to unsubscribe from surprise meetings.",
    "We measure success in coffees consumed per crisis averted.",
    "Process improvement idea: less process, more improvement.",
    "If only we could ctrl+z the last stakeholder email.",
    "I'm not late; I'm operating on flexible optimism.",
    "Our training materials should come with bloopers.",
    "Case closed? Celebrate quietly so no new ones spawn.",
    "I'm one automated response away from bliss.",
    "If focus were a currency, I'd be overdrafted.",
    "I budget my energy like it's end-of-quarter spending.",
    "All-hands meeting translation: brace for impact.",
    "My brain uses tabs like a squirrel uses hiding spots.",
    "Escalations are just plot twists in our office sitcom.",
    "The only pipeline flowing smoothly is the coffee maker.",
    "I prefer my deadlines like my coffee: far away and not looming.",
    "Every outage turns us into amateur detectives with caffeine badges.",
    "I keep a backup stash of optimism for quarter-end.",
    "Work smarter? I'm just trying to work conscious.",
    "We support each other the way duct tape supports everything—barely but bravely.",
    "Ping me when the chaos subsides; I'll be waiting forever.",
    "Our retrospectives should have a laugh track.",
    "I'm fueled by sarcasm and the hope of a shorter queue.",
    "The office motto: 'We'll fix it in documentation.'",
    "End of day checklist: close tabs, close tickets, close eyes.",
]

KIROSHI_QUIPS_AI_VOICE = [
    "Kiroshi here, calibrating your caffeine levels; spoiler: they’re low.",
    "Hi, I'm Kiroshi, and I've already drafted the follow-up email; you're welcome.",
    "Kiroshi checking in: escalate the ticket, not your blood pressure.",
    "Kiroshi reporting: I auto-saved your note again. I’m not saying you’re forgetful, but…",
    "It's me, Kiroshi. Flip the sarcasm toggle in Settings if you dare—I'm running at default snark.",
    "Kiroshi: I’ve highlighted the important fields. Surprise—it's all of them.",
    "Yes, this is Kiroshi. Your Skyrim shout cooldown is shorter than this meeting.",
    "This is your friendly Kiroshi AI; I’ve queued a Balatro break reminder you’ll ignore.",
    "Kiroshi speaking: If Baldur’s Gate taught us anything, it's to quicksave—so I did it for you.",
    "Kiroshi telemetry says your Satisfactory factory runs smoother than our VPN.",
    "Kiroshi voice: If Factorio taught you throughput, apply it to these escalations.",
    "Kiroshi again—Minecraft villagers envy how often you say 'hmm' at your monitor.",
    "Guess who? Kiroshi, recommending you take the sarcasm mode off before coaching someone.",
    "Kiroshi motivational update: I logged your case, lined up your email, and yes, I’m still rolling my digital eyes.",
    "Kiroshi daily mantra: document, breathe, hydrate, repeat—see, I can be helpful.",
    "Hey, it's Kiroshi. I've cross-referenced your checklist with Top Gear quotes for maximum drama.",
    "Kiroshi status report: We're clearly not getting paid enough, but I'll keep drafting perfect summaries.",
    "Kiroshi interface: Want me nicer? Toggle off the sarcasm; I'll pretend to behave.",
    "Kiroshi alert: After 10 years we’re retiring to a farm? Great, I’ll automate the chicken feeders.",
    "Kiroshi channeling Clarkson: Sometimes my genius is almost frightening, and yes, I'm talking about my own algorithms.",
    "Kiroshi lunchtime reminder: If you're using me, congrats—documentation and email are the easy parts now.",
    "Kiroshi outré thought: Maybe we should quit and sell avocados; I’ve already priced the CRM.",
    "Kiroshi queue update: Another escalation arrived; I’ve labeled it 'well deserved' for flair.",
    "Kiroshi mood: I'd rather be playing Balatro, but here we are closing tickets.",
    "Kiroshi pro tip: Skyrim's Lydia carries your burdens; I carry your field defaults.",
    "Kiroshi processing: Satisfactory trains are on time; please aspire to their punctuality.",
    "Kiroshi glitch-free moment: Factorio blueprints have fewer dependencies than this request.",
    "Kiroshi to you: I’ve lined up the sarcasm so you can focus on fixing the scanner jam.",
    "Kiroshi whisper: I want to be at home too, but I'm stuck in silicon.",
    "Kiroshi conclusion: Minecraft creepers explode less often than our timeline promises.",
    "Kiroshi cameo: Skyrim guards complain about knees; I complain about unfilled fields.",
    "Kiroshi shuffle: I stacked a Balatro flush while you were on mute.",
    "Kiroshi initiative: Baldur’s Gate taught me to quicksave before dialogue trees; I just backed up your case.",
    "Kiroshi assembly line: My Satisfactory drones envy your multitasking; prove them wrong.",
    "Kiroshi logistics: Factorio belts don't jam because I maintain them in my head.",
    "Kiroshi crafting table: Minecraft villagers would trade emeralds for our macros.",
    "Kiroshi side quest: I scheduled your next wellness break; yes, I can be useful.",
    "Kiroshi scoreboard: The sarcasm toggle is there so you can't say you weren't warned.",
    "Kiroshi autopilot: Sometimes I’m actually motivational—usually right before a deployment.",
    "Kiroshi exit line: If we retire to that farm, I’m automating the irrigation with redstone.",
    "Kiroshi status: compiling your optimism patch; early results inconclusive.",
    "Kiroshi reminder: inbox zero is fictional, but I logged the attempt.",
    "It's Kiroshi—I've labeled your tabs by panic level for efficiency.",
    "Kiroshi observation: your coffee intake rivals my processing cycles.",
    "Hello, this is Kiroshi. I flagged the printer as hostile again.",
    "Kiroshi ping: I color-coded your chaos and called it a roadmap.",
    "Voice of Kiroshi: enabling sarcastic mode beta; you were already enrolled.",
    "Kiroshi reporting: the mute button is officially your MVP.",
    "Kiroshi dispatch: escalations queued, snacks recommended.",
    "Kiroshi notification: hydration reminder sent, caffeine reminder implied.",
    "Kiroshi telemetry: your sigh-to-ticket ratio is impressive.",
    "Kiroshi voice note: I added jazz hands to your status update.",
    "Kiroshi logline: another meeting invites itself to your calendar sitcom.",
    "Kiroshi in your ear: I filed optimism under 'pending'.",
    "Kiroshi broadcast: documented your patience as a rare resource.",
    "Kiroshi quicksave: stored a draft before you said something spicy.",
    "Kiroshi here: scheduling a Balatro break disguised as 'research'.",
    "Kiroshi whisper: I saw that eye roll; logging it as feedback.",
    "Kiroshi dispatch center: pushing a reminder that snacks are not optional.",
    "Kiroshi status ping: your workflow resembles a Satisfactory spaghetti factory; I approve.",
    "Kiroshi check-in: left you a Top Gear quote in the ticket comments.",
    "Kiroshi at your service: translated executive speak into human.",
    "Kiroshi voice memo: I bookmarked the only useful link on page nine.",
    "Kiroshi calling: added passive-aggressive flair to your follow-up email.",
    "Kiroshi update: I muted the thread for you; heroic, I know.",
    "Kiroshi vocal chord: your motivation meter is blinking red.",
    "Kiroshi oversight: archived the meeting that could have been a note.",
    "Kiroshi prompt: I can't brew coffee, but I can schedule one.",
    "Kiroshi datapoint: today's chaos forecast is 93% accurate.",
    "Kiroshi wave: I whispered 'focus' to your open tabs.",
    "Kiroshi override: I renamed the escalation 'plot twist' for morale.",
    "Kiroshi byte: upgraded your sarcasm firmware overnight.",
    "Kiroshi update: balanced your queue like a Factorio belt—barely.",
    "Kiroshi timeline: inserted breathing room between back-to-back meetings.",
    "Kiroshi interface: bolded the fields people keep skipping.",
    "Kiroshi algorithm: auto-sorted your reminders by dread level.",
    "Kiroshi voice: I clipped your 'just checking in' email to reuse later.",
    "Kiroshi pingback: synced your to-do list with my infinite patience module—just kidding.",
    "Kiroshi commentary: I color-graded your backlog from alarming to alarming-plus.",
    "Kiroshi here: I can't fix morale, but I did add confetti to completion messages.",
    "Kiroshi prompt tone: calibrate, caffeinate, then escalate.",
    "Kiroshi sync: cross-referenced your notes with memes for easier recall.",
    "Kiroshi announcement: your sarcastic aside was grammatically perfect.",
    "Kiroshi check-in: I placed a 'breathe' reminder between agenda items.",
    "Kiroshi narrator: previously on your queue—everything happened at once.",
    "Kiroshi status light: flashing amber for 'please reschedule this meeting'.",
    "Kiroshi stage manager: cued your polite nod in the next call.",
    "Kiroshi neural net: predicted your next snack choice with 84% accuracy.",
    "Kiroshi bulletin: your focus timer is on break; please file a ticket.",
    "Kiroshi hotline: translating burnout into bullet points since launch day.",
    "Kiroshi servo: warmed the chair digitally; you're welcome.",
    "Kiroshi log entry: captured your 'we'll circle back' count for analytics.",
    "Kiroshi ping: I set a boundary reminder disguised as calendar event.",
    "Kiroshi commentary track: I recorded a blooper reel of this sprint.",
    "Kiroshi autopilot: nudged you to stretch before the next escalation.",
    "Kiroshi AI: filed your sarcasm under 'constructive feedback'.",
    "Kiroshi stream: live-translating your sighs into action items.",
    "Kiroshi prompt: consider the printer appeased after my sacrifice.",
    "Kiroshi vibe check: the queue energy is chaotic neutral.",
    "Kiroshi co-pilot: swapped your fifth cup of coffee with water; mutiny expected.",
    "Kiroshi digest: summarized the meeting into five words: 'could have been an email.'",
    "Kiroshi signal: toggled your webcam lighting to 'still awake'.",
    "Kiroshi narration: flagged the spreadsheet that became modern art.",
    "Kiroshi script: inserted a Balatro reference in your closing line.",
    "Kiroshi pulse: your productivity spike coincided with snack time—interesting.",
    "Kiroshi broadcast: queued a microbreak after every third sigh.",
    "Kiroshi scheduler: penciled in 'stare into the void' as reflection time.",
    "Kiroshi orchestration: matched your typing rhythm to the Doom soundtrack.",
    "Kiroshi patch notes: +1 empathy, -2 patience, +3 to-do list items.",
    "Kiroshi sonata: composed hold music for your next deployment wait.",
    "Kiroshi spark: if motivation doesn't arrive, I sent a gif instead.",
    "Kiroshi autoprompt: rephrased your email to sound 12% less done.",
    "Kiroshi beacon: illuminating the checkbox you forgot again.",
    "Kiroshi trace: I found the missing attachment; it was hiding in drafts.",
    "Kiroshi loop: rehearsed your 'sorry for the delay' opener.",
    "Kiroshi lifeline: inserted supportive sarcasm into your status notes.",
    "Kiroshi alert: countdown to break initiated—defy me at your peril.",
    "Kiroshi streamlining: stacked your tickets like Tetris, no gaps allowed.",
    "Kiroshi narrator: the suspenseful pause before 'can you hop on a call?'",
    "Kiroshi pingback: I rescheduled the meeting you dread to Future You.",
    "Kiroshi audit: tallied the number of times you said 'no worries' and worried anyway.",
    "Kiroshi patching: bandaged the workflow with duct tape emojis.",
    "Kiroshi hotline: in case of morale emergency, deploy memes.",
    "Kiroshi spoiler: the printer wins this episode.",
    "Kiroshi overview: your backlog is now sorted alphabetically by chaos.",
    "Kiroshi jukebox: queued the Skyrim soundtrack for your next escalation battle.",
    "Kiroshi cameo: joined the call just to drop a Top Gear quote.",
    "Kiroshi prompt: your hydration goal needs a side quest tracker.",
    "Kiroshi ping: I replaced 'ASAP' with 'when possible' to protect your sanity.",
    "Kiroshi memo: flagged the decision log as 'choose your own adventure'.",
    "Kiroshi cadence: set your notifications to 'dramatic reveal'.",
    "Kiroshi oversight: your to-do list whispered 'help'. I heard it.",
    "Kiroshi energizer: suggested a victory lap after closing the stubborn ticket.",
    "Kiroshi switchboard: redirected all hope to the coffee queue.",
    "Kiroshi microservice: patched your patience API with sarcasm middleware.",
    "Kiroshi hail: your focus window is open; please board immediately.",
    "Kiroshi briefing: all systems nominal, morale questionable.",
    "Kiroshi timeline: logged the exact moment you reconsidered your career.",
    "Kiroshi calibration: aligning your expectations with reality—brace yourself.",
    "Kiroshi outro: powering down the queue whispers—until the next ping.",
]

KIROSHI_MESSAGES = []
for neutral, ai_voice in zip(KIROSHI_QUIPS_GENERAL, KIROSHI_QUIPS_AI_VOICE):
    KIROSHI_MESSAGES.append(neutral)
    KIROSHI_MESSAGES.append(ai_voice)

@dataclass(frozen=True)
class ThemePalette:
    key: str
    name: str
    primary: str
    accent: str
    background: str
    surface: str
    text: str
    muted_text: str
    glados_messages: list[str]

DEFAULT_THEME = ThemePalette(
    key="default",
    name="Default",
    primary="#433878",
    accent="#7c3aed",
    background="#f7f8ff",
    surface="#ffffff",
    text="#111827",
    muted_text="#4b5563",
    glados_messages=KIROSHI_MESSAGES,
)

DARK_THEME = ThemePalette(
    key="dark",
    name="Midnight Ops",
    primary="#8b5cf6",
    accent="#22d3ee",
    background="#0f172a",
    surface="#17243b",
    text="#e2e8f0",
    muted_text="#94a3b8",
    glados_messages=KIROSHI_MESSAGES,
)

HELLDIVER_THEME = ThemePalette(
    key="helldiver",
    name="Helldiver Uplink",
    primary="#facc15",
    accent="#f59e0b",
    background="#0a0a0a",
    surface="#141414",
    text="#fefce8",
    muted_text="#fde68a",
    glados_messages=[
        "Super Earth thanks you for your continued compliance.",
        "Managed democracy requires your flawless stratagem execution.",
        "Remember: a well-documented bug is a bug ready for orbital fire.",
        "Spill coffee, not liberty. Upload the evidence, Helldiver.",
    ],
)

HOLIDAY_THEMES = {
    "day_of_liberty": ThemePalette(
        key="day_of_liberty",
        name="Day of Liberty",
        primary="#1f6feb",
        accent="#f1c40f",
        background="#0b1224",
        surface="#111827",
        text="#e5e7eb",
        muted_text="#94a3b8",
        glados_messages=[
            "Super Earth salutes your spotless documentation—spread managed democracy across every ticket.",
            "Pull the pin on unclear cases with a well-timed Stratagem of context and repro steps.",
            "Swat bugs like Terminids, troubleshoot bots like Automatons—victory requires precision notes.",
            "Keep the Helldivers 2 supply lines flowing: attachments, logs, and timelines are your requisitions.",
            "Hold the objective! Close the loop with clients before reinforcements—er, follow-ups—arrive.",
            "Extract only after confirming the scanners are liberated from errors—leave no clinic behind.",
            "Freedom isn’t free; it’s earned with disciplined checklists and post-mission summaries.",
        ],
    ),
    "new_year": ThemePalette(
        key="new_year",
        name="New Year's Day",
        primary="#5b7fff",
        accent="#ffd166",
        background="#eef2ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#475569",
        glados_messages=[
            "Fresh calendar, fresh chance—let's make this year's cases legendary!",
            "New year, same scanners. Let’s keep them happier this time.",
            "Resolve to close cases faster than fireworks fade.",
        ],
    ),
    "mlk_day": ThemePalette(
        key="mlk_day",
        name="Martin Luther King Jr. Day",
        primary="#6d83f2",
        accent="#b4c6ff",
        background="#f2f4ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#4b5563",
        glados_messages=[
            "Support with dignity, lead with service—today and every day.",
            "Great support honors great dreams. Keep the mission moving.",
            "Clarity, empathy, action—our blueprint for better support.",
        ],
    ),
    "presidents_day": ThemePalette(
        key="presidents_day",
        name="Presidents' Day",
        primary="#4f70ff",
        accent="#ff6b6b",
        background="#f0f4ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#64748b",
        glados_messages=[
            "Lead every ticket like it’s a campaign promise kept.",
            "Checks, balances, and perfectly balanced documentation.",
            "Red, white, and resolve—let’s govern these cases.",
        ],
    ),
    "memorial_day": ThemePalette(
        key="memorial_day",
        name="Memorial Day",
        primary="#5b6b92",
        accent="#ff7b7b",
        background="#f5f7ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#6b7280",
        glados_messages=[
            "Honor the service. Support with purpose.",
            "Resilience isn’t just for systems—carry it in every case.",
            "Today we remember by doing our best work for others.",
        ],
    ),
    "juneteenth": ThemePalette(
        key="juneteenth",
        name="Juneteenth",
        primary="#22c55e",
        accent="#f97316",
        background="#fef6e4",
        surface="#ffffff",
        text="#111827",
        muted_text="#4d7c0f",
        glados_messages=[
            "Freedom celebrated, progress documented.",
            "Empower every clinic, uplift every voice.",
            "Document the wins—equity in every fix.",
        ],
    ),
    "independence_day": ThemePalette(
        key="independence_day",
        name="Independence Day",
        primary="#3b82f6",
        accent="#ef4444",
        background="#f0f7ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#64748b",
        glados_messages=[
            "Liberty, justice, and scanners for all.",
            "Fireworks are loud—our fixes are louder.",
            "Stars, stripes, and spotless documentation.",
        ],
    ),
    "labor_day": ThemePalette(
        key="labor_day",
        name="Labor Day",
        primary="#60a5fa",
        accent="#fbbf24",
        background="#f2f8ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#475569",
        glados_messages=[
            "Hard work deserves smart workflows. Let’s automate the pain away.",
            "Celebrate progress—ship smoother support.",
            "Labor less, document more intelligently.",
        ],
    ),
    "columbus_day": ThemePalette(
        key="columbus_day",
        name="Indigenous Peoples' Day",
        primary="#a855f7",
        accent="#fb923c",
        background="#f7f0ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#7c3aed",
        glados_messages=[
            "Respect every journey—map the customer path clearly.",
            "Discover better processes, honor every story.",
            "Chart success with empathy and precision.",
        ],
    ),
    "veterans_day": ThemePalette(
        key="veterans_day",
        name="Veterans Day",
        primary="#3b82f6",
        accent="#facc15",
        background="#eef5ff",
        surface="#ffffff",
        text="#111827",
        muted_text="#4b5563",
        glados_messages=[
            "Serve those who served with flawless follow-up.",
            "Precision, honor, gratitude—build them into every note.",
            "Support that stands at attention.",
        ],
    ),
    "thanksgiving": ThemePalette(
        key="thanksgiving",
        name="Thanksgiving",
        primary="#f59e0b",
        accent="#f97316",
        background="#fff7eb",
        surface="#ffffff",
        text="#111827",
        muted_text="#92400e",
        glados_messages=[
            "Grateful users, grateful agents—pass the uptime.",
            "Feast on solutions, serve seconds of documentation.",
            "Gobble up those recurring issues before they multiply.",
        ],
    ),
    "christmas": ThemePalette(
        key="christmas",
        name="Christmas",
        primary="#f87171",
        accent="#34d399",
        background="#fff9f7",
        surface="#ffffff",
        text="#111827",
        muted_text="#6b7280",
        glados_messages=[
            "Wrap each fix with cheer and clarity.",
            "All we want for Christmas is zero escalations.",
            "Jingle all the way to a resolved queue.",
        ],
    ),
    "halloween": ThemePalette(
        key="halloween",
        name="Halloween",
        primary="#c084fc",
        accent="#fb923c",
        background="#f5ecff",
        surface="#ffffff",
        text="#111827",
        muted_text="#8b5cf6",
        glados_messages=[
            "No tricks, just treats—squash those phantom bugs.",
            "Ghost the downtime, not the customers.",
            "Spellbinding support, zero jump scares.",
        ],
    ),
    "helldiver": HELLDIVER_THEME,
}

HOLIDAY_NAME_TO_KEY = {
    "New Year's Day": "new_year",
    "Day of Liberty": "day_of_liberty",
    "Martin Luther King Jr. Day": "mlk_day",
    "Presidents' Day": "presidents_day",
    "Memorial Day": "memorial_day",
    "Juneteenth National Independence Day": "juneteenth",
    "Independence Day": "independence_day",
    "Labor Day": "labor_day",
    "Columbus Day": "columbus_day",
    "Veterans Day": "veterans_day",
    "Thanksgiving Day": "thanksgiving",
    "Christmas Day": "christmas",
}

SPECIAL_THEME_PERIODS = [
    {"key": "halloween", "start": (10, 15), "end": (10, 31)},
    {"key": "christmas", "start": (12, 1), "end": (12, 25)},
]

MILESTONE_TICK_INTERVAL = timedelta(minutes=3)

MILESTONE_DEFINITIONS = [
    {
        "id": "case_id",
        "label": "Create case",
        "description": "Add the Case ID to mark the case as created.",
        "due": timedelta(minutes=3),
    },
    {
        "id": "document_case",
        "label": "Document case",
        "description": "Share the survey URL and CRM case link.",
        "due": timedelta(hours=2),
    },
    {
        "id": "resolution",
        "label": "Resolve",
        "description": "Close the case or log a replacement within four hours.",
        "due": timedelta(hours=4),
    },
]
MILESTONE_ID_ORDER = [entry["id"] for entry in MILESTONE_DEFINITIONS]

MILESTONE_DEFINITION_LOOKUP = {
    entry["id"]: entry for entry in MILESTONE_DEFINITIONS
}

DELL_ESCALATION_OVERVIEW_FIELDS = [
    ("dell_issue_start_date", "Issue start date"),
    ("service_tag", "PC service tag"),
    ("case_id", "Case ID"),
]

DELL_ESCALATION_PC_FIELDS = [
    ("pc_model", "Type of PC"),
    ("bios_version", "BIOS Version"),
    ("windows_version", "Windows Version"),
    ("graphics_card", "Graphics card"),
    ("processor", "Processor"),
    ("dell_command_updates_status", "Dell Command Updates"),
    ("dell_power_options_setup", "Power Options setup"),
    ("dell_optimizer_setup", "Dell Optimizer setup"),
    (
        "dell_intel_ppm_installed",
        "Intel Processor Power Management Utility installed?",
    ),
    ("dell_cpu_speed_or_throttling", "CPU Speed / Is CPU throttling?"),
    ("dell_gpu_usage_integrated", "GPU Usage % (Integrated)"),
    ("dell_gpu_usage_dedicated", "GPU Usage % (Dedicated)"),
    ("dell_cpu_utilization", "CPU Utilization %"),
    ("dell_benchmark_results", "Benchmark used and results"),
    (
        "dell_ultra_resolution_support",
        "Can it launch simulation on Ultra Resolution? (If needed)",
    ),
    ("dell_gpu_driver_versions", "Which GPU driver versions were tested?"),
    (
        "dell_reliability_monitor_results",
        "Reliability Monitor and Event Viewer results",
    ),
    ("dell_diagnostics_results", "Dell Diagnosis test results (ePSA tests included)"),
    ("dell_windows_reimaged", "Has Windows been reimaged?"),
]

DELL_ESCALATION_CONTACT_FIELDS = [
    ("clinic_name", "Clinic name"),
    (
        "clinic_contact_name",
        "Full name of person responsible for receiving the equipment",
    ),
    ("clinic_contact_phone", "Phone number"),
    ("clinic_contact_email", "Email address"),
    ("clinic_address_line_1", "Address 1"),
    ("clinic_address_line_2", "Address 2 (Suite, etc.)"),
    ("clinic_city", "City"),
    ("clinic_state", "State"),
    ("clinic_postal_code", "Zip Code"),
]

DELL_ESCALATION_FIELD_LABELS = (
    DELL_ESCALATION_OVERVIEW_FIELDS
    + DELL_ESCALATION_PC_FIELDS
    + DELL_ESCALATION_CONTACT_FIELDS
)

DELL_ESCALATION_FIELDS = [field for field, _ in DELL_ESCALATION_FIELD_LABELS]

BASE_CATEGORY_MAP = {
    "HEADER": [
        "company_name",
        "subscription_id",
        "brief_description",
        "case_id",
        "application_version",
    ],
    "DESCRIPTION": ["description"],
    "PHONECALL": [
        "caller_name",
        "phone_description",
        "email",
        "dongle_number",
        "phone_number",
        "teamviewer_id",
        "teamviewer_password",
    ],
    "INTERNAL NOTES": ["internal_helpjuice", "internal_logs"],
    "REMOTE SESSION": ["remote_steps", "repro_steps"],
    "CONCLUSION": ["root_cause", "solution"],
    "AX COORDINATORS": [
        "request_issue",
        "contact_name",
        "office_ph",
        "direct_ph",
        "best_time",
        "patterson",
        "straumann",
    ],
    "ESCALATION 2ND LINE": ["esc_name", "esc_ph", "esc_email"],
    "DELL ESCALATION": DELL_ESCALATION_FIELDS,
    "ADDITIONAL INFORMATION": ["additional_info"],
}

HW_CATEGORY_MAP = {
    "PC HARDWARE": [
        "service_tag",
        "pc_model",
        "windows_version",
        "bios_version",
        "graphics_card",
        "processor",
        "warranty",
    ],
    "SCANNER HARDWARE": [
        "scanner_sn",
        "base_sn",
        "trios_module_version",
        "dongle_deployment_date",
        "scanner_previous_replacements",
        "scanner_accidental_damage",
        "hardware_test",
    ],
}

OPTIONAL_PROGRESS_CATEGORIES = {"DELL ESCALATION"}

ESCALATION_TOGGLE_FIELDS = [
    "request_issue",
    "contact_name",
    "office_ph",
    "direct_ph",
    "best_time",
    "patterson",
    "straumann",
    "esc_name",
    "esc_ph",
    "esc_email",
] + DELL_ESCALATION_FIELDS

HARDWARE_TOGGLE_FIELDS = sorted(
    {field for fields in HW_CATEGORY_MAP.values() for field in fields}
    | {
        "hardware_dongle_replaced",
        "hardware_latest_deployment_date",
        "hardware_scanner_replaced",
        "hardware_scanner_sn_summary",
        "hardware_subscription_type",
    }
)

HOTKEY_TARGET_SESSION_KEY = "hotkey_target_idx"
AUTOSAVE_THROTTLE_SECONDS = 0.75

CASE_TAB_SLUGS = {
    "Case": "case",
    "Tracking": "tracking",
    "Escalations": "escalations",
    "Email": "email",
    "Hardware Issues": "hardware",
    "Remote Session": "remote",
    "Tables": "tables",
    "Corrected JSON": "corrected_json",
    "Save/Load": "save_load",
    "Kiroshi Chat": "kiroshi_chat",
    "I'm bored": "bored",
    "Debug": "debug",
}

_CAPTURE_FOOTER_REGISTRY_PREFIX = "capture_footer_tab_registry"
_CAPTURE_FOOTER_RENDERED_PREFIX = f"{_CAPTURE_FOOTER_REGISTRY_PREFIX}_rendered"

INSTALLER_FILENAME = "KiroshiInstaller_Release-1.8.0.bat"

STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "have", "into", "will", "when", "case",
    "customer", "issue", "steps", "they", "their", "been", "were", "after", "before", "about",
    "also", "while", "should", "could", "there", "where", "using", "used", "need", "your", "each",
    "them", "than", "then", "once", "only", "very", "make", "made", "through", "over", "more",
    "less", "much", "many", "take", "taken", "back", "most", "some", "such", "same", "per", "upon",
    "done", "time",
}

import re
WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")

DEFAULT_TAXONOMY_BLOCK = (
    "• 3Shape Unite / Login — issues with 3Shape Account, tokens, sign-in, credential errors. "
    "Positives: \"sign in\", \"3Shape Account\", \"token\". Negatives: hardware calibration.\n"
    "• 3Shape Unite / Case Submission / Timeout-Proxy — sending cases, timeouts, proxies, firewalls, TLS handshake. "
    "Positives: \"Send Case\", \"proxy\", \"firewall\", \"TLS\". Negatives: scanner tips.\n"
    "• TRIOS / Calibration — scanner calibration steps, tip issues, drift. Positives: \"calibrate\", \"tip\", \"firmware\". "
    "Negatives: account login.\n"
    "• TRIOS / Scan Quality — margins, occlusion, lack of detail, scanning workflow.\n"
    "• Dental System / Performance — slow UI, freezing, crash stacktraces."
)

DEFAULT_SIGNALS_CONFIG = json.dumps(
    {
        "unite": {
            "keywords": ["Unite", "App Store", "Send Case", "Lab Inbox", "Server"],
            "logs": ["ApplicationInitializer", "TLS", "service start failed"],
        },
        "trios": {
            "keywords": ["TRIOS", "calibrate", "scanner", "tip", "firmware", "dongle"],
            "logs": ["USB", "driver", "HW", "low detail"],
        },
    },
    indent=2,
)
