import logging
import discord
from discord import app_commands, ui
from discord.app_commands import Choice
from typing import List
from slpp import slpp as lua
import os
import sys
import asyncio
import time
import zipfile
import re
import aiofiles
import pathlib
import subprocess
import psutil
import shutil
import requests
import ast

# ------------- LOGGING CONFIGURATION ---------------
#LOG_FILE =r"C:\Users\tbell\Saved Games\DCS.dcs_serverrelease\dcs_admin_bot.log"
#LOG_FILE = os.path.join(os.path.dirname(__file__), "dcs_admin_bot.log")
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller EXE
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(__file__)

LOG_FILE = os.path.join(BASE_DIR, "dcs_admin_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        #logging.StreamHandler()  # Optional: also log to console
    ]
)
logging.info("Test log: Bot started")
# ---------------------------------------------------

# ------------- CONFIGURATION ---------------

DCS_SERVER = os.environ["DCS_SERVER"]
DCS_SAVED_GAMES = os.environ["DCS_SAVED_GAMES"]
DCS_SCRIPTS = os.path.join(DCS_SAVED_GAMES, "Scripts")
DCS_DISCORD_BOT = os.path.join(DCS_SCRIPTS, "Discord_Admin_Bot")
DCS_MISSIONS = os.path.join(DCS_SAVED_GAMES, "Missions")
DCS_CONFIG = os.path.join(DCS_SAVED_GAMES, "Config")
DCS_SERVER_BIN = os.path.join(DCS_SERVER, "bin")
DCS_SERVER_SCRIPTS = os.path.join(DCS_SERVER, "Scripts")

CONFIG_PATH = os.path.join(DCS_DISCORD_BOT, "dcs_admin_bot_config.txt")
BANLIST_PATH = os.path.join(DCS_DISCORD_BOT, "banlist.txt")
PLAYER_LOG_PATH = os.path.join(DCS_DISCORD_BOT, "player_log.csv")
KICKQUEUE_PATH = os.path.join(DCS_DISCORD_BOT, "kickqueue.txt")
MISSIONQUEUE_PATH = os.path.join(DCS_DISCORD_BOT, "missionqueue.txt")
MISSIONCMD_PATH = os.path.join(DCS_DISCORD_BOT, "missioncmd.txt")
MISSIONLIST_PATH = os.path.join(DCS_DISCORD_BOT, "missionlist.txt")
MISSIONSTATUS_PATH = os.path.join(DCS_DISCORD_BOT, "missionstatus.txt")
MISSIONINFO_PATH = os.path.join(DCS_DISCORD_BOT, "missioninfo.txt")
FRIENDLYFIRE_PATH = os.path.join(DCS_DISCORD_BOT, "friendlyfire.txt")
DCS_CHAT_FILE = os.path.join(DCS_DISCORD_BOT, "chatcmd.txt")

DCS_SERVER_PATH = os.path.join(DCS_SERVER_BIN, "DCS_server.exe")
DCS_PROCESS_NAME = "DCS_server.exe"
SRC_SCRIPT_PATH = os.path.join(DCS_SCRIPTS, "MissionScripting.lua")
DST_SCRIPT_PATH = os.path.join(DCS_SERVER_SCRIPTS, "MissionScripting.lua")
FOOTHOLD_SAVES_DIR = os.path.join(DCS_MISSIONS, "Saves")

settings_path = os.path.join(DCS_CONFIG, "serverSettings.lua")

DCS_UPDATER_EXE = os.path.join(DCS_SERVER_BIN, "DCS_updater.exe")


SRS_SERVER = os.environ.get("SRS_SERVER")
SRS_SERVER_CFG = os.environ.get("SRS_SERVER_CFG")
SRS_PROCESS_NAME = "SR-Server.exe"   # The actual process name, adjust if needed

# -------------------------------------------

# ------------- ENVIRONMENT CONFIG ---------------
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN environment variable not set. Please set it before running the bot.")
GUILD_ID = int(os.environ.get("DISCORD_GUILD_ID", "0"))
if not GUILD_ID:
    raise RuntimeError("DISCORD_GUILD_ID environment variable not set. Please set it before running the bot.")
# -------------------------------------------

class ConfirmView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.confirmed = asyncio.Event()

    @ui.button(label="OK, start update", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.confirmed.set()
        self.stop()

class EndAckView(ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.acknowledged = asyncio.Event()

    @ui.button(label="OK", style=discord.ButtonStyle.primary)
    async def ack(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.acknowledged.set()
        self.stop()
        await interaction.channel.send("✅ **DCS server has been updated and is ready!**")

def any_real_players_connected_live():
    players = parse_player_list_from_info(MISSIONINFO_PATH)
    real_players = [
        name for name in players
        if "Server" not in name.lower() and name.strip() != ""
    ]
    return len(real_players) > 0, real_players

def send_dcs_chat_message(msg):
    try:
        with open(DCS_CHAT_FILE, "a", encoding="utf-8") as f:
            f.write(msg.strip() + "\n")
    except Exception as e:
        logging.error(f"Error writing to chatcmd.txt: {e}")

class UpdateOverrideView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.decision = asyncio.Event()
        self.force_update = False

    @ui.button(label="Force Update Now", style=discord.ButtonStyle.danger)
    async def force(self, interaction: discord.Interaction, button: ui.Button):
        self.force_update = True
        await interaction.response.send_message("⚠️ Update will proceed, players will be disconnected!", ephemeral=True)
        self.decision.set()
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Update cancelled.", ephemeral=True)
        self.decision.set()
        self.stop()

async def safe_run_updater_public(interaction: discord.Interaction):
    has_players, names = any_real_players_connected_live()
    if has_players:
        msg = "⚠️ Server admin is preparing to update the server. You may be disconnected in the next minutes!"
        send_dcs_chat_message(msg)
        view = UpdateOverrideView()
        names_str = ", ".join(names)
        await interaction.followup.send(
            f"🚫 Players currently connected: {names_str}\n\n"
            "Do you want to **force the update** (will kick/disconnect all players), or cancel?",
            view=view,
            ephemeral=True
        )
        await view.decision.wait()
        if not view.force_update:
            await interaction.followup.send("Update aborted by admin.", ephemeral=True)
            return
        send_dcs_chat_message("⚠️ Server update in progress! All players will be disconnected!")
        await interaction.followup.send("Proceeding with forced update...", ephemeral=True)
        await asyncio.sleep(5)
    else:
        await interaction.followup.send("No real players connected. Proceeding with update...", ephemeral=True)
        await asyncio.sleep(1)
    await run_updater_public_silent(interaction)

def launch_updater_without_uac(updater_path, dcs_path):
    env = os.environ.copy()
    env['__COMPAT_LAYER'] = 'RUNASINVOKER'
    return subprocess.Popen(
        [updater_path, "update"],
        cwd=dcs_path,
        env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

async def run_updater_public_silent(interaction: discord.Interaction):
    await interaction.followup.send("🔴 Killing DCS_server.exe...", ephemeral=True)
    killed = kill_dcs_server()
    if killed:
        await interaction.followup.send("🟠 DCS server killed. Running updater...", ephemeral=True)
    else:
        await interaction.followup.send("🟠 No DCS server process found. Running updater anyway...", ephemeral=True)

    await interaction.followup.send("🟡 Launching DCS_updater.exe update (silent mode)...", ephemeral=True)
    try:
        updater_proc = subprocess.Popen(
            [DCS_UPDATER_EXE, "update", "--quiet"],
            cwd=DCS_SERVER_BIN,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to start DCS_updater.exe: {e}")
        logging.error(f"Failed to start DCS_updater.exe: {e}")
        return

    await interaction.followup.send("🟡 DCS Updater is running. Progress messages will appear below.")
    while True:
        line = updater_proc.stdout.readline()
        if not line:
            break
        decoded_line = line.decode(errors="ignore").strip()
        if decoded_line:
            await interaction.followup.send(decoded_line)
    updater_proc.wait()
    result_msg = "🟢 DCS Updater finished." if updater_proc.returncode == 0 else f"🔴 DCS Updater failed (exit {updater_proc.returncode})."
    await interaction.followup.send(result_msg)

    if updater_proc.returncode == 0:
        await interaction.followup.send("✅ Update complete. Patching MissionScripting.lua and restarting DCS server...", ephemeral=True)
        try:
            success, msg = await asyncio.get_event_loop().run_in_executor(None, restart_dcs)
        except Exception as e:
            await interaction.followup.send(f"Failed to restart DCS after update: {e}")
            logging.error(f"Failed to restart DCS after update: {e}")
        else:
            if success:
                await interaction.followup.send("✅ DCS server restarted and running (MissionScripting.lua patched).")
            else:
                await interaction.followup.send(f"❌ Failed to restart DCS server after update: {msg}")
    else:
        await interaction.followup.send("⚠️ DCS server not restarted due to update failure.", ephemeral=True)

def pad(val, width):
    return str(val)[:width].ljust(width)

def list_foothold_lua_files(saves_folder):
    return [f for f in os.listdir(saves_folder) if f.endswith('.lua')]

def extract_player_stats(lua_text):
    start_key = "zonePersistance['playerStats'] ="
    start = lua_text.find(start_key)
    if start == -1:
        raise ValueError("Could not find zonePersistance['playerStats'] block.")
    lua_text = lua_text[start + len(start_key):]
    brace_count = 0
    block = ""
    in_block = False
    for char in lua_text:
        if char == '{':
            brace_count += 1
            in_block = True
        elif char == '}':
            brace_count -= 1
        block += char
        if in_block and brace_count == 0:
            break
    block = re.sub(r"\[\s*'([^']+)'\s*\]", r"'\1'", block)
    block = block.replace("=", ":").replace("nil", "None")
    return ast.literal_eval(block)

def process_stats(player_stats):
    air_keys = ['Air']
    ground_keys = ['Ground Units', 'SAM', 'Infantry']
    rows = []
    for player, stats in player_stats.items():
        row = {"Player": player}
        for stat in set(k for d in player_stats.values() for k in d):
            row[stat] = stats.get(stat, 0)
        row['Air Kills'] = sum(row.get(k, 0) for k in air_keys)
        row['Ground Kills'] = sum(row.get(k, 0) for k in ground_keys)
        row['Total Kills'] = row['Air Kills'] + row['Ground Kills']
        row['Profit'] = row.get('Points', 0) - row.get('Points spent', 0)
        row['K/D Ratio'] = round(row['Total Kills'] / row['Deaths'], 2) if row.get('Deaths', 0) > 0 else row['Total Kills']
        rows.append(row)
    return rows

def parse_server_settings_lua(settings_path):
    server_info = {"password": "?", "port": "?", "name": "?"}
    if not os.path.exists(settings_path):
        return server_info
    with open(settings_path, "r", encoding="utf-8") as f:
        content = f.read()
    pw = re.search(r'\["password"\]\s*=\s*"([^"]*)"', content)
    pt = re.search(r'\["port"\]\s*=\s*(\d+)', content)
    name = re.search(r'\["name"\]\s*=\s*"([^"]*)"', content)
    if pw: server_info["password"] = pw.group(1)
    if pt: server_info["port"] = pt.group(1)
    if name: server_info["name"] = name.group(1)
    return server_info

def load_config():
    roles, users = [], []
    upload_channel_id = os.environ.get("DISCORD_UPLOAD_CHANNEL_ID")
    ffire_alert_channel_id = os.environ.get("DISCORD_FFIRE_ALERT_CHANNEL_ID")
    startup_greeting_channel_id = os.environ.get("DISCORD_STARTUP_GREETING_CHANNEL_ID")
    status_update_channel_id = os.environ.get("DISCORD_STATUS_UPDATE_CHANNEL_ID")
    # --- NEW: Check for admin user IDs in env var ---
    admin_user_ids_env = os.environ.get("DISCORD_ADMIN_USER_IDS")
    if admin_user_ids_env:
        # Parse comma-separated list, ignore config file for users
        users = [int(uid.strip()) for uid in admin_user_ids_env.split(",") if uid.strip().isdigit()]
        use_users_from_env = True
    else:
        use_users_from_env = False
    # --- NEW: Check for admin role names in env var ---
    admin_role_names_env = os.environ.get("DISCORD_ADMIN_ROLE_NAMES")
    if admin_role_names_env:
        roles = [role.strip() for role in admin_role_names_env.split(",") if role.strip()]
        use_roles_from_env = True
    else:
        use_roles_from_env = False
    section = None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.lower() == "[roles]":
                section = "roles"
            elif line.lower() == "[users]":
                section = "users"
            elif line.lower() == "[upload_channel]":
                section = "upload_channel"
            elif line.lower() == "[ffire_alert_channel]":
                section = "ffire_alert_channel"
            elif line.lower() == "[startup_greeting_channel]":
                section = "startup_greeting_channel"
            elif line.lower() == "[status_update_channel]":
                section = "status_update_channel"
            elif line.startswith("[") and line.endswith("]"):
                section = None
            else:
                if section == "roles" and not use_roles_from_env:
                    roles.append(line)
                elif section == "users" and not use_users_from_env:
                    try:
                        users.append(int(line))
                    except Exception:
                        pass
                elif section == "upload_channel" and not upload_channel_id:
                    try:
                        upload_channel_id = int(line)
                    except Exception:
                        pass
                elif section == "ffire_alert_channel" and not ffire_alert_channel_id:
                    try:
                        ffire_alert_channel_id = int(line)
                    except Exception:
                        pass
                elif section == "startup_greeting_channel" and not startup_greeting_channel_id:
                    try:
                        startup_greeting_channel_id = int(line)
                    except Exception:
                        pass
                elif section == "status_update_channel" and not status_update_channel_id:
                    try:
                        status_update_channel_id = int(line)
                    except Exception:
                        pass
    # If env vars were set, ensure they are int
    if upload_channel_id: upload_channel_id = int(upload_channel_id)
    if ffire_alert_channel_id: ffire_alert_channel_id = int(ffire_alert_channel_id)
    if startup_greeting_channel_id: startup_greeting_channel_id = int(startup_greeting_channel_id)
    if status_update_channel_id: status_update_channel_id = int(status_update_channel_id)
    return roles, users, upload_channel_id, ffire_alert_channel_id, startup_greeting_channel_id, status_update_channel_id

ADMIN_ROLE_NAMES, ADMIN_USER_IDS, UPLOAD_CHANNEL_ID, FFIRE_ALERT_CHANNEL_ID, STARTUP_GREETING_CHANNEL_ID, STATUS_UPDATE_CHANNEL_ID = load_config()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def get_public_ip():
    try:
        return requests.get("https://api.ipify.org").text
    except Exception:
        return "?"

def user_is_admin(interaction):
    user_id = interaction.user.id
    if user_id in ADMIN_USER_IDS:
        return True
    roles = getattr(interaction.user, "roles", [])
    for role in roles:
        if role.name in ADMIN_ROLE_NAMES:
            return True
    if hasattr(interaction, "guild") and interaction.guild:
        member = interaction.guild.get_member(user_id)
        if member:
            for role in getattr(member, "roles", []):
                if role.name in ADMIN_ROLE_NAMES:
                    return True
    return False

def update_missionscripting():
    try:
        shutil.copy2(SRC_SCRIPT_PATH, DST_SCRIPT_PATH)
        logging.info("MissionScripting.lua updated.")
        return True, "✅ MissionScripting.lua has been updated!"
    except Exception as e:
        logging.error(f"Failed to update MissionScripting.lua: {e}")
        return False, f"❌ Failed to update MissionScripting.lua: {e}"
    
def wait_for_process_exit(process_name, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        if not any(p.info['name'] and p.info['name'].lower() == process_name.lower()
                   for p in psutil.process_iter(['name'])):
            return True
        time.sleep(2)
    return False

def wait_for_process_start(process_name, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        if any(p.info['name'] and p.info['name'].lower() == process_name.lower()
               for p in psutil.process_iter(['name'])):
            return True
        time.sleep(2)
    return False

def kill_dcs_server():
    killed = False
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == DCS_PROCESS_NAME.lower():
            try:
                logging.info(f"Killing {proc.info['name']} (PID {proc.info['pid']})")
                proc.kill()
                killed = True
            except Exception as e:
                logging.error(f"Failed to kill: {e}")
    return killed


def start_dcs_server(dcs_path):
    try:
        subprocess.Popen([dcs_path], cwd=os.path.dirname(dcs_path))
        logging.info(f"Started {dcs_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to start: {e}")
        return False

def restart_dcs():
    update_missionscripting()
    killed = kill_dcs_server()
    if killed:
        logging.info("Waiting for DCS to fully exit...")
        if not wait_for_process_exit(DCS_PROCESS_NAME, timeout=60):
            logging.error("DCS process did not exit after 60 seconds!")
            return False, "DCS process did not exit in time"
        logging.info("DCS process is gone, restarting.")
        time.sleep(3)
    else:
        logging.info("No DCS process found to kill, starting a new one.")

    started = start_dcs_server(DCS_SERVER_PATH)
    if not started:
        return False, "Failed to start DCS process"

    if wait_for_process_start(DCS_PROCESS_NAME, timeout=30):
        logging.info("DCS process is now running.")
        return True, "DCS restarted successfully"
    else:
        logging.error("DCS did not start within 30 seconds.")
        return False, "DCS did not start within 30 seconds"
    
def kill_srs_server():
    killed = False
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == SRS_PROCESS_NAME.lower():
            try:
                logging.info(f"Killing {proc.info['name']} (PID {proc.info['pid']})")
                proc.kill()
                killed = True
            except Exception as e:
                logging.error(f"Failed to kill SRS: {e}")
    return killed

def start_srs_server():
    if not SRS_SERVER or not os.path.exists(SRS_SERVER):
        logging.error("SRS_SERVER not set or invalid path.")
        return False
    # Build the command line with the config file if present
    srs_cfg = os.environ.get("SRS_SERVER_CFG")
    cmd = [SRS_SERVER]
    if srs_cfg and os.path.exists(srs_cfg):
        cmd.append(f'-cfg="{srs_cfg}"')
    try:
        # On Windows, launch with CREATE_NEW_CONSOLE to ensure a visible window
        if os.name == "nt":
            # creationflags=0x00000010 is CREATE_NEW_CONSOLE
            subprocess.Popen(cmd, cwd=os.path.dirname(SRS_SERVER), creationflags=0x00000010)
        else:
            subprocess.Popen(cmd, cwd=os.path.dirname(SRS_SERVER))
        logging.info(f"Started SRS at {SRS_SERVER} with config {srs_cfg}")
        return True
    except Exception as e:
        logging.error(f"Failed to start SRS: {e}")
        return False

def restart_srs():
    killed = kill_srs_server()
    if killed:
        logging.info("Waiting for SRS to fully exit...")
        if not wait_for_process_exit(SRS_PROCESS_NAME, timeout=30):
            logging.error("SRS did not exit after 30 seconds!")
            return False, "SRS process did not exit in time"
        time.sleep(2)
    else:
        logging.info("No SRS process found to kill, starting a new one.")
    started = start_srs_server()
    if not started:
        return False, "Failed to start SRS process"
    if wait_for_process_start(SRS_PROCESS_NAME, timeout=20):
        logging.info("SRS process is now running.")
        return True, "SRS restarted successfully"
    else:
        logging.error("SRS did not start within 20 seconds.")
        return False, "SRS did not start within 20 seconds"


def queue_mission_command(cmd):
    with open(MISSIONCMD_PATH, "w", encoding="utf-8") as f:
        f.write(cmd + "\n")

def read_mission_list():
    if not os.path.exists(MISSIONLIST_PATH):
        return []
    with open(MISSIONLIST_PATH, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def get_current_miz_from_info():
    if not os.path.exists(MISSIONINFO_PATH):
        return None
    with open(MISSIONINFO_PATH, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    for l in lines:
        if l.lower().startswith("mission name:"):
            return l.split(":",1)[1].strip()
    return None

def extract_description_from_miz(miz_path, desc_key):
    if not os.path.isfile(miz_path) or not desc_key:
        return ""
    try:
        with zipfile.ZipFile(miz_path, "r") as z:
            dict_path = "l10n/DEFAULT/dictionary"
            if dict_path in z.namelist():
                dictionary = z.read(dict_path).decode("utf-8", errors="replace")
                for line in dictionary.splitlines():
                    if line.startswith(desc_key):
                        return line.split('=',1)[-1].strip().strip('"')
    except Exception as e:
        logging.error(f"Description extraction error: {e}")
    return ""

def get_miz_metadata(miz_path):
    if not os.path.isfile(miz_path):
        return {}
    with zipfile.ZipFile(miz_path, "r") as z:
        if "mission" not in z.namelist():
            return {}
        mission_raw = z.read("mission").decode("utf-8", errors="replace")
        idx = mission_raw.find("mission = ")
        if idx != -1:
            mission_lua = mission_raw[idx + len("mission = "):]
        else:
            mission_lua = mission_raw
        try:
            if mission_lua.endswith(";"):
                mission_lua = mission_lua[:-1]
            if not mission_lua.strip().endswith("}"):
                mission_lua += "}"
            mission_data = lua.decode(mission_lua)
        except Exception as e:
            logging.error(f"Error decoding mission Lua: {e}")
            return {}
    meta = {}
    try:
        meta["Title"] = mission_data.get("title", os.path.basename(miz_path))
        desc = mission_data.get("descriptionText", "")
        if isinstance(desc, str) and desc.startswith("DictKey_"):
            desc = extract_description_from_miz(miz_path, desc)
        meta["Description"] = desc
        meta["Theater"] = mission_data.get("theatre", "")
        date = mission_data.get("date", "")
        if isinstance(date, dict):
            meta["Date"] = "{:04d}-{:02d}-{:02d}".format(
                date.get("Year", 0), date.get("Month", 0), date.get("Day", 0)
            )
        else:
            meta["Date"] = str(date)
        start_time = mission_data.get("start_time", "")
        try:
            t = int(float(start_time))
            h, m = divmod(t // 60, 60)
            s = t % 60
            meta["Start Time"] = "{:02d}:{:02d}:{:02d}".format(h, m, s)
        except Exception:
            meta["Start Time"] = str(start_time)
        weather = mission_data.get("weather", {})
        if weather:
            meta["Temperature"] = weather.get("temp", "")
            meta["QNH"] = weather.get("qnh", "")
            meta["Clouds"] = weather.get("name", "Clear")
            meta["Cloudbase"] = weather.get("clouds", {}).get("base", "")
            meta["Visibility"] = weather.get("visibility", {}).get("distance", "")
            wind = weather.get("wind", {})
            meta["Wind_Ground"] = wind.get("atGround", {})
            meta["Wind_2000"] = wind.get("at2000", {})
            meta["Wind_8000"] = wind.get("at8000", {})
        else:
            meta["Weather"] = "Unknown"
        def slot_count(coal):
            count = 0
            c = mission_data.get("coalition", {}).get(coal, {})
            for country in c.get("country", {}).values():
                for k, v in country.items():
                    if k in ["plane", "helicopter"] and isinstance(v, dict):
                        for group in v.get("group", {}).values():
                            count += len(group.get("units", []))
            return count
        meta["Slots_Blue"] = slot_count("blue")
        meta["Slots_Red"] = slot_count("red")
        meta["File"] = os.path.basename(miz_path)
    except Exception as e:
        logging.error(f"Error extracting fields: {e}")
    return meta

def parse_player_list_from_info(info_path):
    players = []
    if not os.path.exists(info_path):
        return players
    found = False
    with open(info_path, "r", encoding="utf-8") as f:
        for l in f:
            if l.strip() == "Players:":
                found = True
                continue
            if found:
                line = l.strip()
                if not line: break
                players.append(line)
    return players

def parse_banlist(path):
    bans = []
    if not os.path.exists(path):
        return bans
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",", 4)
            if len(parts) < 5:
                continue
            ucid, name, ban_start, period, reason = parts
            try:
                ban_start = int(ban_start)
                period = int(period)
            except ValueError:
                continue
            bans.append({
                "ucid": ucid,
                "name": name,
                "ban_start": ban_start,
                "period": period,
                "reason": reason,
            })
    return bans

def ban_time_left(ban):
    if ban["period"] == 0:
        return "Permanent"
    now = int(time.time())
    end = ban["ban_start"] + ban["period"]
    left = end - now
    if left < 0:
        return "Expired"
    h = left // 3600
    m = (left % 3600) // 60
    s = left % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

def format_banlist_embed(bans):
    embed = discord.Embed(title="DCS Banlist", color=0xE74C3C)
    if not bans:
        embed.description = "No active bans."
        return embed
    for b in bans:
        left = ban_time_left(b)
        embed.add_field(
            name=b["name"],
            value=(
                f"Reason: `{b['reason'] or 'No reason'}`\n"
                f"Time Left: `{left}`\n"
                f"UCID: `{b['ucid']}`"
            ),
            inline=False
        )
    return embed

def find_ucid_by_name(player_log_path, player_name):
    ucid = None
    if not os.path.exists(player_log_path):
        return None
    with open(player_log_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",", 4)
            if len(parts) < 4:
                continue
            name = parts[2]
            found_ucid = parts[3]
            if name and found_ucid and name.strip().lower() == player_name.strip().lower():
                ucid = found_ucid
    return ucid

def save_banlist(path, bans):
    with open(path, "w", encoding="utf-8") as f:
        for b in bans:
            line = "{},{},{},{},{}\n".format(
                b["ucid"], b["name"], b["ban_start"], b["period"], b["reason"]
            )
            f.write(line)

def add_ban(path, player_name, duration, reason, player_log_path):
    bans = parse_banlist(path)
    ucid = find_ucid_by_name(player_log_path, player_name)
    if not ucid:
        return None
    now = int(time.time())
    bans = [b for b in bans if b["ucid"] != ucid]
    bans.append({
        "ucid": ucid,
        "name": player_name,
        "ban_start": now,
        "period": duration,
        "reason": reason,
    })
    save_banlist(path, bans)
    return ucid

def remove_ban(path, player_name, player_log_path):
    bans = parse_banlist(path)
    ucid = find_ucid_by_name(player_log_path, player_name)
    if not ucid:
        return False
    pre_count = len(bans)
    bans = [b for b in bans if b["ucid"] != ucid]
    save_banlist(path, bans)
    return pre_count != len(bans)

def queue_kick(ucid):
    with open(KICKQUEUE_PATH, "a", encoding="utf-8") as f:
        f.write(ucid + "\n")

def get_recent_players(player_log_path, max_entries=15):
    if not os.path.exists(player_log_path):
        return []
    players = {}
    with open(player_log_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",", 8)
            if len(parts) < 5:
                continue
            date, _, name, ucid, ipaddr = parts[:5]
            key = (name.strip(), ucid.strip())
            players[key] = {"name": name.strip(), "ucid": ucid.strip(), "ipaddr": ipaddr.strip(), "last_time": date.strip()}
    players_list = sorted(players.values(), key=lambda x: x["last_time"], reverse=True)
    return players_list[:max_entries]

def get_all_connections(player_log_path, max_entries=20):
    if not os.path.exists(player_log_path):
        return []
    entries = []
    with open(player_log_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",", 10)
            if len(parts) < 9:
                continue
            date, _, name, ucid, ipaddr, _, _, _, event = parts[:9]
            event = event.strip().upper()
            if event and event != "CONNECT":
                continue
            entries.append({
                "date": date.strip(),
                "name": name.strip(),
                "ucid": ucid.strip(),
                "ipaddr": ipaddr.strip()
            })
    return entries[::-1][:max_entries]

def get_player_stats_from_log(name=None, ucid=None, log_path=PLAYER_LOG_PATH):
    import datetime
    stats = {
        "name": name or "?", "ucid": ucid or "?",
        "connections": 0, "kills": 0, "deaths": 0, "ejects": 0,
        "landings": 0, "crashes": 0,
        "first_seen": None, "last_seen": None, "ip": "?", "slots": set(), "sides": set()
    }
    if not os.path.exists(log_path):
        return stats
    with open(log_path, "r", encoding="utf-8") as f:
        lines = [l.strip().split(",") for l in f if l.strip()]
    for row in lines:
        if len(row) < 9:
            continue
        row_date, row_time, row_name, row_ucid, row_ip, row_side, row_slot, row_ping, row_event = row[:9]
        event = row_event.upper().strip()
        if (ucid and row_ucid == ucid) or (name and row_name.lower() == name.lower()):
            stats["name"] = row_name
            stats["ucid"] = row_ucid
            stats["ip"] = row_ip
            stats["slots"].add(row_slot or "N/A")
            stats["sides"].add(row_side or "N/A")
            try:
                dt = datetime.datetime.strptime(f"{row_date} {row_time}", "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = None
            if dt:
                if not stats["first_seen"] or dt < stats["first_seen"]:
                    stats["first_seen"] = dt
                if not stats["last_seen"] or dt > stats["last_seen"]:
                    stats["last_seen"] = dt
            if event == "CONNECT" or event == "":
                stats["connections"] += 1
            elif event == "KILL":
                stats["kills"] += 1
            elif event == "DEATH":
                stats["deaths"] += 1
            elif event == "EJECT":
                stats["ejects"] += 1
            elif event == "LAND":
                stats["landings"] += 1
            elif event == "CRASH":
                stats["crashes"] += 1
    stats["slots"] = ", ".join(sorted([s for s in stats["slots"] if s and s != "N/A"])) or "?"
    stats["sides"] = ", ".join(sorted([s for s in stats["sides"] if s and s != "N/A"])) or "?"
    return stats

async def friendly_fire_watcher():
    last_size = 0
    await client.wait_until_ready()
    channel = client.get_channel(FFIRE_ALERT_CHANNEL_ID)
    while not client.is_closed():
        if os.path.exists(FRIENDLYFIRE_PATH):
            size = os.path.getsize(FRIENDLYFIRE_PATH)
            if size > last_size:
                async with aiofiles.open(FRIENDLYFIRE_PATH, "r", encoding="utf-8") as f:
                    await f.seek(last_size)
                    lines = await f.readlines()
                for line in lines:
                    m = re.match(r"\[.*?\] EVENT:(\w+) OFFENDER:(.*?)\|(.*?) VICTIM:(.*?)\|(.*?)$", line)
                    if m:
                        event_type, offender, offender_ucid, victim, victim_ucid = m.groups()
                        msg = (
                            f":rotating_light: **FRIENDLY FIRE WARNING** :rotating_light:\n"
                            f"**{offender}** (`{offender_ucid}`) killed teammate **{victim}** (`{victim_ucid}`)\n"
                            f"Event type: `{event_type}`"
                        )
                        if channel:
                            await channel.send(msg)
                last_size = size
        await asyncio.sleep(5)

async def player_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    players = get_recent_players(PLAYER_LOG_PATH, max_entries=50)
    names = sorted(set(p['name'] for p in players if p['name'].lower() != 'server'))
    return [
        app_commands.Choice(name=name, value=name)
        for name in names if current.lower() in name.lower()
    ][:25]

async def banned_player_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    bans = parse_banlist(BANLIST_PATH)
    names = sorted(set(b['name'] for b in bans if b['name'].lower() != 'server'))
    return [
        app_commands.Choice(name=name, value=name)
        for name in names if current.lower() in name.lower()
    ][:25]

async def foothold_lua_file_autocomplete(interaction: discord.Interaction, current: str):
    files = list_foothold_lua_files(FOOTHOLD_SAVES_DIR)
    return [
        Choice(name=f, value=f)
        for f in files if current.lower() in f.lower()
    ][:20]

async def send_live_status_update():
    server_settings = parse_server_settings_lua(str(settings_path))
    await client.wait_until_ready()
    channel_id = STATUS_UPDATE_CHANNEL_ID
    channel = client.get_channel(channel_id)
    if not channel:
        logging.error("Live status update channel not found.")
        return
    message = None
    while not client.is_closed():
        miz_path = get_current_miz_from_info()
        meta = get_miz_metadata(miz_path) if miz_path else {}

        players_connected = []
        if os.path.exists(MISSIONINFO_PATH):
            with open(MISSIONINFO_PATH, "r", encoding="utf-8") as f:
                add_players = False
                for line in f:
                    if line.lower().startswith("players:"):
                        add_players = True
                        continue
                    if add_players and line.strip():
                        parts = line.strip().rsplit("[", 1)
                        if len(parts) == 2:
                            name = parts[0].strip()
                            ucid = parts[1].replace("]", "").strip()
                            players_connected.append({"name": name, "ucid": ucid})
                        else:
                            players_connected.append({"name": line.strip(), "ucid": ""})
                    elif add_players and not line.strip():
                        break

        embed = build_rich_status_embed(meta, players_connected, server_settings, show_password=False)
        try:
            if not message:
                message = await channel.send(embed=embed)
            else:
                await message.edit(embed=embed)
        except Exception as e:
            logging.error(f"Error updating status message: {e}")
            message = None
        await asyncio.sleep(3600)

def format_wind(w):
    if not isinstance(w, dict): return "?"
    d = w.get("dir", "?")
    s = w.get("speed", "?")
    return f"{d}° / {s} kts"

def build_rich_status_embed(meta, players_connected, server_settings, show_password=False):
    server_settings = parse_server_settings_lua(str(settings_path))
    server_ip = get_public_ip()
    embed = discord.Embed(
        title=server_settings['name'],
        color=0x3498db,
        description=f"**Mission:** {meta.get('Title','?')}\n"
                    f"{meta.get('Description','')}",
    )
    embed.add_field(name="Map", value=meta.get("Theater","?"), inline=True)
    embed.add_field(name="Server-IP / Port", value=f"{server_ip}:{server_settings['port']}", inline=True)
    embed.add_field(name="Date/Time in Mission", value=f"{meta.get('Date','?')} {meta.get('Start Time','?')}", inline=True)
    embed.add_field(name="Slots (Blue | Red)", value=f"{meta.get('Slots_Blue','?')} | {meta.get('Slots_Red','?')}", inline=True)
    embed.add_field(name="Temperature", value=f"{meta.get('Temperature','?')} °C", inline=True)
    embed.add_field(name="QNH", value=f"{meta.get('QNH','?')} hPa", inline=True)
    embed.add_field(name="Clouds", value=meta.get("Clouds","?"), inline=True)
    embed.add_field(name="Cloudbase", value=f"{meta.get('Cloudbase','?')} ft", inline=True)
    v = meta.get('Visibility')
    vis_km = f"{int(v)//1000} km" if v and str(v).isdigit() else "?"
    embed.add_field(name="Visibility", value=vis_km, inline=True)
    embed.add_field(name="Wind (Ground)", value=format_wind(meta.get("Wind_Ground")), inline=True)
    embed.add_field(name="Wind (6600ft)", value=format_wind(meta.get("Wind_2000")), inline=True)
    embed.add_field(name="Wind (26000ft)", value=format_wind(meta.get("Wind_8000")), inline=True)
    embed.add_field(name="Players Connected", value=str(len(players_connected)), inline=True)
    password = server_settings.get("password", "🔒")
    if show_password:
        embed.add_field(name="Password", value=password, inline=True)
    else:
        embed.add_field(name="Password", value="🔒 (admin only)", inline=True)
    if players_connected:
        plist = "\n".join(f"{p['name']} [{p['ucid']}]" for p in players_connected)
    else:
        plist = "No players"
    embed.add_field(name="Player List (Name [UCID])", value=plist, inline=False)
    return embed

# ========== SLASH COMMANDS =============

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user} (ID: {client.user.id})')
    try:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        logging.info("Slash commands synced.")
    except Exception as e:
        logging.error(f"Error syncing slash commands: {e}")
    client.loop.create_task(send_live_status_update())
    client.loop.create_task(friendly_fire_watcher())

    channel_id = STARTUP_GREETING_CHANNEL_ID
    channel = client.get_channel(channel_id)
    if channel:
        try:
            greeting = f":satellite: **DCS Admin Bot** started!\nServer: `{client.user}`"
            queue_mission_command("missioninfo")
            await asyncio.sleep(2)
            await channel.send(greeting)
        except Exception as e:
            await channel.send(f":warning: Bot started but error loading mission status: {e}")
            logging.error(f"Bot started but error loading mission status: {e}")
            
@tree.command(name="help", description="Show all DCS bot commands", guild=discord.Object(id=GUILD_ID))
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="DCS Admin Bot – Slash Commands",
        description="All commands. 🔒 = Admin only.",
        color=0x5865f2
    )
    embed.add_field(
        name="Missions",
        value=(
            "`/uploadmission`           🔒 (attach .miz in upload-missions channel)\n"
            "`/listmissions`\n"
            "`/loadmission number`      🔒\n"
            "`/missioninfo`\n"
        ),
        inline=False
    )
    embed.add_field(
        name="Server(missions)",
        value=(
            "`/pause`	                🔒 Pause mission\n"
            "`/unpause`	                🔒 Unpause mission\n"
            "`/restartmission`          🔒 Restart mission\n"
            "`/status`                  Show live server and player status now\n"
        ),
        inline=False
    )
    embed.add_field(
        name="Server(DCS process, file)",
        value=(
            "`/restart_dcs_server`	    🔒 Restart DCS sever (Update Missionscripting.lua)\n"
            "`/dcsupdate`	            🔒 Update DCS server\n"
            "`/update_missionscripting`	🔒 Update Missionscripting.lua\n"
            "`/restart_srs`             🔒 restart SRS server\n"
        ),
        inline=False
    )
    embed.add_field(
        name="Players & Bans",
        value=(
            "`/footholdstats`\n"
            "`/playerstats`\n"
            "`/dcsplayers`\n"
            "`/dcsconnections`\n"
            "`/dcsbanlist`\n"
            "`/dcsban player duration reason` 🔒 (permanent: duration = 0)\n"
            "`/dcsunban player`          🔒\n"
        ),
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(
    name="uploadmission", 
    description="Upload a new .miz mission file (admin only)", 
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    mizfile="Attach a .miz mission file"
)
async def uploadmission(
    interaction: discord.Interaction,
    mizfile: discord.Attachment
):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    if interaction.channel_id != UPLOAD_CHANNEL_ID:
        await interaction.response.send_message("Please use this command in the designated upload channel.", ephemeral=True)
        return
    if not mizfile.filename.lower().endswith('.miz'):
        await interaction.response.send_message("You must attach a `.miz` file.", ephemeral=True)
        return
    save_path = os.path.join(DCS_MISSIONS, mizfile.filename)
    await mizfile.save(save_path)
    await interaction.response.send_message(f"Mission `{mizfile.filename}` uploaded and added!")
    with open(MISSIONQUEUE_PATH, "a", encoding="utf-8") as f:
        f.write(mizfile.filename + "\n")
    queue_mission_command("listmissions")

@tree.command(name="listmissions", description="Show all missions", guild=discord.Object(id=GUILD_ID))
async def listmissions(interaction: discord.Interaction):
    queue_mission_command("listmissions")
    await asyncio.sleep(2)
    missions = read_mission_list()
    if not missions:
        await interaction.response.send_message("No missions found.", ephemeral=True)
        return
    embed = discord.Embed(title="DCS Server Missions", color=0x9b59b6)
    for line in missions:
        idx, rest = line.split(":", 1)
        embed.add_field(name=f"#{idx}", value=rest, inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="loadmission", description="Load a mission by number (see /listmissions)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(number="Mission number to load")
async def loadmission(interaction: discord.Interaction, number: int):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    queue_mission_command(f"loadmission:{number}")
    await interaction.response.send_message(f"Requested loading mission #{number}...")

@tree.command(name="missioninfo", description="Show the current mission status", guild=discord.Object(id=GUILD_ID))
async def missioninfo(interaction: discord.Interaction):
    await interaction.response.defer()
    queue_mission_command("missioninfo")
    await asyncio.sleep(2)
    meta = {}
    miz_path = get_current_miz_from_info()
    if miz_path and os.path.isfile(miz_path):
        meta = get_miz_metadata(miz_path)
    mission_time = None
    players_connected = None
    if os.path.exists(MISSIONINFO_PATH):
        with open(MISSIONINFO_PATH, "r", encoding="utf-8") as f:
            for l in f:
                if l.lower().startswith("mission time:"):
                    mission_time = l.split(":",1)[1].strip()
                if l.lower().startswith("players connected:"):
                    players_connected = l.split(":",1)[1].strip()
    embed = discord.Embed(title="DCS Server Status", color=0x27ae60)
    if meta.get("Title"):       embed.add_field(name="Mission Title", value=meta["Title"], inline=False)
    if meta.get("Description") and meta["Description"].strip():
        embed.add_field(name="Description", value=meta["Description"], inline=False)
    if meta.get("Date"):        embed.add_field(name="Mission Date", value=meta["Date"], inline=True)
    if meta.get("Start Time"):  embed.add_field(name="Start Time", value=meta["Start Time"], inline=True)
    if meta.get("Theater"):     embed.add_field(name="Map", value=meta["Theater"], inline=True)
    if meta.get("Weather"):     embed.add_field(name="Weather", value=meta["Weather"], inline=True)
    if mission_time:            embed.add_field(name="Mission Time", value=mission_time, inline=True)
    if players_connected:       embed.add_field(name="Players Connected", value=players_connected, inline=True)
    players = parse_player_list_from_info(MISSIONINFO_PATH)
    if players:
        embed.add_field(name="Players (Name [UCID])", value="\n".join(players), inline=False)
    if not meta: embed.description = "No mission info found."
    await interaction.followup.send(embed=embed)

@tree.command(name="dcsbanlist", description="Show current banlist", guild=discord.Object(id=GUILD_ID))
async def dcsbanlist(interaction: discord.Interaction):
    bans = parse_banlist(BANLIST_PATH)
    now = int(time.time())
    bans = [b for b in bans if b["period"] == 0 or (b["ban_start"] + b["period"] > now)]
    embed = format_banlist_embed(bans)
    await interaction.response.send_message(embed=embed)

@tree.command(name="dcsban", description="Ban a player (admin only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(player="Player name (as in log)", duration="Duration in seconds (0=perm)", reason="Ban reason (optional)")
@app_commands.autocomplete(player=player_autocomplete)
async def dcsban(interaction: discord.Interaction, player: str, duration: int = 0, reason: str = ""):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    ucid = add_ban(BANLIST_PATH, player, duration, reason, PLAYER_LOG_PATH)
    if not ucid:
        await interaction.response.send_message(f"Player `{player}` not found in log. They must have joined at least once.", ephemeral=True)
        return
    queue_kick(ucid)
    await interaction.response.send_message(
        f":no_entry: **{player}** banned for {ban_time_left({'period': duration, 'ban_start': int(time.time())})}.\nReason: `{reason or 'No reason'}`\nUCID: `{ucid}`"
    )

@tree.command(name="dcsunban", description="Unban a player (admin only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(player="Player name (as in banlist)")
@app_commands.autocomplete(player=banned_player_autocomplete)
async def dcsunban(interaction: discord.Interaction, player: str):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    ok = remove_ban(BANLIST_PATH, player, PLAYER_LOG_PATH)
    if ok:
        await interaction.response.send_message(f":white_check_mark: **{player}** has been unbanned.")
    else:
        await interaction.response.send_message(f":warning: No ban found for **{player}**.")

@tree.command(name="dcsplayers", description="Show recent unique players", guild=discord.Object(id=GUILD_ID))
async def dcsplayers(interaction: discord.Interaction):
    players = get_recent_players(PLAYER_LOG_PATH)
    # Exclude the server "player" (case-insensitive)
    filtered = [p for p in players if p['name'].strip().lower() != "server" and p['ucid'].strip().lower() != "ucid"]
    if not filtered:
        await interaction.response.send_message("No player log data found.", ephemeral=True)
        return
    embed = discord.Embed(title="DCS Connection History (recent unique players)", color=0x3498DB)
    for p in filtered:
        embed.add_field(
            name=f"{p['name']} ({p['ucid']})",
            value=f"Last: `{p['last_time']}`\nIP: `{p['ipaddr']}`",
            inline=False
        )
    await interaction.response.send_message(embed=embed)


    
@tree.command(name="dcsconnections", description="Show last 20 player connections", guild=discord.Object(id=GUILD_ID))
async def dcsconnections(interaction: discord.Interaction):
    connections = get_all_connections(PLAYER_LOG_PATH, max_entries=40)  # Grab more, we'll filter
    # Exclude any player where name is "server" (case-insensitive)
    filtered = [c for c in connections if c['name'].strip().lower() != "server" ]
    # Now only show last 20 real players
    filtered = filtered[:20]
    if not filtered:
        await interaction.response.send_message("No connection data found in log.", ephemeral=True)
        return
    embed = discord.Embed(title="DCS Player Connection Log (last 20)", color=0x2ECC71)
    for c in filtered:
        embed.add_field(
            name=f"{c['name']} ({c['ucid']})",
            value=f"Time: `{c['date']}`\nIP: `{c['ipaddr']}`",
            inline=False
        )
    await interaction.response.send_message(embed=embed)
    
@tree.command(name="pause", description="Pause the DCS mission", guild=discord.Object(id=GUILD_ID))
async def pause_cmd(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    queue_mission_command("pause")
    await interaction.response.send_message(":pause_button: Server pause requested.")

@tree.command(name="unpause", description="Unpause the DCS mission", guild=discord.Object(id=GUILD_ID))
async def unpause_cmd(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    queue_mission_command("unpause")
    await interaction.response.send_message(":arrow_forward: Server unpause requested.")



@tree.command(name="restartmission", description="Restart the current DCS mission", guild=discord.Object(id=GUILD_ID))
async def restartmission_cmd(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    queue_mission_command("restart")
    await interaction.response.send_message(":repeat: Server restart requested.")
    


@tree.command(name="restart_dcs_server", description="Restart the DCS server process", guild=discord.Object(id=GUILD_ID))
async def restartdcs_cmd(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    await interaction.response.send_message("Restarting DCS server process (updating script, then restarting)...", ephemeral=True)
    # Try to update script and always notify
    ok, update_msg = update_missionscripting()
    await interaction.followup.send(update_msg)
    # Now restart DCS regardless of update success
    try:
        success, msg = await asyncio.get_event_loop().run_in_executor(None, restart_dcs)
    except Exception as e:
        await interaction.followup.send(f"Failed to restart DCS: {e}")
    else:
        if success:
            await interaction.followup.send("✅ DCS server restarted and running.")
        else:
            await interaction.followup.send(f"❌ Failed to restart DCS server: {msg}")



@tree.command(name="update_missionscripting", description="Overwrite DCS MissionScripting.lua from Saved Games", guild=discord.Object(id=GUILD_ID))
async def update_missionscripting_cmd(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    ok, msg = update_missionscripting()
    await interaction.response.send_message(msg, ephemeral=True)

@tree.command(name="status", description="Show live server and player status now", guild=discord.Object(id=GUILD_ID))
async def status_cmd(interaction: discord.Interaction):
    await interaction.response.defer()

    # Get current mission meta
    miz_path = get_current_miz_from_info()
    meta = get_miz_metadata(miz_path) if miz_path else {}

    # Parse connected players from mission info or your player log
    players_connected = []
    if os.path.exists(MISSIONINFO_PATH):
        with open(MISSIONINFO_PATH, "r", encoding="utf-8") as f:
            add_players = False
            for line in f:
                if line.lower().startswith("players:"):
                    add_players = True
                    continue
                if add_players and line.strip():
                    parts = line.strip().rsplit("[", 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        ucid = parts[1].replace("]", "").strip()
                        players_connected.append({"name": name, "ucid": ucid})
                    else:
                        players_connected.append({"name": line.strip(), "ucid": ""})
                elif add_players and not line.strip():
                    break

    # Get server settings (path as appropriate for your setup)
    #settings_path = BASE_DIR / "Config" / "serverSettings.lua"
    server_settings = parse_server_settings_lua(str(settings_path))

    # Only show password if user is admin
    show_password = user_is_admin(interaction)

    embed = build_rich_status_embed(meta, players_connected, server_settings, show_password)
    await interaction.followup.send(embed=embed)


@tree.command(name="footholdstats", description="Show player stats from a Foothold save file", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(filename="Select a foothold LUA save file", private="Show results only to you (default: no)")
@app_commands.autocomplete(filename=foothold_lua_file_autocomplete)
async def footholdstats(interaction: discord.Interaction, filename: str, private: bool = False):
    try:
        filepath = os.path.join(FOOTHOLD_SAVES_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            lua_text = f.read()
        player_stats = extract_player_stats(lua_text)
        stats_rows = process_stats(player_stats)
        header = ["Player", "Air", "Ground", "Tot", "Deaths", "K/D", "Points", "Profit"]
        widths = [25, 5, 7, 5, 7, 7, 8, 9]  # Adjust widths as needed
        msg = "Foothold Player Stats:\n"
        msg += " ".join(pad(h, w) for h, w in zip(header, widths)) + "\n"
        msg += "-" * sum(widths) + "\n"

        for row in stats_rows:
            vals = [
                pad(row.get("Player", ""), widths[0]),
                pad(row.get("Air Kills", ""), widths[1]),
                pad(row.get("Ground Kills", ""), widths[2]),
                pad(row.get("Total Kills", ""), widths[3]),
                pad(row.get("Deaths", ""), widths[4]),
                pad(row.get("K/D Ratio", ""), widths[5]),
                pad(row.get("Points", ""), widths[6]),
                pad(row.get("Profit", ""), widths[7]),
            ]
            msg += " ".join(vals) + "\n"

        # Send as a message or as a file if too large
        if len(msg) < 1900:
            await interaction.response.send_message(f"```{msg}```", ephemeral=private)
        else:
            from io import StringIO
            import discord
            file = discord.File(fp=StringIO(msg), filename="foothold_stats.txt")
            await interaction.response.send_message("Table is too large for Discord. See attached file.", file=file, ephemeral=private)

    except Exception as e:
        await interaction.response.send_message(f"Error parsing stats: {e}", ephemeral=True)


@tree.command(name="playerstats", description="Get stats for a player", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(player="Player name (as shown in log)")
@app_commands.autocomplete(player=player_autocomplete)
async def playerstats_cmd(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    stats = get_player_stats_from_log(name=player)
    embed = discord.Embed(
        title=f"Player Stats: {stats['name']}",
        color=0x6e5494
    )
    embed.add_field(name="UCID", value=stats["ucid"], inline=False)
    embed.add_field(name="Total Connections", value=str(stats["connections"]), inline=True)
    embed.add_field(name="Kills", value=str(stats["kills"]), inline=True)
    embed.add_field(name="Deaths", value=str(stats["deaths"]), inline=True)
    embed.add_field(name="Ejections", value=str(stats["ejects"]), inline=True)
    embed.add_field(name="Landings", value=str(stats["landings"]), inline=True)
    embed.add_field(name="Crashes", value=str(stats["crashes"]), inline=True)
    embed.add_field(name="First Seen", value=str(stats["first_seen"]) if stats["first_seen"] else "?", inline=True)
    embed.add_field(name="Last Seen", value=str(stats["last_seen"]) if stats["last_seen"] else "?", inline=True)
    embed.add_field(name="Last Known IP", value=stats.get("ip", "?"), inline=True)
    embed.add_field(name="Slots Used", value=stats.get("slots", "?"), inline=True)
    embed.add_field(name="Sides Joined", value=stats.get("sides", "?"), inline=True)
    await interaction.followup.send(embed=embed)

@tree.command(
    name="dcsupdate",
    description="Kill DCS_server.exe, launch DCS_updater.exe update (with confirmation)",
    guild=discord.Object(id=GUILD_ID)
)
async def dcsupdate(interaction: discord.Interaction):
    # Step 1: Private confirmation for the command initiator only
    view = ConfirmView()
    await interaction.response.send_message(
        "**DCS Update Requested!**\n"
        "This will stop the DCS server and launch the updater.\n"
        "Click OK to continue.",
        view=view,
        ephemeral=True
    )
    try:
        await asyncio.wait_for(view.confirmed.wait(), timeout=120)
    except asyncio.TimeoutError:
        await interaction.followup.send("Update cancelled (no confirmation).", ephemeral=True)
        return

    # Step 2: Run update, progress/status messages are PUBLIC
    await safe_run_updater_public(interaction)

    # Step 3: Private final acknowledgment
    end_view = EndAckView()
    await interaction.followup.send(
        "Update complete. Click OK to acknowledge (only visible to you).",
        view=end_view,
        ephemeral=True
    )
    try:
        await asyncio.wait_for(end_view.acknowledged.wait(), timeout=300)
    except asyncio.TimeoutError:
        await interaction.followup.send("Update acknowledgement timed out.", ephemeral=True)
        
@tree.command(name="restart_srs", description="Restart the SRS (SimpleRadio Standalone) server", guild=discord.Object(id=GUILD_ID))
async def restart_srs_cmd(interaction: discord.Interaction):
    if not user_is_admin(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    await interaction.response.send_message("Restarting SRS server process...", ephemeral=True)
    try:
        success, msg = await asyncio.get_event_loop().run_in_executor(None, restart_srs)
    except Exception as e:
        await interaction.followup.send(f"Failed to restart SRS: {e}")
        logging.error(f"Failed to restart SRS: {e}")
    else:
        if success:
            await interaction.followup.send("✅ SRS server restarted and running.")
        else:
            await interaction.followup.send(f"❌ Failed to restart SRS server: {msg}")


# ------------- RUN THE BOT --------------
client.run(TOKEN)