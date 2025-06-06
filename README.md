# 🛡️ DCS Admin Bot

A Discord-based administration bot for **DCS World Dedicated Server**.

## 📦 Features

- Upload and load missions from Discord
- Live player stats and killboard from Foothold
- Ban and kick players via Discord slash commands
- Update DCS server remotely
- Realtime server status and alerts
- Logs and stats parsed from Saved Games

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Discord Setup

#### Create a Discord Bot
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and name your bot
3. Navigate to the "Bot" tab and click "Add Bot"
4. Under Privileged Gateway Intents, enable:
   - Server Members Intent
   - Message Content Intent
5. Copy your bot token (you'll need this later)

#### Add Bot to Your Server
1. Go to the "OAuth2" → "URL Generator" tab
2. Select scopes: `bot` and `applications.commands`
3. Select bot permissions:
   - Send Messages
   - Manage Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions
   - Use Slash Commands
4. Copy the generated URL and open it in your browser
5. Select your Discord server to add the bot

### 3. Environment Configuration

The bot requires these environment variables:

```pwsh
# Set environment variables in PowerShell
$env:DISCORD_BOT_TOKEN = "your_bot_token_here"
$env:DISCORD_GUILD_ID = "your_guild_id_here"
```

To get your Guild ID:
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click on your server name and select "Copy ID"

### 4. Configuration File

Create or update `Local/Discord_Admin_Bot/dcs_admin_bot_config.txt` with the following format:

```
ADMIN_ROLE_NAMES=DCS Admin,Server Admin,Moderator
ADMIN_USER_IDS=1234567890,0987654321
UPLOAD_CHANNEL_ID=1234567890123456789
FFIRE_ALERT_CHANNEL_ID=1234567890123456789
STARTUP_GREETING_CHANNEL_ID=1234567890123456789
STATUS_UPDATE_CHANNEL_ID=1234567890123456789
```

- `ADMIN_ROLE_NAMES`: Discord roles that can use admin commands
- `ADMIN_USER_IDS`: User IDs that can use admin commands regardless of roles
- `UPLOAD_CHANNEL_ID`: Channel for mission uploads
- `FFIRE_ALERT_CHANNEL_ID`: Channel for friendly fire alerts
- `STARTUP_GREETING_CHANNEL_ID`: Channel for startup messages
- `STATUS_UPDATE_CHANNEL_ID`: Channel for regular status updates

### 5. DCS Server Configuration

Update paths in `dcs_admin_bot.py` to match your DCS server installation:

```python
DCS_SAVED_GAMES = r"C:\Users\username\Saved Games\DCS.dcs_serverrelease"
DCS_SCRIPTS = os.path.join(DCS_SAVED_GAMES, "Scripts")
DCS_SERVER_BIN = r"C:\Program Files\Eagle Dynamics\DCS World Server\bin"
```

### 6. Launch the Bot

Run the bot with:

```pwsh
python dcs_admin_bot.py
```

For persistent operation, you can use the included PowerShell script:

```pwsh
.\Local\run_dcs_bot.ps1
```
