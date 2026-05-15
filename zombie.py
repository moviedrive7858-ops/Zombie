import telebot
import random
import time
import threading
import json
import os
from telebot import types
from flask import Flask

# --- Web Server for Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Setup ---
API_TOKEN = os.environ.get('BOT_TOKEN', '')
bot = telebot.TeleBot(API_TOKEN)
ADMIN_ID = 6895314939

DATA_FILE = 'win_counts.json'
GROUPS_FILE = 'active_groups.json'

# --- State Management ---
games = {}  # {chat_id: game_state}
games_lock = threading.Lock()
active_groups_db = {}

# --- Data Loading / Saving ---
def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

active_groups_db = load_json(GROUPS_FILE)

def update_player_stats(user_id, name, won=False, enemy_kills=0, zombie_kills=0):
    data = load_json(DATA_FILE)
    uid = str(user_id)
    if uid not in data:
        data[uid] = {'name': name, 'wins': 0, 'total_enemy_kills': 0, 'total_zombie_kills': 0, 'games_played': 0}
    data[uid]['name'] = name
    if won:
        data[uid]['wins'] += 1
    data[uid]['total_enemy_kills'] += enemy_kills
    data[uid]['total_zombie_kills'] += zombie_kills
    data[uid]['games_played'] = data[uid].get('games_played', 0) + 1
    save_json(DATA_FILE, data)

# --- Helper Functions ---
def get_game(chat_id):
    with games_lock:
        if chat_id not in games:
            games[chat_id] = {
                'waiting_room': [],
                'game_active': False,
                'round_num': 0,
                'current_players': [],
                'current_duels': {},  # {duel_id: duel_state}
                'previous_pairs': set(),
                'offender_count': {},  # {user_id: count} - unauthorized button press
                'eliminated': [],
                'join_timer': None,
                'used_locations': [],
            }
        return games[chat_id]

def reset_game(chat_id):
    with games_lock:
        if chat_id in games:
            if games[chat_id].get('join_timer'):
                games[chat_id]['join_timer'].cancel()
            del games[chat_id]

def check_bot_admin(chat_id):
    try:
        chat_member = bot.get_chat_member(chat_id, bot.get_me().id)
        return chat_member.status == 'administrator'
    except:
        return False

def get_mention(uid, name):
    clean_name = name.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
    return f"[{clean_name}](tg://user?id={uid})"

def update_group_info(chat):
    if chat.type in ['group', 'supergroup']:
        chat_id = str(chat.id)
        link = f"https://t.me/{chat.username}" if chat.username else "No Link"
        if link == "No Link":
            try:
                link = bot.export_chat_invite_link(chat.id)
            except:
                pass
        active_groups_db[chat_id] = {'id': chat.id, 'name': chat.title, 'link': link}
        save_json(GROUPS_FILE, active_groups_db)

# --- Locations (50 locations with story text) ---
LOCATIONS = [
    # Medical
    {"name": "💉 စွန့်ပစ်ဆေးရုံ", "story": "ဆေးနံ့တွေနဲ့ အလောင်းနံ့တွေ ရောနှောနေတဲ့ စင်္ကြံလမ်းမှာ\nခြေလှမ်းသံတွေ ပဲ့တင်ထပ်နေတယ်..."},
    {"name": "🧪 ဗိုင်းရပ်စ်သုတေသနခန်း", "story": "ဖန်ပြွန်ကွဲသံတွေကြားထဲမှာ\nအစိမ်းရောင် အရည်တွေ ကျနေတယ်..."},
    {"name": "🏥 ပြိုကျနေတဲ့ ဆေးရုံကြီး", "story": "အရေးပေါ်ခန်းထဲက မီးတွေ မှိတ်တုတ်မှိတ်တုတ်\nလူနာတင်ကုတင်တွေ မှောက်လဲနေတယ်..."},
    {"name": "💊 ဆေးဆိုင်ဟောင်း", "story": "ဆေးဗူးတွေ ကွဲပြားနေတဲ့ ကြမ်းပြင်ပေါ်မှာ\nသွေးခြေရာတွေ ဆွဲထားတယ်..."},
    {"name": "🧬 မြေအောက် ဓာတ်ခွဲခန်း", "story": "အေးစက်နေတဲ့ သံတံခါးနောက်ကွယ်မှာ\nတစ်ခုခု လှုပ်ရှားနေတယ်..."},
    {"name": "🩺 သွားဆေးခန်းဟောင်း", "story": "သွားဆေးခုံပေါ်မှာ သွေးခြောက်တွေ ကပ်နေပြီး\nဆေးကိရိယာတွေ ပြန့်ကျဲနေတယ်..."},
    {"name": "🔬 ရောဂါထိန်းချုပ်ရေးစင်တာ", "story": "သတိပေးမီးနီတွေ လက်နေပြီး\nအသံလွှင့်စက်ထဲက ဟစ်သံတွေ ကြားရတယ်..."},

    # Urban
    {"name": "🏚 အိမ်ယာဟောင်း", "story": "အိမ်ခေါင်မိုးပေါက်ကနေ လရောင်ကျနေပြီး\nအိပ်ခန်းထဲက ခြစ်သံတွေ ကြားရတယ်..."},
    {"name": "🏢 ရုံးတိုက်ပျက်", "story": "ဓာတ်လှေကားတံခါး ပွင့်လိုက်ပိတ်လိုက်\nအထဲက မှောင်မိုက်နေတယ်..."},
    {"name": "🏫 ကျောင်းဟောင်း", "story": "ကလေးတွေရဲ့ ပန်းချီကားတွေ နံရံမှာ ကပ်နေသေးပြီး\nစာသင်ခုံတွေကြားမှာ အရိပ်တွေ လှုပ်ရှားနေတယ်..."},
    {"name": "⛪ ဘုရားကျောင်းပျက်", "story": "ခေါင်းလောင်းသံ ရုတ်တရက် မြည်လာပြီး\nပြတင်းပေါက်ကနေ လက်တွေ ထိုးဝင်လာတယ်..."},
    {"name": "🏪 စူပါမားကက်ဟောင်း", "story": "စားသောက်ကုန်စင်တွေကြားမှာ\nတစ်ခုခု ကိုက်ဖြတ်နေတဲ့ အသံကြားရတယ်..."},
    {"name": "🏗 ဆောက်လက်စ အဆောက်အဦ", "story": "သံမဏိ ကြိုးတွေကြားမှာ ပိတ်မိနေပြီး\nအပေါ်ထပ်ကနေ ခုန်ချသံ ကြားရတယ်..."},
    {"name": "🎭 ရုပ်ရှင်ရုံဟောင်း", "story": "ဖန်သားပြင်ပေါ်မှာ static ပြနေပြီး\nထိုင်ခုံတန်းတွေကြားမှာ အရိပ်တွေ ထနေတယ်..."},
    {"name": "📻 ရေဒီယိုစခန်းဟောင်း", "story": "ရေဒီယိုထဲက ဆူညံသံကြားမှာ\nအကူအညီတောင်းသံ ဝိုးတဝါး ကြားရတယ်..."},
    {"name": "🏨 ဟိုတယ်ပျက်", "story": "လော်ဘီထဲက ဆွဲတံခါးတွေ ပွင့်နေပြီး\nအထပ်မြင့်ကနေ ပစ္စည်းတွေ ကျလာနေတယ်..."},
    {"name": "🎰 ကာစီနိုဟောင်း", "story": "စလော့မက်ရှင်တွေ ရုတ်တရက် လည်ပတ်လာပြီး\nအလင်းရောင်တွေကြားမှာ အရိပ်တွေ ကခုန်နေတယ်..."},
    {"name": "🚉 ဘတ်စ်ကားဂိတ်ဟောင်း", "story": "ဘတ်စ်ကားတွေ တန်းစီရပ်နေပြီး\nအတွင်းမှာ တစ်ခုခု လှုပ်ရှားနေတယ်..."},
    {"name": "📚 စာကြည့်တိုက်ဟောင်း", "story": "စာအုပ်တွေ ပြန့်ကျဲနေတဲ့ ကြမ်းပြင်ပေါ်မှာ\nခြေရာသစ်တွေ ထင်နေတယ်..."},
    {"name": "🏦 ဘဏ်ဟောင်း", "story": "သံမဏိ vault တံခါးနောက်ကနေ\nခေါက်သံတွေ ကြားရတယ်..."},

    # Nature
    {"name": "🌲 သစ်တောအနက်", "story": "သစ်ကိုင်းတွေကြားမှာ တစ်ခုခု ခုန်ပြေးသွားပြီး\nအရွက်တွေ ဖြတ်ကနဲ ကျတယ်..."},
    {"name": "🌊 မြစ်ကမ်းပါး", "story": "ညရဲ့ မြစ်ရေထဲကနေ လက်တွေ ထိုးထွက်လာပြီး\nကမ်းပါးဘက် တက်လာနေတယ်..."},
    {"name": "⛰ တောင်ကြားလမ်း", "story": "ကျဉ်းမြောင်းတဲ့ လမ်းကြောင်းမှာ\nနောက်ကနေ ခြေလှမ်းသံတွေ နီးလာနေတယ်..."},
    {"name": "🌾 စပါးခင်းဟောင်း", "story": "မြက်ပင်ရှည်တွေကြားမှာ တစ်ခုခု ရွေ့လျားနေပြီး\nအနံ့ဆိုးတွေ လွင့်လာတယ်..."},
    {"name": "🕳 ဂူအဝင်", "story": "မှောင်မဲနေတဲ့ ဂူထဲကနေ အသက်ရှူသံတွေ\nပဲ့တင်ထပ်ပြီး ထွက်လာနေတယ်..."},
    {"name": "🌿 ရေကန်ဟောင်း", "story": "ရေမြှုပ်နေတဲ့ ရုပ်အလောင်းတွေကြားမှာ\nတစ်ခုခု ရေပေါ် ပေါ်လာတယ်..."},
    {"name": "🏕 စခန်းချထားတဲ့ တောအုပ်", "story": "တဲတွေ ဆုတ်ပြဲနေပြီး မီးပုံထဲမှာ\nအရိုးတွေ ကျန်နေတယ်..."},

    # Underground
    {"name": "🚇 မြေအောက်ဘူတာ", "story": "ရထားသံလမ်းပေါ်မှာ ခြေလှမ်းသံတွေ ပဲ့တင်ထပ်နေပြီး\nဥမင်အဝင်ဝမှာ အရိပ်တွေ ထနေတယ်..."},
    {"name": "🚰 ရေပိုက်လိုဏ်ခေါင်း", "story": "ရေစီးသံကြားထဲမှာ ဟစ်သံတွေ ရောနေပြီး\nနံရံပေါ်မှာ ခြစ်ရာတွေ ထင်နေတယ်..."},
    {"name": "🔦 မြေအောက်ခိုလှုံခန်း", "story": "အရေးပေါ်မီးတွေ မှိတ်နေပြီး\nသံတံခါးနောက်ကနေ ထုသံတွေ ကြားရတယ်..."},
    {"name": "⛏ သတ္တုတွင်းဟောင်း", "story": "တွင်းတူးစက်တွေ သံချေးတက်နေပြီး\nအောက်ဆုံးထပ်ကနေ ညည်းသံတွေ ကြားရတယ်..."},
    {"name": "🕯 မြေအောက်ဘုရားကျောင်း", "story": "ဖယောင်းတိုင်တွေ မီးလောင်နေသေးပြီး\nရုပ်ထုတွေနောက်မှာ တစ်ခုခု ပုန်းနေတယ်..."},

    # Military
    {"name": "🎖 စစ်စခန်းဟောင်း", "story": "တံခါးတွေ ပွင့်ဟနေတဲ့ စစ်စခန်းထဲမှာ\nလက်နက်တွေ ပြန့်ကျဲနေပေမယ့် ကျည်ဆံတွေ ကုန်ခါနီးပြီ..."},
    {"name": "🔫 လက်နက်သိုလှောင်ရုံ", "story": "သံမဏိစင်တွေကြားမှာ ဗုံးကွဲသံ ဝေးဝေးကနေ ကြားရပြီး\nတံခါးကို တစ်ခုခု ခေါက်နေတယ်..."},
    {"name": "🚁 ရဟတ်ယာဉ်ကွင်း", "story": "ပျက်စီးနေတဲ့ ရဟတ်ယာဉ်တွေကြားမှာ\nအင်ဂျင်တစ်ခု ရုတ်တရက် စတက်လာတယ်..."},
    {"name": "📡 ဆက်သွယ်ရေးစခန်း", "story": "ဆက်သွယ်ရေးစက်တွေ ဆူညံနေပြီး\nမော်နီတာပေါ်မှာ SOS signal ပေါ်နေတယ်..."},
    {"name": "🛡 စစ်ဘက်ဆေးရုံ", "story": "လူနာတင်ကုတင်တွေ တန်းစီနေပြီး\nအဝတ်ဖြူတွေပေါ်မှာ သွေးစွန်းနေတယ်..."},
    {"name": "🚧 စစ်ဘက်ဂိတ်ဟောင်း", "story": "သံဆူးကြိုးတွေကြားမှာ ဖြတ်သန်းရပြီး\nကင်းစောင့်တာဝါပေါ်မှာ တစ်ခုခု ရပ်နေတယ်..."},

    # Industrial
    {"name": "🏭 စက်ရုံဟောင်း", "story": "စက်တွေ ရုတ်တရက် လည်ပတ်လာပြီး\nconveyor belt ပေါ်မှာ တစ်ခုခု ရွေ့လာနေတယ်..."},
    {"name": "⚡ ဓာတ်အားပေးစက်ရုံ", "story": "ဓာတ်အားလိုင်းတွေ မီးပွင့်လိုက်ပျက်လိုက်\nမှောင်ထဲမှာ မျက်လုံးတွေ တောက်နေတယ်..."},
    {"name": "🛢 ရေနံသိုလှောင်ကန်", "story": "ရေနံနံ့ပြင်းပြင်းကြားမှာ\nသံဗူးတွေ လိမ့်ကျသံ ကြားရတယ်..."},
    {"name": "🔧 ကားပြင်ဆိုင်ဟောင်း", "story": "ကားတွေအောက်မှာ တစ်ခုခု တွားနေပြီး\nကိရိယာတွေ ကျသံ ကြားရတယ်..."},
    {"name": "🧱 အုတ်ဖုတ်စက်ရုံ", "story": "မီးဖိုထဲက အပူဓာတ်တွေ ကျန်နေသေးပြီး\nအုတ်ပုံတွေနောက်မှာ ရှုပ်ရှက်သံ ကြားရတယ်..."},

    # Special
    {"name": "🚂 ရထားဟောင်း", "story": "သံချေးတက်နေတဲ့ ရထားတွဲတွေထဲမှာ\nခရီးသည်တွေရဲ့ ပစ္စည်းတွေ ကျန်နေသေးတယ်..."},
    {"name": "🎪 ဆာကပ်တဲဟောင်း", "story": "ရောင်စုံတဲတွေ စုတ်ပြဲနေပြီး\nရယ်မောသံတွေ ဝိုးတဝါး ကြားရတယ်..."},
    {"name": "🗼 ရေတာဝါဟောင်း", "story": "သံလှေကားတွေ တကျိတ်ကျိတ်မြည်နေပြီး\nအပေါ်ဆုံးမှာ တစ်ခုခု စောင့်နေတယ်..."},
    {"name": "🚢 ဆိပ်ကမ်းဟောင်း", "story": "သင်္ဘောပျက်တွေကြားမှာ ရေလှိုင်းသံနဲ့အတူ\nညည်းသံတွေ ရောနေတယ်..."},
    {"name": "🏟 အားကစားကွင်းဟောင်း", "story": "ပရိသတ်ထိုင်ခုံတွေပေါ်မှာ အရိုးတွေ ကျန်နေပြီး\nကွင်းလယ်မှာ တစ်ခုခု စုဝေးနေတယ်..."},
    {"name": "🌉 တံတားပျက်", "story": "တံတားကြိုးတွေ ယိမ်းနေပြီး\nအောက်က မြစ်ထဲမှာ တစ်ခုခု ကူးနေတယ်..."},
]

# Final round location
FINAL_LOCATION = {
    "name": "📦 နောက်ဆုံး ရိက္ခာသိုလှောင်ရုံ",
    "story": "ဒီနေရာကို ရောက်ဖို့ အရာအားလုံးကို စွန့်လွှတ်ခဲ့ကြပြီ...\nရိက္ခာက တစ်ယောက်စာပဲ ကျန်တယ်..."
}

GAME_INTRO = """
🌑 *နှစ်ပေါင်း ၅၀ ကြာပြီ...*

ကမ္ဘာကြီးက ပျက်စီးသွားပြီ။ ဗိုင်းရပ်စ် X\\-7 က လူသားတွေကို ဇွန်ဘီအဖြစ် ပြောင်းလဲပစ်ခဲ့တယ်။

ကျန်ရစ်သူ အနည်းငယ်က မြို့ပျက်ကြီးထဲမှာ အသက်ရှင်ရပ်တည်ဖို့ ရုန်းကန်နေကြတယ်...

⚠️ *ရိက္ခာက ကုန်ခါနီးပြီ။ နောက်ဆုံးကျန်တဲ့ သိုလှောင်ရုံကို ရောက်ဖို့ တစ်ယောက်ပဲ ရှင်နိုင်တယ်...*
"""

# --- Attack System ---
# Behind the scenes: attack_player, attack_zombie, run
# Results matrix:
# P1\P2         | attack_player | attack_zombie | run
# attack_player | REMATCH       | P1 kills P2   | P1 advances
# attack_zombie | P2 kills P1   | BOTH advance  | P1 dies (zombie gets him while running away)
# run           | P2 advances   | P2 dies*      | BOTH advance
#
# * run vs attack_zombie: runner ရှင်, zombie တိုက်သူ သေ
#   (zombie ကိုတိုက်နေတုန်း runner ထွက်ပြေးသွားလို့ zombie က တိုက်သူကို ပြန်ကိုက်)

ATTACK_PLAYER = "attack_player"
ATTACK_ZOMBIE = "attack_zombie"
RUN = "run"

def resolve_duel(p1_choice, p2_choice):
    """
    Returns: (p1_alive, p2_alive, result_type)
    result_type: 'rematch', 'p1_kills', 'p2_kills', 'both_advance', 'p1_advance', 'p2_advance', 'p1_dies', 'p2_dies'
    """
    if p1_choice == ATTACK_PLAYER and p2_choice == ATTACK_PLAYER:
        return True, True, 'rematch'
    elif p1_choice == ATTACK_PLAYER and p2_choice == ATTACK_ZOMBIE:
        return True, False, 'p1_kills'
    elif p1_choice == ATTACK_PLAYER and p2_choice == RUN:
        return True, False, 'p1_advance'
    elif p1_choice == ATTACK_ZOMBIE and p2_choice == ATTACK_PLAYER:
        return False, True, 'p2_kills'
    elif p1_choice == ATTACK_ZOMBIE and p2_choice == ATTACK_ZOMBIE:
        return True, True, 'both_advance'
    elif p1_choice == ATTACK_ZOMBIE and p2_choice == RUN:
        return False, True, 'p2_advance_zombie'
    elif p1_choice == RUN and p2_choice == ATTACK_PLAYER:
        return False, True, 'p2_advance'
    elif p1_choice == RUN and p2_choice == ATTACK_ZOMBIE:
        return True, False, 'p1_advance_zombie'
    elif p1_choice == RUN and p2_choice == RUN:
        return True, True, 'both_advance'
    return True, True, 'both_advance'

# Result messages (dramatic)
RESULT_MESSAGES = {
    'rematch': "⚔️ နှစ်ယောက်လုံး တစ်ယောက်ကိုတစ်ယောက် ချိန်ရွယ်တိုက်ခိုက်လိုက်ကြပေမယ့်\nတစ်ပြိုင်နက် ရှောင်လိုက်ကြတယ်\\! ပြန်တိုက်\\!",
    'p1_kills': "🎯 {p1} က {p2} ကို သတ်ပစ်လိုက်လို့\\!\n💀 {p2} ဇွန်ဘီတွေရဲ့ အစာဖြစ်သွားပြီ...",
    'p2_kills': "🎯 {p2} က {p1} ကို သတ်ပစ်လိုက်လို့\\!\n💀 {p1} ဇွန်ဘီတွေရဲ့ အစာဖြစ်သွားပြီ...",
    'p1_advance': "🏃 {p2} လွတ်မြောက်အောင် ထွက်ပြေးဖို့ ကြိုးစားပေမယ့်\n🎯 {p1} က အနောက်ကနေ ချောင်းမြောင်းသတ်လိုက်တယ်\\!",
    'p2_advance': "🏃 {p1} လွတ်မြောက်အောင် ထွက်ပြေးဖို့ ကြိုးစားပေမယ့်\n🎯 {p2} က အနောက်ကနေ ချောင်းမြောင်းသတ်လိုက်တယ်\\!",
    'both_advance': "🤝 နှစ်ယောက်လုံး ဇွန်ဘီတွေကို အောင်မြင်စွာ တိုက်ထုတ်ပြီး\n✅ နောက်တစ်ဆင့် အတူတက်လိုက်ကြတယ်\\!",
    'p1_advance_zombie': "🏃 {p1} ကထွက်ပြေးသွားပြီး\n🧟 {p2} ကဇွန်ဘီကို တိုက်နေရင်း ဇွန်ဘီရဲ့သတ်ဖြတ်ခြင်းခံလိုက်ရတယ်\\!",
    'p2_advance_zombie': "🏃 {p2} ကထွက်ပြေးသွားပြီး\n🧟 {p1} ကဇွန်ဘီကို တိုက်နေရင်း ဇွန်ဘီရဲ့သတ်ဖြတ်ခြင်းခံလိုက်ရတယ်\\!",
}

# --- Bot vs Player (50/50) ---
def resolve_bot_duel():
    """Returns True if player survives, False if dies"""
    return random.choice([True, False])

BOT_SURVIVE_MESSAGES = [
    "🔫 ဇွန်ဘီရဲ့ ခေါင်းကို သေနတ်နဲ့ တည့်တည့်ပစ်မိပြီး လွတ်မြောက်ခဲ့တယ်\\!",
    "🗡 နောက်ဆုံးအချိန်မှာ ဇွန်ဘီရဲ့လည်ပင်းကို ဓားနဲ့ ခုတ်ချလိုက်ပြီး ရှင်သန်ခဲ့တယ်\\!",
    "🏃 ဇွန်ဘီအုပ်စုကြားက အသက်လုပြီး ပြေးထွက်လာခဲ့တယ်\\!",
]

BOT_DIE_MESSAGES = [
    "🧟 ဇွန်ဘီက လည်ပင်းကို ကိုက်ဖြတ်လိုက်တယ်...",
    "💀 မြေပေါ်လဲကျပြီး ဇွန်ဘီအုပ်ကြီးက ဝိုင်းစားလိုက်ကြတယ်...",
    "☠️ ဇွန်ဘီရဲ့ လက်သည်းတွေ ရင်ဘတ်ကို ဆွဲဖြတ်လိုက်တယ်...",
]

# --- Commands ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    if message.chat.type == 'private':
        markup = None
        if message.from_user.id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        bot.send_message(message.chat.id,
            "🧟 *Zombie Survival Game*\n\n"
            "Group ထဲမှာ /join နှိပ်ပြီး ပါဝင်နိုင်ပါတယ်\\!",
            reply_markup=markup, parse_mode="MarkdownV2")
    else:
        update_group_info(message.chat)
        bot.send_message(message.chat.id, "🎮 ဂိမ်းစတင်ရန် /join ကို နှိပ်ပါ\\!", parse_mode="MarkdownV2")


@bot.message_handler(commands=['join'])
def join_handler(message):
    if message.chat.type == 'private':
        return
    update_group_info(message.chat)
    if not check_bot_admin(message.chat.id):
        bot.reply_to(message, "⚠️ Bot ကို Admin ပေးမှ ဂိမ်းစနစ် အလုပ်လုပ်ပါမည်။")
        return

    chat_id = message.chat.id
    game = get_game(chat_id)
    if game['game_active']:
        bot.reply_to(message, "⚠️ ပြိုင်ပွဲ စနေပါပြီ။ ပြီးအောင်စောင့်ပါ။")
        return

    uid = message.from_user.id
    name = message.from_user.first_name

    if not any(p['id'] == uid for p in game['waiting_room']):
        if not game['waiting_room']:
            game['join_timer'] = threading.Timer(300.0, auto_cancel_join, [chat_id])
            game['join_timer'].start()
        game['waiting_room'].append({'id': uid, 'name': name})
        count = len(game['waiting_room'])
        bot.reply_to(message,
            f"✅ {get_mention(uid, name)} ပါဝင်လာပြီ\\! \\(စုစုပေါင်း: {count} ယောက်\\)",
            parse_mode="MarkdownV2")
    else:
        bot.reply_to(message, "⚠️ သင် Join ပြီးသားပါ။")


@bot.message_handler(commands=['start_game'])
def start_game_handler(message):
    if message.chat.type == 'private':
        return
    chat_id = message.chat.id
    game = get_game(chat_id)

    if game['game_active']:
        bot.reply_to(message, "⚠️ ပြိုင်ပွဲ စနေပါပြီ။")
        return
    if len(game['waiting_room']) < 2:
        bot.reply_to(message, "❌ အနည်းဆုံး ၂ ယောက် ရှိမှ ရပါမယ်။")
        return

    game['game_active'] = True
    if game['join_timer']:
        game['join_timer'].cancel()
        game['join_timer'] = None

    # Send intro
    player_names = ", ".join([p['name'] for p in game['waiting_room']])
    intro_text = GAME_INTRO + f"\n👥 *ပါဝင်သူများ \\({len(game['waiting_room'])} ယောက်\\):*\n{escape_md(player_names)}"
    bot.send_message(chat_id, intro_text, parse_mode="MarkdownV2")
    time.sleep(3)

    threading.Thread(target=run_tournament, args=(chat_id,), daemon=True).start()


@bot.message_handler(commands=['cancel_game'])
def cancel_game_handler(message):
    chat_id = message.chat.id
    game = get_game(chat_id)
    uid = message.from_user.id

    # Only admin or game starter can cancel
    if uid == ADMIN_ID or (game['waiting_room'] and game['waiting_room'][0]['id'] == uid):
        bot.send_message(chat_id, "🚫 ပြိုင်ပွဲ ဖျက်သိမ်းလိုက်ပါပြီ။")
        reset_game(chat_id)
    else:
        bot.reply_to(message, "⚠️ ပြိုင်ပွဲဖျက်ခွင့် မရှိပါ။")


@bot.message_handler(commands=['rank'])
def rank_handler(message):
    data = load_json(DATA_FILE)
    if not data:
        bot.reply_to(message, "📊 မှတ်တမ်း မရှိသေးပါ။")
        return

    sorted_players = sorted(data.items(), key=lambda x: (x[1].get('wins', 0), x[1].get('total_enemy_kills', 0)), reverse=True)
    text = "🏆 *Top Players*\n━━━━━━━━━━━━━━━━\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, info) in enumerate(sorted_players[:10]):
        medal = medals[i] if i < 3 else f"{i+1}\\."
        name = escape_md(info.get('name', 'Unknown'))
        wins = info.get('wins', 0)
        kills = info.get('total_enemy_kills', 0)
        text += f"{medal} {name} \\- 🏅{wins} wins \\| ⚔️{kills} kills\n"

    bot.send_message(message.chat.id, text, parse_mode="MarkdownV2")


# --- Escape MarkdownV2 ---
def escape_md(text):
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


# --- Tournament Logic ---
def auto_cancel_join(chat_id):
    game = get_game(chat_id)
    if not game['game_active'] and len(game['waiting_room']) > 0:
        bot.send_message(chat_id, "⏰ စောင့်ဆိုင်းချိန် ၅ မိနစ်ကြာပြီးမို့လို့ ပြိုင်ပွဲ ဖျက်သိမ်းလိုက်ပါပြီ။")
        reset_game(chat_id)


def get_random_location(game):
    """Get a random location that hasn't been used yet"""
    available = [loc for loc in LOCATIONS if loc['name'] not in game['used_locations']]
    if not available:
        game['used_locations'] = []
        available = LOCATIONS[:]
    loc = random.choice(available)
    game['used_locations'].append(loc['name'])
    return loc


def make_pairs(players, previous_pairs):
    """
    Pair players avoiding previous pairs.
    Returns: list of (p1, p2) tuples, and optionally one solo player for zombie duel.
    """
    random.shuffle(players)
    pairs = []
    solo = None

    if len(players) % 2 == 1:
        # Odd number: last one goes to zombie duel
        solo = players[-1]
        players = players[:-1]

    # Try to avoid previous pairs (max 10 attempts)
    for attempt in range(10):
        random.shuffle(players)
        temp_pairs = []
        valid = True
        for i in range(0, len(players), 2):
            p1, p2 = players[i], players[i+1]
            pair_key = frozenset([p1['id'], p2['id']])
            if pair_key in previous_pairs and attempt < 9:
                valid = False
                break
            temp_pairs.append((p1, p2))
        if valid:
            pairs = temp_pairs
            break
    else:
        # Fallback: just pair them
        pairs = [(players[i], players[i+1]) for i in range(0, len(players), 2)]

    return pairs, solo


def run_tournament(chat_id):
    game = get_game(chat_id)
    current_players = list(game['waiting_room'])
    game['current_players'] = current_players
    total_players = len(current_players)
    last_bot_duel_player = None  # Track who had bot duel last

    round_num = 0
    while len(current_players) > 1 and game['game_active']:
        round_num += 1
        game['round_num'] = round_num

        # Check if final (2 players left)
        if len(current_players) == 2:
            run_final(chat_id, current_players[0], current_players[1], round_num, total_players)
            return

        # Get location
        location = get_random_location(game)

        # Round header
        alive_count = len(current_players)
        header = (
            f"━━━━━━━━━━━━━━━━\n"
            f"⚔️ *Round {round_num}* \\| ကျန်သူ: {alive_count}/{total_players} ယောက်\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📍 *{escape_md(location['name'])}*\n\n"
            f"_{escape_md(location['story'])}_"
        )
        bot.send_message(chat_id, header, parse_mode="MarkdownV2")
        time.sleep(2)

        # Make pairs (avoid previous + avoid giving same person bot duel twice in a row)
        pairs, solo = make_pairs(current_players, game['previous_pairs'])

        # If solo player is same as last bot duel player, try to swap
        if solo and last_bot_duel_player and solo['id'] == last_bot_duel_player['id'] and pairs:
            # Swap solo with someone from a pair
            swap_pair = random.choice(pairs)
            swap_player = random.choice(swap_pair)
            pairs.remove(swap_pair)
            other = swap_pair[0] if swap_pair[1] == swap_player else swap_pair[1]
            pairs.append((solo, other))
            solo = swap_player

        # Update previous pairs
        game['previous_pairs'] = set()
        for p1, p2 in pairs:
            game['previous_pairs'].add(frozenset([p1['id'], p2['id']]))

        # Execute duels
        round_survivors = []
        round_eliminated = []

        for p1, p2 in pairs:
            survivors, eliminated = execute_pvp_duel(chat_id, p1, p2, game)
            round_survivors.extend(survivors)
            round_eliminated.extend(eliminated)
            time.sleep(1.5)

        # Bot duel for solo player (if any)
        if solo:
            last_bot_duel_player = solo
            survived = execute_zombie_duel(chat_id, solo, game)
            if survived:
                round_survivors.append(solo)
            else:
                round_eliminated.append(solo)
            time.sleep(1.5)
        else:
            last_bot_duel_player = None

        # Round summary
        send_round_summary(chat_id, round_num, round_survivors, round_eliminated)
        current_players = round_survivors
        game['current_players'] = current_players
        time.sleep(3)

    # If only 1 player left (shouldn't happen normally, but just in case)
    if len(current_players) == 1 and game['game_active']:
        declare_winner(chat_id, current_players[0], round_num, total_players, game)

    if not current_players and game['game_active']:
        bot.send_message(chat_id, "💀 အားလုံး ကျဆုံးသွားပါပြီ\\.\\.\\. အသက်ရှင်ကျန်သူမရှိခဲ့ပါ\\!", parse_mode="MarkdownV2")
        reset_game(chat_id)


def execute_pvp_duel(chat_id, p1, p2, game):
    """Execute a PvP duel with the 3-button system. Returns (survivors, eliminated)"""
    max_rematches = 3
    rematch_count = 0

    while rematch_count < max_rematches:
        # Create buttons with shuffled hidden actions
        actions = [ATTACK_PLAYER, ATTACK_ZOMBIE, RUN]
        random.shuffle(actions)

        duel_id = f"{chat_id}_{p1['id']}_{p2['id']}_{time.time()}"
        game['current_duels'][duel_id] = {
            'p1': p1,
            'p2': p2,
            'actions_map': {0: actions[0], 1: actions[1], 2: actions[2]},
            'responses': {},
            'active': True,
            'event': threading.Event(),
            'allowed_players': {p1['id'], p2['id']},
        }

        # Button labels (all look the same - player doesn't know what's behind)
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("🔫", callback_data=f"duel_{duel_id}_0"),
            types.InlineKeyboardButton("🗡", callback_data=f"duel_{duel_id}_1"),
            types.InlineKeyboardButton("💣", callback_data=f"duel_{duel_id}_2"),
        )

        duel_text = f"⚔️ {escape_md(p1['name'])} VS {escape_md(p2['name'])}\n\n🎯 လက်နက်ရွေးချယ်ပါ\\!"
        sent = bot.send_message(chat_id, duel_text, reply_markup=markup, parse_mode="MarkdownV2")

        # Wait for both responses (15 seconds timeout)
        game['current_duels'][duel_id]['event'].wait(timeout=15.0)
        game['current_duels'][duel_id]['active'] = False

        try:
            bot.delete_message(chat_id, sent.message_id)
        except:
            pass

        # Get choices
        responses = game['current_duels'][duel_id]['responses']
        actions_map = game['current_duels'][duel_id]['actions_map']

        p1_choice = actions_map.get(responses.get(p1['id'])) if p1['id'] in responses else None
        p2_choice = actions_map.get(responses.get(p2['id'])) if p2['id'] in responses else None

        # Handle timeouts - player who didn't respond loses
        if p1_choice is None and p2_choice is None:
            bot.send_message(chat_id,
                f"⏰ {escape_md(p1['name'])} နဲ့ {escape_md(p2['name'])} နှစ်ယောက်လုံး ဘာလုပ်ရမှန်းမသိပဲ ကြောက်လန့်တုန်လှုပ်နေကြလို့ \\!\n💀 ဇွန်ဘီအုပ်စုကြီးက နှစ်ယောက်လုံးကို သတ်ဖြတ်ပြီးစားသောက်လိုက်ကြတယ်\\!",
                parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            return [], [p1, p2]
        elif p1_choice is None:
            bot.send_message(chat_id,
                f"⏰ {escape_md(p1['name'])} သင်ကြောက်လန့်ပြီးငေးကြောင်နေလို့\\!\n🧟 ဇွန်ဘီတွေ ရဲ့ ဝိုင်းဝန်းသတ်ဖြတ်စားသောက်ခြင်းကိုခံလိုက်ရပါပြီ\\!",
                parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            update_player_stats(p2['id'], p2['name'], enemy_kills=1)
            return [p2], [p1]
        elif p2_choice is None:
            bot.send_message(chat_id,
                f"⏰ {escape_md(p2['name'])} သင်ကြောက်လန့်ပြီးငေးကြောင်နေလို့\\!\n🧟 ဇွန်ဘီတွေ ရဲ့ ဝိုင်းဝန်းသတ်ဖြတ်စားသောက်ခြင်းကိုခံလိုက်ရပါပြီ\\!",
                parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            update_player_stats(p1['id'], p1['name'], enemy_kills=1)
            return [p1], [p2]

        # Resolve
        p1_alive, p2_alive, result_type = resolve_duel(p1_choice, p2_choice)

        if result_type == 'rematch':
            rematch_count += 1
            msg = RESULT_MESSAGES['rematch']
            if rematch_count < max_rematches:
                msg += f"\n\n🔄 *ပြန်တိုက်\\! \\({rematch_count}/{max_rematches}\\)*"
            bot.send_message(chat_id, msg, parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            time.sleep(2)
            continue
        else:
            # Send result message
            msg_template = RESULT_MESSAGES.get(result_type, "")
            msg = msg_template.format(p1=escape_md(p1['name']), p2=escape_md(p2['name']))
            bot.send_message(chat_id, msg, parse_mode="MarkdownV2")

            # Update stats
            if not p2_alive:
                update_player_stats(p1['id'], p1['name'], enemy_kills=1)
            if not p1_alive:
                update_player_stats(p2['id'], p2['name'], enemy_kills=1)

            del game['current_duels'][duel_id]

            survivors = []
            eliminated = []
            if p1_alive:
                survivors.append(p1)
            else:
                eliminated.append(p1)
            if p2_alive:
                survivors.append(p2)
            else:
                eliminated.append(p2)
            return survivors, eliminated

    # Max rematches reached - both advance
    bot.send_message(chat_id,
        f"🤝 {escape_md(p1['name'])} နဲ့ {escape_md(p2['name'])} တော်ကြပါတယ်\nနှစ်ယောက်လုံး ဒီအဆင့်မှာရှင်သန်ပြီးလွတ်မြောက်သွားကြပါတယ်\\!",
        parse_mode="MarkdownV2")
    if duel_id in game['current_duels']:
        del game['current_duels'][duel_id]
    return [p1, p2], []


def execute_zombie_duel(chat_id, player, game):
    """Execute a zombie duel (50/50). Returns True if survived."""
    bot.send_message(chat_id,
        f"🧟 *Zombie Attack\\!*\n\n"
        f"💀 {escape_md(player['name'])} တစ်ယောက်တည်း ဇွန်ဘီအုပ်စုနဲ့ဆုံတွေ့ပြီ\\!",
        parse_mode="MarkdownV2")
    time.sleep(2)

    survived = resolve_bot_duel()

    if survived:
        msg = random.choice(BOT_SURVIVE_MESSAGES)
        bot.send_message(chat_id, f"✅ {escape_md(player['name'])} {msg}", parse_mode="MarkdownV2")
        update_player_stats(player['id'], player['name'], zombie_kills=1)
    else:
        msg = random.choice(BOT_DIE_MESSAGES)
        bot.send_message(chat_id, f"💀 {escape_md(player['name'])} {msg}", parse_mode="MarkdownV2")

    return survived


def send_round_summary(chat_id, round_num, survivors, eliminated):
    """Send round summary"""
    text = f"\n━━━ *Round {round_num} ပြီးဆုံးခြင်း* ━━━\n"
    if survivors:
        names = ", ".join([escape_md(p['name']) for p in survivors])
        text += f"✅ ရှင်သန်သူ: {names}\n"
    if eliminated:
        names = ", ".join([escape_md(p['name']) for p in eliminated])
        text += f"💀 ကျဆုံးသူ: {names}\n"
    text += f"\n👥 ကျန်သူ: {len(survivors)} ယောက်"
    bot.send_message(chat_id, text, parse_mode="MarkdownV2")


def run_final(chat_id, p1, p2, round_num, total_players):
    """Run the final showdown - Best of 3"""
    game = get_game(chat_id)

    final_text = (
        f"━━━━━━━━━━━━━━━━\n"
        f"🏆 *FINAL SHOWDOWN* 🏆\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📍 *{escape_md(FINAL_LOCATION['name'])}*\n\n"
        f"_{escape_md(FINAL_LOCATION['story'])}_\n\n"
        f"⚔️ {escape_md(p1['name'])} VS {escape_md(p2['name'])}\n"
        f"🎯 *Best of 3 \\- ၂ ခါနိုင်ရမယ်\\!*"
    )
    bot.send_message(chat_id, final_text, parse_mode="MarkdownV2")
    time.sleep(3)

    p1_wins = 0
    p2_wins = 0
    match_num = 0

    while p1_wins < 2 and p2_wins < 2 and game['game_active']:
        match_num += 1
        bot.send_message(chat_id, f"🔥 *Final Match {match_num}/3*", parse_mode="MarkdownV2")
        time.sleep(1)

        # Execute single duel (no rematch limit in final - keep going until someone wins)
        actions = [ATTACK_PLAYER, ATTACK_ZOMBIE, RUN]
        random.shuffle(actions)

        duel_id = f"final_{chat_id}_{match_num}_{time.time()}"
        game['current_duels'][duel_id] = {
            'p1': p1,
            'p2': p2,
            'actions_map': {0: actions[0], 1: actions[1], 2: actions[2]},
            'responses': {},
            'active': True,
            'event': threading.Event(),
            'allowed_players': {p1['id'], p2['id']},
        }

        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("🔫", callback_data=f"duel_{duel_id}_0"),
            types.InlineKeyboardButton("🗡", callback_data=f"duel_{duel_id}_1"),
            types.InlineKeyboardButton("💣", callback_data=f"duel_{duel_id}_2"),
        )

        duel_text = f"⚔️ {escape_md(p1['name'])} \\[{p1_wins}\\] VS {escape_md(p2['name'])} \\[{p2_wins}\\]\n\n🎯 လက်နက်ရွေးချယ်ပါ\\!"
        sent = bot.send_message(chat_id, duel_text, reply_markup=markup, parse_mode="MarkdownV2")

        game['current_duels'][duel_id]['event'].wait(timeout=15.0)
        game['current_duels'][duel_id]['active'] = False

        try:
            bot.delete_message(chat_id, sent.message_id)
        except:
            pass

        responses = game['current_duels'][duel_id]['responses']
        actions_map = game['current_duels'][duel_id]['actions_map']

        p1_choice = actions_map.get(responses.get(p1['id'])) if p1['id'] in responses else None
        p2_choice = actions_map.get(responses.get(p2['id'])) if p2['id'] in responses else None

        # Handle timeouts
        if p1_choice is None and p2_choice is None:
            bot.send_message(chat_id, "⏰ ကြောက်ရွံ့တုန်လှုပ်မနေနဲ့\\! ရှင်သန်ဖို့အတွက် ပြန်တိုက်ခိုက်ပါ\\!", parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            time.sleep(1)
            continue
        elif p1_choice is None:
            p2_wins += 1
            bot.send_message(chat_id, f"⏰ {escape_md(p1['name'])} အချိန်ကုန်\\! {escape_md(p2['name'])} အမှတ်ရ\\!", parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            time.sleep(2)
            continue
        elif p2_choice is None:
            p1_wins += 1
            bot.send_message(chat_id, f"⏰ {escape_md(p2['name'])} အချိန်ကုန်\\! {escape_md(p1['name'])} အမှတ်ရ\\!", parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            time.sleep(2)
            continue

        p1_alive, p2_alive, result_type = resolve_duel(p1_choice, p2_choice)

        if result_type == 'rematch':
            msg = RESULT_MESSAGES['rematch'] + "\n\n🔄 *မြို့ပျက်ကြီးထဲ အသက်ရှင်ကျန်ဖို့အတွက် ထပ်မံတိုက်ခိုက်ပါ\\!*"
            bot.send_message(chat_id, msg, parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            time.sleep(2)
            continue

        msg_template = RESULT_MESSAGES.get(result_type, "")
        msg = msg_template.format(p1=escape_md(p1['name']), p2=escape_md(p2['name']))

        if not p2_alive or (p1_alive and not p2_alive):
            p1_wins += 1
            msg += f"\n\n📊 Score: {escape_md(p1['name'])} \\[{p1_wins}\\] \\- \\[{p2_wins}\\] {escape_md(p2['name'])}"
        elif not p1_alive or (p2_alive and not p1_alive):
            p2_wins += 1
            msg += f"\n\n📊 Score: {escape_md(p1['name'])} \\[{p1_wins}\\] \\- \\[{p2_wins}\\] {escape_md(p2['name'])}"
        else:
            # Both alive in final = no point scored, redo
            msg += "\n\n🔄 *တိုက်ပွဲကပိုမိုပြင်းထင်လာပြီ \\! ထပ်ပြီးတိုက်ခိုက်ကြမယ်\\!*"
            bot.send_message(chat_id, msg, parse_mode="MarkdownV2")
            del game['current_duels'][duel_id]
            time.sleep(2)
            continue

        bot.send_message(chat_id, msg, parse_mode="MarkdownV2")
        del game['current_duels'][duel_id]
        time.sleep(2)

    # Determine winner
    if p1_wins >= 2:
        declare_winner(chat_id, p1, round_num, total_players, game)
        update_player_stats(p2['id'], p2['name'], games_played=0)
    elif p2_wins >= 2:
        declare_winner(chat_id, p2, round_num, total_players, game)
        update_player_stats(p1['id'], p1['name'], games_played=0)


def declare_winner(chat_id, winner, round_num, total_players, game):
    """Declare the winner with stats"""
    data = load_json(DATA_FILE)
    uid = str(winner['id'])
    total_wins = data.get(uid, {}).get('wins', 0) + 1
    total_kills = data.get(uid, {}).get('total_enemy_kills', 0)

    winner_text = (
        f"🏆🏆🏆 *CHAMPION* 🏆🏆🏆\n\n"
        f"🎖 *{escape_md(winner['name'])}* သည် မြို့ပျက်ကြီးထဲမှ\n"
        f"အသက်ရှင် လွတ်မြောက်ခဲ့ပါပြီ\\!\n\n"
        f"📊 *ပွဲစဉ်မှတ်တမ်း:*\n"
        f"👥 ပါဝင်သူ: {total_players} ယောက်\n"
        f"⏱ ပွဲကြာချိန်: {round_num} round\n"
        f"🏅 စုစုပေါင်း အနိုင်: {total_wins} ကြိမ်"
    )
    bot.send_message(chat_id, winner_text, parse_mode="MarkdownV2")
    update_player_stats(winner['id'], winner['name'], won=True)
    reset_game(chat_id)


# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    chat_id = call.message.chat.id
    uid = call.from_user.id

    # Duel buttons
    if call.data.startswith('duel_'):
        parts = call.data.split('_')
        # Format: duel_{duel_id}_0/1/2
        # duel_id contains underscores, so we need to reconstruct it
        button_idx = int(parts[-1])
        duel_id = '_'.join(parts[1:-1])

        game = get_game(chat_id)
        duel = game['current_duels'].get(duel_id)

        if not duel or not duel['active']:
            bot.answer_callback_query(call.id, "⏰ ယခုပြိုင်ပွဲ ပြီးသွားပါပြီ။", show_alert=False)
            return

        allowed = duel['allowed_players']

        # Check if player is in the game at all
        all_player_ids = {p['id'] for p in game.get('current_players', [])}

        if uid not in allowed:
            if uid in all_player_ids:
                # Player is in the game but not in this duel
                offender_count = game.get('offender_count', {})
                count = offender_count.get(uid, 0) + 1
                offender_count[uid] = count
                game['offender_count'] = offender_count

                if count == 1:
                    bot.answer_callback_query(call.id,
                        "⚠️ သတိပေးချက်! ယခုတိုက်ပွဲမှာ သင်မပါဝင်ပါ။ ထပ်နှိပ်ရင် ပြိုင်ပွဲက ထုတ်ပစ်ပါမယ်!",
                        show_alert=True)
                else:
                    # Second offense - eliminate
                    bot.answer_callback_query(call.id,
                        "🚫 ပြိုင်ပွဲစည်းကမ်းဖောက်ဖျက်မှုကြောင့် ထုတ်ပစ်လိုက်ပါပြီ!",
                        show_alert=True)
                    # Remove from current_players
                    game['current_players'] = [p for p in game['current_players'] if p['id'] != uid]
                    player_name = call.from_user.first_name
                    bot.send_message(chat_id,
                        f"🚫 {escape_md(player_name)} ပြိုင်ပွဲစည်းကမ်းဖောက်လို့ ဇွန်ဘီရဲ့ သတ်ဖြတ်ခြင်းခံလိုက်ရပြီ\\! 🧟",
                        parse_mode="MarkdownV2")
            else:
                # Not in game at all - just ignore
                bot.answer_callback_query(call.id, "❌ သင် ဒီပြိုင်ပွဲမှာ မပါဝင်ပါ။", show_alert=False)
            return

        # Valid player in this duel
        if uid in duel['responses']:
            bot.answer_callback_query(call.id, "✅ ရွေးချယ်ပြီးပါပြီ။ စောင့်ပါ...", show_alert=False)
            return

        duel['responses'][uid] = button_idx
        bot.answer_callback_query(call.id, "✅ ရွေးချယ်ပြီး!", show_alert=False)

        # Check if both responded
        if len(duel['responses']) >= 2:
            duel['event'].set()

    # Admin panel
    elif call.data == "admin_panel":
        if uid != ADMIN_ID:
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_bc_menu"),
            types.InlineKeyboardButton("👥 Groups", callback_data="adm_grp_menu")
        )
        bot.edit_message_text("⚙️ *Admin Control Panel*", call.message.chat.id,
            call.message.message_id, reply_markup=markup, parse_mode="MarkdownV2")

    elif call.data == "adm_bc_menu":
        if uid != ADMIN_ID:
            return
        bot.edit_message_text("📢 Broadcast message ပို့ရန် reply ဖြင့် စာရေးပါ။\n/broadcast <message>",
            call.message.chat.id, call.message.message_id)

    elif call.data == "adm_grp_menu":
        if uid != ADMIN_ID:
            return
        groups = load_json(GROUPS_FILE)
        text = "👥 *Active Groups:*\n\n"
        for gid, info in groups.items():
            text += f"• {escape_md(info.get('name', 'Unknown'))}\n"
        if not groups:
            text += "No groups yet\\."
        bot.edit_message_text(text, call.message.chat.id,
            call.message.message_id, parse_mode="MarkdownV2")


# --- Broadcast Command ---
@bot.message_handler(commands=['broadcast'])
def broadcast_handler(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace('/broadcast', '').strip()
    if not text:
        bot.reply_to(message, "Usage: /broadcast <message>")
        return

    groups = load_json(GROUPS_FILE)
    sent_count = 0
    for gid, info in groups.items():
        try:
            bot.send_message(int(gid), text)
            sent_count += 1
        except:
            pass
    bot.reply_to(message, f"✅ {sent_count} group(s) သို့ ပို့ပြီးပါပြီ။")


# --- Main ---
if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🧟 Zombie Survival Bot is starting...")
    bot.infinity_polling()
