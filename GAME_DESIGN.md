# 🧟 Zombie Survival Bot - Game Design

## Attack System (နောက်ကွယ်မှာ ဘာရှိလဲ)

ခလုတ် ၃ ခု ပြမယ်: 🔫 🗡 💣
ဒါပေမယ့် round တိုင်းမှာ ခလုတ်တွေရဲ့ နောက်ကွယ်က action တွေ ကျပန်း ပြောင်းနေတယ်။

**နောက်ကွယ်မှာ ၃ မျိုး ရှိတယ်:**
- `attack_player` - ရန်သူကို တိုက်
- `attack_zombie` - ဇွန်ဘီကို တိုက်
- `run` - ထွက်ပြေး

## ရလဒ် Matrix

| Player 1 ⬇ \ Player 2 ➡ | attack_player | attack_zombie | run |
|---------------------------|---------------|---------------|-----|
| **attack_player** | ⚔️ ပြန်တိုက် (Rematch) | P1 အနိုင် (P2 သေ) | P1 အနိုင် (P2 သေ) |
| **attack_zombie** | P2 အနိုင် (P1 သေ) | ✅ ၂ ယောက်လုံး ရှင် | P1 သေ (P2 ရှင်) |
| **run** | P2 အနိုင် (P1 သေ) | P2 သေ (P1 ရှင်) | ✅ ၂ ယောက်လုံး ရှင် |

### ရှင်းလင်းချက်:
- **attack_player vs attack_player** → နှစ်ယောက်လုံး ချိန်ရွယ်ကြလို့ ပြန်တိုက်ရ (max 3 ကြိမ်)
- **attack_player vs attack_zombie** → zombie တိုက်နေသူကို player တိုက်သူက သတ်လိုက်
- **attack_player vs run** → ပြေးသူကို နောက်ကနေ ပစ်ချ
- **attack_zombie vs attack_zombie** → ၂ ယောက်လုံး zombie တိုက်ပြီး ရှင်သန်
- **attack_zombie vs run** → zombie တိုက်နေတုန်း ပြေးသူ ထွက်သွား → zombie က တိုက်သူကို ပြန်ကိုက်
- **run vs run** → ၂ ယောက်လုံး ထွက်ပြေးပြီး ရှင်သန်

## Game Flow

1. `/join` - Player တွေ ဝင်ကြ
2. `/start_game` - ပွဲစ
3. Round တိုင်းမှာ:
   - နေရာအသစ် + ဇာတ်လမ်းစာတို (၁-၂ ကြောင်း)
   - Player တွေကို pair ဖွဲ့ (ယခင် round ဆုံခဲ့သူ ပြန်မဆုံအောင်)
   - Odd number ဖြစ်ရင် ကျန်တဲ့ ၁ ယောက် zombie နဲ့ ဆုံ (50/50)
   - Bot နဲ့ ဆက်တိုက် ၂ ကြိမ် မကျအောင် ထိန်းထားတယ်
4. ၂ ယောက် ကျန်ရင် → Final Showdown (Best of 3)
5. Winner ကြေညာ

## Security Features

- **သက်ဆိုင်ရာ Player ပဲ နှိပ်ခွင့်ရ** - duel ထဲ မပါတဲ့ player နှိပ်ရင်:
  - ပထမအကြိမ်: သတိပေး
  - ဒုတိယအကြိမ်: ပြိုင်ပွဲက ထုတ်ပစ် (ဇွန်ဘီ သတ်ခံရ)
- **ပြိုင်ပွဲမှာ မပါသူ** နှိပ်လို့ မရ
- **Group အလိုက် game state** - group တစ်ခုနဲ့ တစ်ခု မရောဘူး
- **Thread-safe** - threading.Lock သုံးထားတယ်

## Timeout

- ၁၅ စက္ကန့်အတွင်း မနှိပ်ရင် auto-lose
- Final မှာလည်း ၁၅ စက္ကန့် timeout

## Commands

- `/join` - ပြိုင်ပွဲဝင်
- `/start_game` - ပွဲစ
- `/cancel_game` - ပွဲဖျက် (admin/game starter only)
- `/rank` - Top 10 ranking ကြည့်
- `/broadcast <msg>` - Admin: group အားလုံးကို message ပို့
