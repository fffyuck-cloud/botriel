import discord
from discord import app_commands
from discord.ext import commands
import json, os, re, io, math, random, threading, time, unicodedata, urllib.request, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import timedelta
from typing import Union, Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID", "0"))
GIF_URL = "https://i.pinimg.com/originals/d2/a6/cc/d2a6cc7134978023c1149b3b27b305d4.gif"
POLICY_URL = "https://discord.com"

BLACK = 0x000000
DARKER = 0x0A0A0A

WELCOME_CHANNEL_ID = 1548691233143128064
RULE_CHANNEL_ID = 1548730728479719494

WARN_FILE = "warnings.json"
MUTE_FILE = "mutes.json"
SETTINGS_FILE = "settings.json"
CONFIG_FILE = "config.json"

AUTO_MUTE_SECONDS = 36

AUTO_REPLIES = [
    "noi chuyen lich su chut di ban",
    "tu ngu do khong phu hop o day",
    "minh khong thich kieu noi nay",
    "bo cai kieu noi do di",
    "noi tu te thoi nao",
]

BAD_WORDS = [
    "nhutgay", "nhutga", "nhatgay", "nutgay",
    "nhutbede", "nhutbd", "nhutpede", "nhutpd",
    "nhutlgbt", "nhutbong", "gaynhut",
]

SCAM_IMAGE_WORDS = [
    "zevawin", "vyro", "withdrawal success", "withdraw success",
    "crypto casino", "casino crypto", "promo code", "promocode",
    "usdt", "tether", "bitcoin", "ethereum", "crypto",
    "bank card", "wallet address", "withdrawal method",
    "select a withdraw", "enter wallet", "withdrawal amount",
    "claim reward", "claim bonus", "activate code", "activate bonus",
    "free nitro", "free robux", "free gift", "giveaway",
    "mrbeast", "mr beast", "mr.beast",
    "bonuses", "vip-club", "vip club", "rake back", "rakeback",
    "deposit", "withdraw", "transactions", "verification",
]

SCAM_IMAGE_DOMAINS = [
    "zevawin", "vyro", "bit.ly", "tinyurl", "cutt.ly", "shorturl",
    "steamcommunit", "steamcomrnunity", "dlscord", "discord-nitro",
    "discordgift", "discord-airdrop", "free-nitro", "nitro-gift",
]

SCAM_IMAGE_REGEX = [
    r"\$\s?\d{3,}",
    r"\d{3,}\s?(usdt|usd)",
    r"promo\s?code",
    r"ma\s?khuyen\s?mai",
    r"withdraw(al)?\s+success",
    r"zevawin",
    r"vyro",
    r"code\s?[:=]?\s?bet\b",
    r"bonus",
    r"casino",
]

SCAM_LOG_CHANNEL_KEY = "scamLog"

ROAST_TEXT = "is stupid"
TEMPLATE_FILE = "arrow.png"
TEMPLATE_URL = "https://i.pinimg.com/1200x/d0/ef/e9/d0efe9560ad8d16e47643939024025c6.jpg"
_tpl_cache = None
_avatar_cache = {}
_last_msg = {}


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def run_keepalive():
    try:
        HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), PingHandler).serve_forever()
    except Exception:
        pass


threading.Thread(target=run_keepalive, daemon=True).start()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.bans = True

bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    help_command=None,
    case_insensitive=True,
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
)
tree = bot.tree


def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    return d
    except Exception:
        pass
    return {}


def save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def normalize_text(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s\._\-*/\\]+", "", text)


def base_embed(title=None, description=None, member=None):
    e = discord.Embed(title=title, description=description, color=BLACK, timestamp=discord.utils.utcnow())
    if member:
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
    return e


def log_embed(title, img=None):
    e = discord.Embed(title=title, color=BLACK)
    e.set_image(url=img or GIF_URL)
    e.set_footer(text="Log System")
    return e


def clean(t):
    return t.replace("```", "``\u200b`") if t else "(trong)"


def part(t, n):
    return [t[i:i+n] for i in range(0, len(t), n)] or [""]


def progress_bar(cur, total, length=10):
    filled = int(length * cur / total)
    return "█" * filled + "░" * (length - filled)


def fmt_time(sec):
    if sec < 60:
        return f"{sec} giay"
    if sec < 3600:
        return f"{sec//60} phut"
    if sec < 86400:
        return f"{sec//3600} gio"
    return f"{sec//86400} ngay"


def parse_duration(text):
    m = re.fullmatch(r"(\d+)([spmhd])", text.lower().strip())
    if not m:
        return None
    a, u = int(m.group(1)), m.group(2)
    if u == "s":
        return a if 1 <= a <= 60 else None
    if u in ("p", "m"):
        return a * 60 if 1 <= a <= 60 else None
    if u == "h":
        return a * 3600 if 1 <= a <= 24 else None
    if u == "d":
        return a * 86400 if 1 <= a <= 28 else None
    return None


def ocr_image_bytes(data):
    if not HAS_OCR:
        return ""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        if img.width > 1600:
            img = img.resize((1600, int(img.height * 1600 / img.width)))
        return pytesseract.image_to_string(img).lower()
    except Exception:
        return ""


def is_scam_image_text(text):
    if not text or not text.strip():
        return False
    if any(d in text for d in SCAM_IMAGE_DOMAINS):
        return True
    hits = sum(1 for w in SCAM_IMAGE_WORDS if w in text)
    if hits >= 3:
        return True
    if any(re.search(p, text) for p in SCAM_IMAGE_REGEX) and hits >= 2:
        return True
    return False


async def check_scam_images(message):
    if not HAS_OCR:
        return False
    for att in message.attachments:
        if not (att.content_type and att.content_type.startswith("image/")):
            continue
        try:
            data = await att.read()
        except Exception:
            continue
        text = ocr_image_bytes(data)
        if is_scam_image_text(text):
            return True
    return False


def download_template():
    if os.path.exists(TEMPLATE_FILE):
        return
    try:
        req = urllib.request.Request(TEMPLATE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r, open(TEMPLATE_FILE, "wb") as f:
            f.write(r.read())
    except Exception:
        pass


def load_font(size):
    for path in ["Caveat-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "C:/Windows/Fonts/Inkfree.ttf", "C:/Windows/Fonts/comici.ttf"]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def handdrawn_line(draw, start, end, width=8):
    for _ in range(2):
        pts = []
        for i in range(21):
            t = i / 20
            pts.append((start[0] + (end[0]-start[0])*t + random.uniform(-3, 3),
                        start[1] + (end[1]-start[1])*t + random.uniform(-3, 3)))
        draw.line(pts, fill="white", width=width, joint="curve")


def get_template():
    global _tpl_cache
    if _tpl_cache is not None:
        return _tpl_cache
    if not os.path.exists(TEMPLATE_FILE):
        return None
    tpl = Image.open(TEMPLATE_FILE).convert("RGBA")
    if tpl.width > 1200:
        tpl = tpl.resize((1200, int(tpl.height * 1200 / tpl.width)))
    mask = tpl.convert("L").point(lambda v: 255 if v > 40 else 0)
    tpl.putalpha(mask)
    _tpl_cache = tpl
    return tpl


def create_roast_image(avatar_bytes):
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar = ImageOps.fit(avatar, (280, 280))
    tpl = get_template()
    if tpl:
        tw, th = tpl.size
        tip = (int(tw * 0.11), int(th * 0.81))
        GAP, AV = 25, 280
        AV_X = 60
        tpl_x = AV_X + AV + GAP - tip[0]
        tpl_y = 20
        av_x, av_y = AV_X, max(10, tpl_y + tip[1] - AV // 2)
        W = tpl_x + tw + 10
        H = max(th + tpl_y, av_y + AV + 10, 300)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        canvas.alpha_composite(avatar, (av_x, av_y))
        canvas.alpha_composite(tpl, (tpl_x, tpl_y))
    else:
        W, H = 1250, 400
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        canvas.paste(avatar, (100, 60), avatar)
        draw = ImageDraw.Draw(canvas)
        tip, tail = (435, 340), (670, 110)
        handdrawn_line(draw, tail, tip)
        ang = math.atan2(tip[1]-tail[1], tip[0]-tail[0])
        for s in (1, -1):
            a = ang + math.pi + s * 0.5
            handdrawn_line(draw, tip, (tip[0]+90*math.cos(a), tip[1]+90*math.sin(a)))
        font = load_font(110)
        layer = Image.new("RGBA", (580, 220), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((0, 0), ROAST_TEXT, font=font, fill="white")
        layer = layer.rotate(8, expand=True, resample=Image.BICUBIC)
        canvas.alpha_composite(layer, (700, 55))
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf


async def get_avatar(member):
    key = (member.id, str(member.display_avatar))
    now = time.time()
    if key in _avatar_cache and now - _avatar_cache[key][1] < 600:
        return _avatar_cache[key][0]
    data = await member.display_avatar.replace(format="png", size=256).read()
    _avatar_cache[key] = (data, now)
    if len(_avatar_cache) > 200:
        oldest = min(_avatar_cache, key=lambda k: _avatar_cache[k][1])
        _avatar_cache.pop(oldest, None)
    return data


async def send_with_roast(ctx, embed, member):
    try:
        data = await get_avatar(member)
        buf = create_roast_image(data)
        file = discord.File(buf, filename="roast.png")
        embed.set_image(url="attachment://roast.png")
        await ctx.send(embed=embed, file=file)
    except Exception:
        await ctx.send(embed=embed)


SETTINGS = load_json(SETTINGS_FILE)


def get_ch(guild, key):
    cid = SETTINGS.get(str(guild.id), {}).get(key)
    return guild.get_channel(int(cid)) if cid else None


def set_ch(gid, key, cid):
    SETTINGS.setdefault(str(gid), {})[key] = str(cid)
    save_json(SETTINGS_FILE, SETTINGS)


CONFIG = load_json(CONFIG_FILE)


def get_cfg(guild_id):
    return CONFIG.get(str(guild_id), {})


def save_config():
    save_json(CONFIG_FILE, CONFIG)


def is_staff(member):
    p = member.guild_permissions
    if p.administrator or p.manage_guild or p.manage_channels:
        return True
    cfg = get_cfg(member.guild.id)
    ids = [cfg.get("admin_role_id"), cfg.get("support_role_id")]
    return any(member.get_role(r) for r in ids if r)


def get_category(guild):
    cid = get_cfg(guild.id).get("category_id")
    if not cid:
        return None
    ch = guild.get_channel(cid)
    if isinstance(ch, discord.TextChannel):
        return ch.category
    if isinstance(ch, discord.CategoryChannel):
        return ch
    return None


def get_ping_roles(guild):
    cfg = get_cfg(guild.id)
    roles = []
    for rid in (cfg.get("admin_role_id"), cfg.get("support_role_id")):
        if rid:
            r = guild.get_role(rid)
            if r and r not in roles:
                roles.append(r)
    if roles:
        return roles
    for r in guild.roles:
        if r.is_default() or r.managed:
            continue
        n = r.name.lower()
        if "admin" in n or "support" in n or "mod" in n:
            roles.append(r)
        if len(roles) >= 2:
            break
    return roles


async def send_log(guild, key, embeds):
    ch = get_ch(guild, key)
    if ch:
        for i in range(0, len(embeds), 10):
            await ch.send(embeds=embeds[i:i+10])


@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        await bot.process_commands(message)
        return

    n = normalize_text(message.content)

    if message.attachments:
        is_mod = (message.author.guild_permissions.moderate_members or
                  message.author.guild_permissions.administrator)
        if not is_mod:
            scam = await check_scam_images(message)
            if scam:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    e = base_embed("ANTI-SCAM", member=message.author)
                    e.description = (
                        f"{message.author.mention} vua gui anh lua dao\n"
                        f"Kenh: {message.channel.mention}\n"
                        "Tin nhan da bi xoa")
                    e.set_thumbnail(url=message.author.display_avatar.url)
                    e.set_image(url=GIF_URL)
                    warn_msg = await message.channel.send(
                        content=f"{message.author.mention} dung gui anh lua dao o day",
                        embed=e)
                    await asyncio.sleep(6)
                    await warn_msg.delete()
                except Exception:
                    pass
                log_ch = get_ch(message.guild, SCAM_LOG_CHANNEL_KEY)
                if log_ch:
                    try:
                        files = []
                        for att in message.attachments[:4]:
                            try:
                                files.append(await att.to_file())
                            except Exception:
                                pass
                        e = base_embed("CANH BAO SCAM", member=message.author)
                        e.description = (
                            f"**Nguoi gui:** {message.author.mention} `{message.author.id}`\n"
                            f"**Kenh:** {message.channel.mention}\n"
                            f"**Loai:** anh lua dao")
                        e.set_thumbnail(url=message.author.display_avatar.url)
                        e.set_image(url=GIF_URL)
                        if files:
                            await log_ch.send(embed=e, files=files)
                        else:
                            await log_ch.send(embed=e)
                    except Exception:
                        pass
                return

    if any(w in n for w in BAD_WORDS):
        member = message.author
        if member.guild_permissions.moderate_members or member.guild_permissions.administrator:
            await bot.process_commands(message)
            return
        already = member.timed_out_until and member.timed_out_until > discord.utils.utcnow()
        try:
            await message.delete()
        except Exception:
            pass
        if not already:
            until = discord.utils.utcnow() + timedelta(seconds=AUTO_MUTE_SECONDS)
            try:
                await member.timeout(until, reason="auto-mod")
                mutes = load_json(MUTE_FILE)
                mutes.setdefault(str(message.guild.id), {})[f"automod_{member.id}"] = {
                    "until": until.isoformat(),
                    "mod": "AUTO-MOD",
                    "reason": "noi tu cam"}
                save_json(MUTE_FILE, mutes)
                e = base_embed("AUTO-MUTE", member=member)
                e.description = f"{member.mention} bi cam mom {AUTO_MUTE_SECONDS}s"
                e.set_thumbnail(url=member.display_avatar.url)
                e.set_image(url=GIF_URL)
                await message.channel.send(content=f"{member.mention} {random.choice(AUTO_REPLIES)}", embed=e)
            except Exception:
                pass

    ch = get_ch(message.guild, "messageLog")
    if ch:
        user = message.author
        avatar = user.display_avatar.url
        info = (f"**Nguoi dung:** {user.mention} `{user}`\n"
                f"**Kenh:** {message.channel.mention} `#{message.channel.name}`\n"
                f"<t:{int(message.created_at.timestamp())}:R>\n\n")
        reply = ""
        if message.reference and message.reference.resolved:
            try:
                reply = f"**Reply:** {message.reference.resolved.author.mention}\n\n"
            except Exception:
                pass
        gifs = [a for a in message.attachments if a.content_type == "image/gif"]
        imgs = [a for a in message.attachments if a.content_type and
                a.content_type.startswith("image/") and a.content_type != "image/gif"]
        files = [a for a in message.attachments
                 if not a.content_type or not a.content_type.startswith("image/")]
        links = re.findall(r"https?://\S+", message.content or "")
        text = re.sub(r"https?://\S+", "", message.content or "").strip()
        try:
            if gifs:
                e = log_embed("GIF MOI", gifs[0].url)
                e.set_author(name=f"GIF • {user}", icon_url=avatar)
                e.description = info + f"**So luong:** `{len(gifs)}`"
                es = [e] + [discord.Embed(color=BLACK).set_image(url=g.url) for g in gifs[1:]]
                await send_log(message.guild, "messageLog", es)
            if imgs:
                e = log_embed("ANH MOI", imgs[0].url)
                e.set_author(name=f"Anh • {user}", icon_url=avatar)
                e.description = info + f"**So luong:** `{len(imgs)}`"
                es = [e] + [discord.Embed(color=BLACK).set_image(url=a.url) for a in imgs[1:]]
                await send_log(message.guild, "messageLog", es)
            if links:
                body = info + reply + f"**Link:** `{len(links)}`\n\n" + \
                       "\n".join(f"`{i+1}.` {l}" for i, l in enumerate(links))
                for idx, p in enumerate(part(clean(body), 4000)):
                    e = log_embed("LINK MOI" if not idx else f"LINK ({idx+1})")
                    e.set_author(name=f"Link • {user}", icon_url=avatar)
                    e.description = p
                    await ch.send(embed=e)
            if files:
                body = info + f"**File:** `{len(files)}`\n\n" + "\n".join(
                    f"`{i+1}.` **{f.filename}** • `{f.size/1024:.1f} KB` • [Tai]({f.url})"
                    for i, f in enumerate(files))
                for idx, p in enumerate(part(clean(body), 4000)):
                    e = log_embed("FILE MOI" if not idx else f"FILE ({idx+1})")
                    e.set_author(name=f"File • {user}", icon_url=avatar)
                    e.description = p
                    await ch.send(embed=e)
            if text:
                body = info + reply + "**Noi dung:**\n"
                for idx, p in enumerate(part(clean(text), 3600)):
                    e = log_embed("TIN NHAN MOI" if not idx else f"TIN NHAN ({idx+1})")
                    e.set_author(name=f"Chat • {user}", icon_url=avatar)
                    e.description = body + f"```\n{p}\n```" if not idx else f"```\n{p}\n```"
                    await ch.send(embed=e)
        except Exception:
            pass

    await bot.process_commands(message)


@bot.event
async def on_message_delete(message):
    if not message.guild or (message.author and message.author.bot):
        return
    ch = get_ch(message.guild, "messageLog")
    if not ch:
        return
    try:
        img = message.attachments[0].url if message.attachments else GIF_URL
        e = log_embed("TIN NHAN BI XOA", img)
        if message.author:
            e.set_author(name=f"Xoa • {message.author}", icon_url=message.author.display_avatar.url)
            who = f"**{message.author.mention}** `{message.author}`\n"
        else:
            who = "`Khong ro`\n"
        attach = "\n".join(f"`{a.filename}`" for a in message.attachments) if message.attachments else "khong co"
        parts = part(clean(message.content), 3400)
        e.description = (who + f"{message.channel.mention} `#{message.channel.name}`\n\n"
                         f"**Da xoa:**\n```\n{parts[0]}\n```\n**File:** {attach}")
        es = [e]
        for p in parts[1:]:
            e2 = log_embed("(tiep)")
            e2.description = f"```\n{p}\n```"
            es.append(e2)
        await send_log(message.guild, "messageLog", es)
    except Exception:
        pass


@bot.event
async def on_message_edit(before, after):
    if not before.guild or (before.author and before.author.bot):
        return
    if before.content == after.content:
        return
    ch = get_ch(before.guild, "messageLog")
    if not ch:
        return
    try:
        user = before.author
        e = log_embed("TIN NHAN SUA")
        e.set_author(name=f"Sua • {user}", icon_url=user.display_avatar.url)
        e.description = (f"**{user.mention}**\n{before.channel.mention}\n\n"
                         f"**Cu:**\n```\n{clean(before.content)[:1800]}\n```\n"
                         f"**Moi:**\n```\n{clean(after.content)[:1800]}\n```\n"
                         f"[Xem tin]({after.jump_url})")
        await ch.send(embed=e)
    except Exception:
        pass


@bot.event
async def on_member_ban(guild, user):
    ch = get_ch(guild, "serverLog")
    if not ch:
        return
    e = log_embed("BI BAN", user.display_avatar.url)
    e.set_author(name=f"Ban • {user}", icon_url=user.display_avatar.url)
    e.description = f"**{user.mention}** `{user}`\nID: `{user.id}`"
    await ch.send(embed=e)


@bot.event
async def on_member_unban(guild, user):
    ch = get_ch(guild, "serverLog")
    if not ch:
        return
    e = log_embed("DUOC UNBAN", user.display_avatar.url)
    e.set_author(name=f"Unban • {user}", icon_url=user.display_avatar.url)
    e.description = f"**{user.mention}** `{user}`\nID: `{user.id}`"
    await ch.send(embed=e)


@bot.event
async def on_voice_state_update(member, before, after):
    ch = get_ch(member.guild, "voiceLog")
    if not ch:
        return
    try:
        if not before.channel and after.channel:
            t, desc = "VAO VOICE", f"`{after.channel.name}`"
        elif before.channel and not after.channel:
            t, desc = "ROI VOICE", f"`{before.channel.name}`"
        elif before.channel != after.channel and after.channel:
            t, desc = "CHUYEN VOICE", f"`{before.channel.name}` -> `{after.channel.name}`"
        else:
            return
        e = log_embed(t)
        e.set_author(name=f"Voice • {member}", icon_url=member.display_avatar.url)
        e.description = f"**{member.mention}**\n{desc}"
        await ch.send(embed=e)
    except Exception:
        pass


@bot.event
async def on_guild_channel_create(c):
    ch = get_ch(c.guild, "serverLog")
    if ch:
        e = log_embed("TAO KENH")
        e.description = f"{c.mention} `#{c.name}`"
        await ch.send(embed=e)


@bot.event
async def on_guild_channel_delete(c):
    ch = get_ch(c.guild, "serverLog")
    if ch:
        e = log_embed("XOA KENH")
        e.description = f"`#{c.name}`"
        await ch.send(embed=e)


@bot.event
async def on_guild_role_create(r):
    ch = get_ch(r.guild, "serverLog")
    if ch:
        e = log_embed("TAO ROLE")
        e.description = f"{r.mention} `{r.name}`"
        await ch.send(embed=e)


@bot.event
async def on_guild_role_delete(r):
    ch = get_ch(r.guild, "serverLog")
    if ch:
        e = log_embed("XOA ROLE")
        e.description = f"`@{r.name}`"
        await ch.send(embed=e)


@bot.event
async def on_member_join(member):
    ch = bot.get_channel(WELCOME_CHANNEL_ID)
    if not ch:
        return
    e = discord.Embed(
        title="Chao mung thanh vien moi",
        description=(f"Chao **{member.mention}** da den voi **{member.guild.name}**\n\n"
                     f"Doc luat o <#{RULE_CHANNEL_ID}>\nChat cung moi nguoi nhe"),
        color=BLACK)
    e.set_image(url=GIF_URL)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Ten", value=member.name, inline=True)
    e.add_field(name="Thanh vien thu", value=str(member.guild.member_count), inline=True)
    e.set_footer(text=f"ID: {member.id}")
    await ch.send(content=f"{member.mention}", embed=e)


class CloseReasonModal(discord.ui.Modal, title="Dong Ticket"):
    ly_do = discord.ui.TextInput(
        label="Ly do dong ticket",
        style=discord.TextStyle.paragraph,
        placeholder="VD: da ho tro xong",
        required=False, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        staff = " ".join(r.mention for r in get_ping_roles(interaction.guild))
        desc = (f"**Ly do:** {self.ly_do.value or 'khong co'}\n"
                f"**Nguoi dong:** {interaction.user.mention}\n"
                + (f"**Thong bao:** {staff}\n" if staff else "")
                + "\nXac nhan dong ticket?")
        await interaction.response.send_message(
            embed=base_embed("XAC NHAN DONG TICKET", desc), view=ConfirmClose())


class TicketControl(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="NHAN XU LY", style=discord.ButtonStyle.secondary, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                embed=base_embed(description="chi staff moi nhan duoc"), ephemeral=True)
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            embed=base_embed(description=f"{interaction.user.mention} da nhan ticket"))

    @discord.ui.button(label="DONG TICKET", style=discord.ButtonStyle.secondary, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseReasonModal())


class ConfirmClose(discord.ui.View):
    @discord.ui.button(label="XAC NHAN", style=discord.ButtonStyle.secondary)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=base_embed(description="ticket se bi xoa sau 5 giay"))
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason="Ticket closed")
        except Exception:
            pass

    @discord.ui.button(label="HUY", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class TicketPanel(discord.ui.View):
    def __init__(self, policy_link: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="CHINH SACH MUA HANG",
            style=discord.ButtonStyle.link, url=policy_link))

    @discord.ui.button(label="MUA HANG", style=discord.ButtonStyle.secondary, custom_id="ticket_buy")
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "mua-hang", "MUA HANG")

    @discord.ui.button(label="HO TRO", style=discord.ButtonStyle.secondary, custom_id="ticket_support")
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, "ho-tro", "HO TRO")


def panel_embed(guild):
    e = base_embed(
        title="HO TRO KHACH HANG",
        description=(
            "**MUA HANG:**\n"
            "Muon mua key ban quyen hoac dich vu toi uu PC\n\n"
            "**HO TRO:**\n"
            "Can kich hoat key, cai dat, bao hanh hoac gap loi sau khi mua\n\n"
            "Vui long khong spam ticket\n"
            "Khach hang la thuong de\n"
            "Mua hang = chap nhan Rules & Chinh sach"))
    e.set_image(url=GIF_URL)
    e.set_footer(text=f"{guild.name} • TICKET SUPPORT")
    return e


def ticket_embed(guild, user, loai):
    e = base_embed(
        title=f"TICKET {loai}",
        description=(
            f"Chao {user.mention}\n\n"
            "Mo ta chi tiet van de de staff ho tro nhanh nhat.\n\n"
            "Khong spam / ping staff lien tuc\n"
            "Khong chia se thong tin ca nhan\n"
            "Staff se phan hoi trong it phut"))
    e.set_thumbnail(url=user.display_avatar.url)
    e.set_image(url=GIF_URL)
    e.set_footer(text=f"{guild.name} • TICKET SUPPORT")
    return e


async def open_ticket(interaction, slug, loai):
    try:
        await _open_ticket(interaction, slug, loai)
    except Exception as e:
        msg = base_embed(description=f"loi: `{e}`")
        if interaction.response.is_done():
            await interaction.followup.send(embed=msg, ephemeral=True)
        else:
            await interaction.response.send_message(embed=msg, ephemeral=True)


async def _open_ticket(interaction, slug, loai):
    guild, user = interaction.guild, interaction.user
    category = get_category(guild)
    if not category:
        return await interaction.response.send_message(
            embed=base_embed(description="server chua cai dat, admin go /setup truoc"),
            ephemeral=True)
    for ch in category.text_channels:
        if ch.topic and ch.topic.startswith(f"ticket|{user.id}|"):
            return await interaction.response.send_message(
                embed=base_embed(description=f"ban da co ticket: {ch.mention}"),
                ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    ping_roles = get_ping_roles(guild)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    for role in ping_roles:
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True)
    for role in guild.roles:
        if role.is_default():
            continue
        p = role.permissions
        if p.administrator or p.manage_guild or p.manage_channels:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True)
    try:
        channel = await guild.create_text_channel(
            name=f"{slug}-{user.name}", category=category,
            topic=f"ticket|{user.id}|{slug}", overwrites=overwrites)
    except discord.Forbidden:
        return await interaction.followup.send(
            embed=base_embed(description="bot thieu quyen Manage Channels"),
            ephemeral=True)
    mention = " ".join(r.mention for r in ping_roles)
    content = user.mention + (f" • {mention}" if mention else "")
    await channel.send(content, embed=ticket_embed(guild, user, loai), view=TicketControl())
    await interaction.followup.send(
        embed=base_embed(description=f"ticket cua ban: {channel.mention}"),
        ephemeral=True)


class ChannelPick(discord.ui.ChannelSelect):
    def __init__(self, key, label):
        super().__init__(placeholder="Chon kenh log", channel_types=[discord.ChannelType.text])
        self.key, self.label = key, label

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.guild.get_channel(self.values[0].id)
        if not channel:
            return
        set_ch(interaction.guild_id, self.key, channel.id)
        e = base_embed("DA CAI DAT")
        e.description = f"Loai: `{self.label}`\nKenh: {channel.mention}\nBoi: {interaction.user.mention}"
        await interaction.followup.send(embed=e, ephemeral=True)


class LogMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(placeholder="Chon loai log", options=[
        discord.SelectOption(label="Log Tin nhan", value="messageLog",
                             description="Chat, anh, gif, link, file"),
        discord.SelectOption(label="Log Server", value="serverLog",
                             description="Ban, kenh, role"),
        discord.SelectOption(label="Log Voice", value="voiceLog",
                             description="Vao, roi, chuyen kenh"),
        discord.SelectOption(label="Log Scam", value="scamLog",
                             description="Anh lua dao bi xoa"),
        discord.SelectOption(label="Xem cai dat", value="view",
                             description="Xem kenh log da cai"),
    ])
    async def select_menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return
        choice = select.values[0]
        if choice == "view":
            s = SETTINGS.get(str(interaction.guild_id), {})
            def g(k):
                c = interaction.guild.get_channel(int(s[k])) if s.get(k) else None
                return f"{c.mention}" if c else "`chua cai`"
            e = base_embed("CAI DAT HIEN TAI")
            e.description = (f"Tin nhan: {g('messageLog')}\n"
                             f"Server: {g('serverLog')}\n"
                             f"Voice: {g('voiceLog')}\n"
                             f"Scam: {g('scamLog')}")
            await interaction.followup.send(embed=e, ephemeral=True)
            return
        labels = {"messageLog": "TIN NHAN", "serverLog": "SERVER",
                  "voiceLog": "VOICE", "scamLog": "SCAM"}
        v = discord.ui.View(timeout=120)
        v.add_item(ChannelPick(choice, labels[choice]))
        await interaction.followup.send(f"Chon kenh log {labels[choice]}:", view=v, ephemeral=True)


@tree.command(name="log", description="cai dat kenh log")
async def log_cmd(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("chi admin", ephemeral=True)
    e = base_embed("CAI DAT LOG", "Chon loai log")
    await interaction.response.send_message(embed=e, view=LogMenu(), ephemeral=True)


@tree.command(name="help", description="bang lenh")
async def help_cmd(interaction: discord.Interaction):
    e = base_embed("LENH BOT")
    e.description = (
        "**Slash:** `/log` `/help` `/ping` `/setup` `/panel` `/ticket`\n\n"
        "**Mod (prefix /):**\n"
        "`/m` mute • `/um` unmute • `/mi` info mute\n"
        "`/b` ban • `/ub` unban • `/bl` banlist\n"
        "`/w` warn • `/ws` warns • `/cw` clearwarn\n\n"
        "**Anti-scam:** bot doc chu trong anh, xoa anh lua dao")
    await interaction.response.send_message(embed=e, ephemeral=True)


@tree.command(name="ping", description="do tre bot")
async def ping_cmd(interaction: discord.Interaction):
    e = base_embed("PONG", f"`{round(bot.latency*1000)}ms`")
    await interaction.response.send_message(embed=e, ephemeral=True)


@tree.command(name="setup", description="cai dat ticket cho server")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    category="category chua ticket",
    admin_role="role admin duoc tag",
    support_role="role support duoc tag")
async def setup(interaction: discord.Interaction,
                category: Union[discord.CategoryChannel, discord.TextChannel],
                admin_role: Optional[discord.Role] = None,
                support_role: Optional[discord.Role] = None):
    cfg = CONFIG.setdefault(str(interaction.guild_id), {})
    cfg["category_id"] = category.id if isinstance(category, discord.CategoryChannel) else category.category_id
    cfg["admin_role_id"] = admin_role.id if admin_role else 0
    cfg["support_role_id"] = support_role.id if support_role else 0
    save_config()
    roles_txt = []
    if admin_role:
        roles_txt.append(admin_role.mention)
    if support_role:
        roles_txt.append(support_role.mention)
    tag_txt = " • ".join(roles_txt) if roles_txt else "tu tim role admin/support/mod"
    await interaction.response.send_message(
        embed=base_embed("DA CAI DAT",
            f"Category: {category.mention if isinstance(category, discord.TextChannel) else category.name}\n"
            f"Tag: {tag_txt}\n\n"
            "Go `/panel` de gui bang ticket"),
        ephemeral=True)


@setup.error
async def setup_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("chi admin", ephemeral=True)


@tree.command(name="panel", description="gui bang ticket")
@app_commands.checks.has_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    cfg = get_cfg(interaction.guild_id)
    if not cfg.get("category_id"):
        return await interaction.response.send_message("chua cai dat, go /setup truoc", ephemeral=True)
    link = cfg.get("policy_link") or POLICY_URL
    await interaction.response.send_message(embed=panel_embed(interaction.guild), view=TicketPanel(link))


@panel.error
async def panel_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("chi admin", ephemeral=True)


@tree.command(name="ticket", description="tao ticket ngay")
@app_commands.choices(loai=[
    app_commands.Choice(name="MUA HANG", value="mua-hang"),
    app_commands.Choice(name="HO TRO", value="ho-tro"),
])
async def ticket_cmd(interaction: discord.Interaction, loai: app_commands.Choice[str] = None):
    slug = loai.value if loai else "ho-tro"
    ten = "MUA HANG" if slug == "mua-hang" else "HO TRO"
    await open_ticket(interaction, slug, ten)


class WarnActionView(discord.ui.View):
    def __init__(self, member):
        super().__init__(timeout=600)
        self.member = member
        self.message = None

    @discord.ui.button(label="Ban ngay", style=discord.ButtonStyle.danger)
    async def ban_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("khong du quyen ban", ephemeral=True)
        try:
            await self.member.ban(reason=f"du 5 warn | boi {interaction.user}")
        except discord.Forbidden:
            return await interaction.response.send_message("bot thieu quyen ban", ephemeral=True)
        except discord.NotFound:
            return await interaction.response.send_message("nguoi dung da roi server", ephemeral=True)
        warnings = load_json(WARN_FILE)
        gid, uid = str(interaction.guild_id), str(self.member.id)
        if gid in warnings and uid in warnings[gid]:
            del warnings[gid][uid]
            save_json(WARN_FILE, warnings)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"**{self.member}** da bi ban boi **{interaction.user}**",
            embed=None, view=self)
        e = base_embed("DA BAN", member=self.member)
        e.description = f"**{self.member.mention}** bi ban. ID: `{self.member.id}`"
        e.set_image(url=GIF_URL)
        await interaction.channel.send(embed=e)

    @discord.ui.button(label="Xoa het warn", style=discord.ButtonStyle.secondary)
    async def clear_warns(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("khong du quyen", ephemeral=True)
        warnings = load_json(WARN_FILE)
        gid, uid = str(interaction.guild_id), str(self.member.id)
        if gid in warnings and uid in warnings[gid]:
            del warnings[gid][uid]
            save_json(WARN_FILE, warnings)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"**{interaction.user}** da xoa warn cho **{self.member}**",
            embed=None, view=self)

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


async def cooldown_check(ctx):
    key = (ctx.author.id, ctx.command.qualified_name)
    now = time.time()
    last = _last_msg.get(key, 0)
    if now - last < 3:
        raise commands.CommandOnCooldown(None, 3 - (now - last))
    _last_msg[key] = now
    return True


bot.add_check(cooldown_check)


@bot.command(aliases=["m"])
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member = None, time_str: str = None, *, reason=None):
    if member is None:
        return await ctx.send(embed=base_embed("Thieu nguoi dung", "/m @user 10m ly_do", ctx.author))
    seconds = parse_duration(time_str) if time_str else None
    if time_str and seconds is None:
        reason = f"{time_str} {reason}" if reason else time_str
        time_str = None
    if member == ctx.author:
        return await ctx.send(embed=base_embed("Loi", "tu mute minh lam gi", ctx.author))
    if member.bot:
        return await ctx.send(embed=base_embed("Loi", "bot khong co mom de mute", ctx.author))
    if member.guild_permissions.moderate_members and ctx.author != ctx.guild.owner:
        return await ctx.send(embed=base_embed("Loi", "khong the mute mod", ctx.author))
    if seconds is None:
        seconds = 28 * 86400
    until = discord.utils.utcnow() + timedelta(seconds=seconds)
    try:
        await member.timeout(until, reason=f"{ctx.author} | {reason or 'khong ly do'}")
    except discord.Forbidden:
        return await ctx.send(embed=base_embed("Bot thieu quyen", "can quyen Timeout Members", ctx.author))
    mutes = load_json(MUTE_FILE)
    mutes.setdefault(str(ctx.guild.id), {})[str(member.id)] = {
        "until": until.isoformat(), "mod": str(ctx.author), "reason": reason or "khong ly do"}
    save_json(MUTE_FILE, mutes)
    try:
        dm = base_embed("Bi mute", member=ctx.author)
        dm.add_field(name="Server", value=ctx.guild.name, inline=False)
        dm.add_field(name="Thoi luong", value=fmt_time(seconds), inline=True)
        dm.add_field(name="Ly do", value=reason or "khong ly do", inline=True)
        dm.add_field(name="Mod", value=str(ctx.author), inline=True)
        await member.send(embed=dm)
    except Exception:
        pass
    e = base_embed("DA MUTE", member=member)
    e.color = DARKER
    e.description = f"{member.mention} bi mute den **{until.strftime('%H:%M:%S %d/%m/%Y')}**"
    e.add_field(name="Thoi luong", value=fmt_time(seconds), inline=True)
    e.add_field(name="Ly do", value=reason or "khong ly do", inline=True)
    e.add_field(name="Mod", value=ctx.author.mention, inline=True)
    e.set_thumbnail(url=member.display_avatar.url)
    await send_with_roast(ctx, e, member)


@bot.command(aliases=["um"])
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member = None):
    if member is None:
        return await ctx.send(embed=base_embed("Thieu nguoi dung", "tag nguoi can unmute", ctx.author))
    if member.timed_out_until is None:
        return await ctx.send(embed=base_embed("Loi", "nguoi nay khong bi mute", ctx.author))
    try:
        await member.timeout(None, reason=f"unmute boi {ctx.author}")
    except discord.Forbidden:
        return await ctx.send(embed=base_embed("Bot thieu quyen", "can Timeout Members", ctx.author))
    mutes = load_json(MUTE_FILE)
    gid, uid = str(ctx.guild.id), str(member.id)
    if gid in mutes and uid in mutes[gid]:
        del mutes[gid][uid]
        save_json(MUTE_FILE, mutes)
    e = base_embed("DA UNMUTE", member=member)
    e.add_field(name="Nguoi dung", value=member.mention, inline=True)
    e.add_field(name="Boi", value=ctx.author.mention, inline=True)
    e.set_thumbnail(url=member.display_avatar.url)
    e.set_image(url=GIF_URL)
    await ctx.send(embed=e)


@bot.command(aliases=["mi"])
async def muteinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    info = load_json(MUTE_FILE).get(str(ctx.guild.id), {}).get(str(member.id))
    if member.timed_out_until:
        until = member.timed_out_until
        total = int((until - discord.utils.utcnow()).total_seconds())
        e = base_embed("MUTE INFO", member=member)
        if total > 0:
            e.add_field(name="Con lai", value=fmt_time(total), inline=True)
        e.add_field(name="Het luc", value=until.strftime("%H:%M:%S %d/%m/%Y"), inline=True)
        if info:
            e.add_field(name="Ly do", value=info.get("reason", "?"), inline=False)
            e.add_field(name="Mod", value=info.get("mod", "?"), inline=True)
        e.set_thumbnail(url=member.display_avatar.url)
        return await ctx.send(embed=e)
    if info:
        return await ctx.send(embed=base_embed("MUTE INFO", f"het luc {info['until'][:19]}", member))
    return await ctx.send(embed=base_embed("Loi", "nguoi nay khong bi mute", member))


@bot.command(aliases=["b"])
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member = None, *, reason=None):
    if member is None:
        return await ctx.send(embed=base_embed("Thieu nguoi dung", "/b @user ly_do", ctx.author))
    if member == ctx.author:
        return await ctx.send(embed=base_embed("Loi", "tu ban minh lam gi", ctx.author))
    if member.bot:
        return await ctx.send(embed=base_embed("Loi", "khong ban bot", ctx.author))
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        return await ctx.send(embed=base_embed("Loi", "role nguoi nay cao hon ban", ctx.author))
    await member.ban(reason=f"{reason or 'khong ly do'} | Mod: {ctx.author}")
    try:
        dm = base_embed("Bi ban", member=ctx.author)
        dm.add_field(name="Server", value=ctx.guild.name, inline=False)
        dm.add_field(name="Ly do", value=reason or "khong ly do", inline=False)
        dm.add_field(name="Mod", value=str(ctx.author), inline=True)
        await member.send(embed=dm)
    except Exception:
        pass
    e = base_embed("DA BAN", member=member)
    e.color = DARKER
    e.description = f"{member.mention} bi ban khoi server"
    e.add_field(name="Ly do", value=reason or "khong ly do", inline=True)
    e.add_field(name="Mod", value=ctx.author.mention, inline=True)
    e.add_field(name="ID", value=f"`{member.id}`", inline=True)
    e.set_thumbnail(url=member.display_avatar.url)
    await send_with_roast(ctx, e, member)


@bot.command(aliases=["ub"])
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int = None, *, reason=None):
    if user_id is None:
        e = base_embed("UNBAN", "nhap ID: `/ub 123456789`")
        e.add_field(name="Khong biet ID?", value="dung `/bl` xem danh sach", inline=False)
        return await ctx.send(embed=e)
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"{ctx.author} | {reason or 'khong ly do'}")
        e = base_embed("DA UNBAN", member=user)
        e.add_field(name="Nguoi dung", value=f"{user.mention}\n`{user.id}`", inline=False)
        e.add_field(name="Mod", value=ctx.author.mention, inline=True)
        e.set_thumbnail(url=user.display_avatar.url)
        e.set_image(url=GIF_URL)
        await ctx.send(embed=e)
    except discord.NotFound:
        return await ctx.send(embed=base_embed("Loi", "nguoi nay khong bi ban", ctx.author))


@bot.command(aliases=["bl"])
@commands.has_permissions(ban_members=True)
async def banlist(ctx):
    bans = [b async for b in ctx.guild.bans()]
    if not bans:
        return await ctx.send(embed=base_embed("BAN LIST", "khong co ai bi ban", ctx.author))
    e = base_embed(f"DANH SACH BAN ({len(bans)})", member=ctx.author)
    for i, b in enumerate(bans[:25], 1):
        e.add_field(name=f"{i}. {b.user}", value=f"`{b.user.id}`", inline=True)
    e.set_footer(text="dung /ub <ID> de unban")
    await ctx.send(embed=e)


@bot.command(aliases=["w"])
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member = None, *, reason=None):
    if member is None:
        return await ctx.send(embed=base_embed("Thieu nguoi dung", "/w @user ly_do", ctx.author))
    if member.bot:
        return await ctx.send(embed=base_embed("Loi", "khong warn bot", ctx.author))
    warnings = load_json(WARN_FILE)
    gid, uid = str(ctx.guild.id), str(member.id)
    warnings.setdefault(gid, {}).setdefault(uid, [])
    warnings[gid][uid].append({"reason": reason or "khong ly do", "mod": str(ctx.author)})
    save_json(WARN_FILE, warnings)
    count = len(warnings[gid][uid])
    try:
        dm = base_embed("Bi canh bao", member=ctx.author)
        dm.add_field(name="Server", value=ctx.guild.name, inline=False)
        dm.add_field(name="Ly do", value=reason or "khong ly do", inline=False)
        dm.add_field(name="Lan", value=f"{progress_bar(count, 5)} `{count}/5`", inline=False)
        dm.add_field(name="Mod", value=str(ctx.author), inline=True)
        await member.send(embed=dm)
        dm_status = "da gui DM"
    except Exception:
        dm_status = "khong gui duoc DM"
    if count >= 5:
        e = base_embed("DU 5 WARN", member=member)
        e.description = (f"{member.mention} du **{count}/5** warn\n{progress_bar(count, 5)}\n\n"
                         "mod quyet dinh")
        e.add_field(name="Warn moi", value=reason or "khong ly do", inline=False)
        e.add_field(name="Mod", value=ctx.author.mention, inline=True)
        e.add_field(name="DM", value=dm_status, inline=True)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_image(url=GIF_URL)
        view = WarnActionView(member)
        view.message = await ctx.send(embed=e, view=view)
        return
    e = base_embed("DA WARN", member=member)
    e.description = f"{member.mention} vua nhan 1 warn"
    e.add_field(name="Tien do", value=f"{progress_bar(count, 5)} `{count}/5`", inline=False)
    e.add_field(name="Ly do", value=reason or "khong ly do", inline=True)
    e.add_field(name="Mod", value=ctx.author.mention, inline=True)
    e.add_field(name="DM", value=dm_status, inline=True)
    e.set_thumbnail(url=member.display_avatar.url)
    await send_with_roast(ctx, e, member)


@bot.command(aliases=["ws", "warnings"])
async def warns(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = load_json(WARN_FILE).get(str(ctx.guild.id), {}).get(str(member.id), [])
    e = base_embed("WARN INFO", member=member)
    e.set_thumbnail(url=member.display_avatar.url)
    if not data:
        e.description = "khong co warn nao"
    else:
        e.description = f"{member.mention} dang co `{len(data)}/5` warn\n{progress_bar(len(data), 5)}"
        for i, w in enumerate(data, 1):
            e.add_field(name=f"Warn #{i}", value=f"ly do: {w['reason']}\nmod: {w['mod']}", inline=False)
    await ctx.send(embed=e)


@bot.command(aliases=["cw"])
@commands.has_permissions(manage_messages=True)
async def clearwarn(ctx, member: discord.Member = None):
    if member is None:
        return await ctx.send(embed=base_embed("Thieu nguoi dung", "tag nguoi can xoa warn", ctx.author))
    warnings = load_json(WARN_FILE)
    gid, uid = str(ctx.guild.id), str(member.id)
    if gid in warnings and uid in warnings[gid]:
        del warnings[gid][uid]
        save_json(WARN_FILE, warnings)
        e = base_embed("DA XOA WARN", f"{member.mention} da duoc xoa het warn", member=member)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_image(url=GIF_URL)
        await ctx.send(embed=e)
    else:
        return await ctx.send(embed=base_embed("Loi", "nguoi nay khong co warn", ctx.author))


@bot.command(name="help")
async def help_prefix(ctx):
    e = base_embed("LENH BOT", member=ctx.author)
    e.description = (
        "**Mod:**\n"
        "`/m @user <30s|10p|2h|1d> [ly do]` - mute\n"
        "`/um @user` - unmute\n"
        "`/mi @user` - mute info\n"
        "`/b @user [ly do]` - ban\n"
        "`/ub <ID>` - unban\n"
        "`/bl` - ban list\n"
        "`/w @user [ly do]` - warn\n"
        "`/ws [@user]` - xem warn\n"
        "`/cw @user` - xoa warn\n\n"
        "**Slash:** `/log` `/setup` `/panel` `/ticket` `/ping` `/help`\n\n"
        "**Anti-scam:** bot tu doc chu trong anh, xoa anh lua dao")
    e.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=e)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        return await ctx.send(embed=base_embed("Tu tu", f"doi {error.retry_after:.1f}s", ctx.author), delete_after=5)
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send(embed=base_embed("Khong du quyen", None, ctx.author))
    if isinstance(error, commands.BotMissingPermissions):
        return await ctx.send(embed=base_embed("Bot thieu quyen", None, ctx.author))
    if isinstance(error, commands.MemberNotFound):
        return await ctx.send(embed=base_embed("Khong tim thay nguoi dung", None, ctx.author))
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(embed=base_embed("Thieu thong tin", "go /help xem cach dung", ctx.author))


@bot.event
async def setup_hook():
    download_template()
    if not HAS_OCR:
        print("canh bao: chua cai pytesseract, anti-scam anh se khong hoat dong")
    try:
        if GUILD_ID:
            g = discord.Object(id=GUILD_ID)
            tree.copy_global_to(guild=g)
            await tree.sync(guild=g)
        else:
            await tree.sync()
    except Exception as e:
        print("sync loi:", e)


@bot.event
async def on_ready():
    bot.add_view(TicketPanel(POLICY_URL))
    bot.add_view(TicketControl())
    print(f"online: {bot.user} | {len(bot.guilds)} server")
    try:
        await bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name="log he thong"))
    except Exception:
        pass


if __name__ == "__main__":
    bot.run(TOKEN)
