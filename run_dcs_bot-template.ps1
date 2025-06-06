# run_dcs_bot.ps1

# Set Discord bot token and guild ID
$env:DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"
$env:DISCORD_GUILD_ID = "YOUR_DISCORD_GUILD_ID_HERE"

# Set channel IDs (from your config file)
$env:DISCORD_UPLOAD_CHANNEL_ID = "CHANNEL_ID_FOR_UPLOADS"  # <-- Replace with your upload channel ID
$env:DISCORD_FFIRE_ALERT_CHANNEL_ID = "FriendlyFireAlertChannelID"  # <-- Replace with your Friendly Fire Alert channel ID
$env:DISCORD_STARTUP_GREETING_CHANNEL_ID = "GREETING_CHANNEL_ID"  # <-- Replace with your startup greeting channel ID
$env:DISCORD_STATUS_UPDATE_CHANNEL_ID = "updateChannelID"  # <-- Replace with your status update channel ID

# Set admin user IDs (comma-separated, overrides config file [users] section)
$env:DISCORD_ADMIN_USER_IDS = "123456789012345678,987654321098765432"  # optional with Roles<-- Replace with your admin Discord user IDs

# Set admin role names (comma-separated, overrides config file [roles] section)
$env:DISCORD_ADMIN_ROLE_NAMES = "Server Admins,SuperAdmin"  # <-- Replace with your admin role names

# (Optional) Set any other environment variables your bot may use

# Start the bot EXE (update the path if needed)
Start-Process -FilePath "Your_script_PATH\dcs_admin_bot.exe" -NoNewWindow -Wait