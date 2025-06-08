# 🛡️ DCS Admin Bot

A full-featured **Discord-based administration bot** and **in-game command monitor** for **DCS World Dedicated Server**. This system links your DCS server with Discord and in-game chat, allowing powerful remote control, player moderation, logging, and mission management.

---

## 🔧 Requirements

### ✅ System Requirements

- Windows-based DCS Dedicated Server
- Python 3.10+ (if using python version)
- Discord account with server management rights
- [DCS SimpleRadio Standalone (SRS)](https://github.com/ciribob/DCS-SimpleRadioStandalone) (optional)

### 📦 Python Dependencies

Install via:

```bash
pip install -r requirements.txt
```

---

## 🤖 Discord Bot Setup

1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and add a bot
3. Enable intents under the **Bot** tab:
   - Message Content Intent
   - Server Members Intent
4. Under **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Manage Messages`, `Use Slash Commands`
5. Invite the bot to your server using the generated URL
6. Copy the bot token and your server (guild) ID

---

## ⚙️ Configuration

### Files Installation

1. Unzip the last released it should contain 2 folders
   -  Hooks , ensure discord_admin_allinone_hook.lua is in Hooks folder
   -  Discord_Admin_Bot folder , where you will found DCSAdminBot.exe and run_dcs_bot.ps1 (those script should work in any place on your server but recommended to keep everything inside this folder where all files and logs will be created/updated)
2. copy all folder into your C:\Users\<user>\Saved Games\DCS\Scripts
3. set up all you env. variables

### 🔐 Environment Variables

Set the following (in the run_dcs_bot.ps1):

```powershell
   Set Discord Server, Bot, Channels
$env:DISCORD_BOT_TOKEN = "your_token_here"
$env:DISCORD_GUILD_ID = "your_guild_id"

   Set channel IDs
$env:DISCORD_UPLOAD_CHANNEL_ID = "123456789012345678"  # <-- Replace with your upload channel ID
$env:DISCORD_FFIRE_ALERT_CHANNEL_ID = "123456789012345678"  # <-- Replace with your Friendly Fire Alert channel ID
$env:DISCORD_STARTUP_GREETING_CHANNEL_ID = "123456789012345678"  # <-- Replace with your startup greeting channel ID
$env:DISCORD_STATUS_UPDATE_CHANNEL_ID = "123456789012345678"  # <-- Replace with your status update channel ID

   Set DCS, SRS path
$env:DCS_SERVER = "C:\Path\To\DCS-Server"
$env:DCS_SAVED_GAMES = "C:\Users\<user>\Saved Games\DCS"
$env:SRS_SERVER = "C:\Path\To\SR-Server.exe"
$env:SRS_SERVER_CFG = "C:\Path\To\SRS.cfg"

   set Path to exe
Start-Process -FilePath "C:\Users\<user>\Saved Games\DCS\Scripts\Discord_Admin_Bot\DCSAdminBot.exe" -NoNewWindow -Wait
```

---

### 📁 Folder Structure

- `Scripts\Discord_Admin_Bot\` –  text command files, & Logs
- `Scripts\Hooks\` - Lua hook
- `Missions\` – Mission files and save folders (foothold)
- `Config\serverSettings.lua` – Server config file

---

## 🚀 Launching

### PowerShell

You can use the template script:

```powershell
.\run_dcs_bot.ps1
```

This script sets up environment variables and runs the bot in the background (no window pop-up if configured via Task Scheduler).

---


## 🗓️ Run on Startup via Task Scheduler

To launch the bot automatically when the server starts:

### 🧾 Steps

1. Open **Task Scheduler** (`taskschd.msc`)
2. Click **Create Task**
3. Under **General** tab:
   - Name: `DCS Admin Bot`
   - Select **Run whether user is logged on or not**
   - Check **Run with highest privileges**
4. Under **Triggers** tab:
   - Click **New**
   - Begin the task: `At startup`
   - Click **OK**
5. Under **Actions** tab:
   - Click **New**
   - Action: `Start a program`
   - Program/script: `powershell.exe`
   - Add arguments (replace path as needed):

     ```text
     -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\Users\USERNAME\Saved Games\DCS.dcs_serverrelease\run_dcs_bot.ps1"
     ```

6. Click **OK**, enter Server Admin credentials when prompted.

### ✅ Notes

- Make sure `run_dcs_bot.ps1` is present at the specified path.
- The script will run silently without opening a PowerShell window.
- You can confirm operation via `dcs_admin_bot.log` or the bot’s presence in Discord.


## 💬 Available Commands

### 🎮 In-Game Chat Commands (for Admins)

Use in the in-game chat (coalition or global):

| Command | Description |
|--------|-------------|
| `!addadmin [PlayerName]` | Promote a connected player to admin |
| `!removeadmin [PlayerName]` | Remove admin rights from a connected player |
| `!ban [PlayerName] duration reason` | Ban player (duration in seconds, `0` = permanent) |
| `!unban [PlayerName]` | Remove a player from banlist |
| `!pause` / `!unpause` | Pause/unpause the mission |

### ✅ Notes
   you can create this file in Discord_Admin_Bot folder manually and add UCID of player to give admin right and use in-game command or use !addadmin command: admin_ucids.txt

---

### 🛰️ Discord Slash Commands

Use Discord slash commands for bot control. Admin-only commands are restricted via role/user ID config.

#### Mission Control

- `/uploadmission` 📤 Upload a `.miz` file to server (requires upload channel)
- `/listmissions` 📜 List missions on server
- `/loadmission number` 🔄 Load mission by number
- `/missioninfo` ℹ️ Show current mission status

#### Server Control

- `/pause` ⏸️ Pause mission
- `/unpause` ▶️ Unpause mission
- `/restartmission` 🔁 Restart current mission
- `/restart_dcs_server` 🛠️ Kill & restart DCS Server
- `/dcsupdate` ⬆️ Update DCS via DCS_updater.exe (it should bypass UAC prompt and launch silent update, also MissionScripting.lua)
- `/update_missionscripting` 📂 Update `MissionScripting.lua` (it try to found MissionScripting.lua (must be desanitized) in Saved     Game\Scripts and copy to Server installation Scripts folder)
- `/restart_srs` 🔊 Restart SRS server

#### Players & Logs

- `/dcsplayers` 🧑‍✈️ Recent unique players
- `/dcsconnections` 🔌 Show recent player connections
- `/dcsban player duration reason` 🚫 Ban a player
- `/dcsunban player` ✅ Unban a player
- `/dcsbanlist` 📋 View active banlist
- `/playerstats` 📈 Detailed player session stats
- `/footholdstats` 🪖 Extract killboard stats from Foothold save

#### Status & Help

- `/status` 📡 Live server & mission status
- `/help` 📘 List all bot commands

---

## 📁 Files Generated

The bot uses and maintains the following files:

| File | Purpose |
|------|---------|
| `player_log.csv` | Logs player joins/leaves and events |
| `banlist.txt` | Persistent bans |
| `kickqueue.txt` | Temporary kicks (via Discord) |
| `chatcmd.txt` | Queue for in-game bot chat messages |
| `missioncmd.txt` | Discord → DCS command channel |
| `missioninfo.txt`, `missionstatus.txt`, `missionlist.txt` | Status and mission details |
| `friendlyfire.txt` | Friendly fire log |

---

## 📊 Foothold Integration

If you use the [Foothold Campaign](https://github.com/Dzsek/Foothold), you can run `/footholdstats` to generate a leaderboard from any `.lua` save file in the `Missions/Saves` directory.

---

## 🧪 Advanced Features

- Friendly fire watcher with Discord alerts (not tested)
- Auto-update mission list (it does NOT update serverSettings so list is not persitente after restart of DCS)
- UCID-based player management
- Supports both role-based and user ID-based admin permission checks
- DCS server auto-restart on update (possible bug)