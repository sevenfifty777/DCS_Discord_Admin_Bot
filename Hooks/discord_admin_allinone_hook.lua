local monitor = {}

local lfs = require('lfs')
local scripts_dir = lfs.writedir() .. "/Scripts/Discord_Admin_Bot/"
local missions_dir = lfs.writedir() .. "/Missions/"

local csv_filename         = scripts_dir .. "player_log.csv"
do
    local f = io.open(csv_filename, "r")
    local first_line = f and f:read("*l") or nil
    if f then f:close() end
    if not first_line or not first_line:find("event") then
        local f2 = io.open(csv_filename, "a")
        if f2 then
            f2:write("date,time,name,ucid,ipaddr,side,slot,ping,event,extra1,extra2\n")
            f2:close()
        end
    end
end
local banlist_filename     = scripts_dir .. "banlist.txt"
local admin_ucids_path     = scripts_dir .. "admin_ucids.txt"
local missionqueue_path    = scripts_dir .. "missionqueue.txt"
local missioncmd_path      = scripts_dir .. "missioncmd.txt"
local missionlist_path     = scripts_dir .. "missionlist.txt"
local missionstatus_path   = scripts_dir .. "missionstatus.txt"
local missioninfo_path     = scripts_dir .. "missioninfo.txt"
local kickqueue_path       = scripts_dir .. "kickqueue.txt"
local friendlyfire_path    = scripts_dir .. "friendlyfire.txt"
local chatcmd_file         = scripts_dir .. "chatcmd.txt"


local last_chatcmd_line = 0

local function process_chatcmd_file()
    local f = io.open(chatcmd_file, "r")
    if not f then return end
    local lines = {}
    for line in f:lines() do
        table.insert(lines, line)
    end
    f:close()
    for i = last_chatcmd_line + 1, #lines do
        local msg = lines[i]
        if msg and msg ~= "" then
            net.send_chat("[BOT] " .. msg, true) -- Sends as global chat
        end
    end
    last_chatcmd_line = #lines
end

-- Utility: Write player info as CSV
local function append_player_csv(info)
    local f = io.open(csv_filename, "a")
    if f then
        f:write(string.format(
            "%s,%s,%s,%s,%s,%s,%s,%s,CONNECT,,\n",
            os.date("%Y-%m-%d"), os.date("%H:%M:%S"),
            tostring(info.name or ""),
            tostring(info.ucid or ""),
            tostring(info.ipaddr or ""),
            tostring(info.side or ""),
            tostring(info.slot or ""),
            tostring(info.ping or "")
        ))
        f:close()
    end
end


local function append_player_event_csv(info, event, extra1, extra2)
    local f = io.open(csv_filename, "a")
    if f then
        f:write(string.format(
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n",
            os.date("%Y-%m-%d"), os.date("%H:%M:%S"),
            tostring(info.name or ""),
            tostring(info.ucid or ""),
            tostring(info.ipaddr or ""),
            tostring(info.side or ""),
            tostring(info.slot or ""),
            tostring(info.ping or ""),
            tostring(event or ""),
            tostring(extra1 or ""),
            tostring(extra2 or "")
        ))
        f:close()
    end
end


local function append_player_disconnect_csv(info)
    local f = io.open(csv_filename, "a")
    if f then
        f:write(string.format(
            "%s,%s,%s,%s,%s,%s,%s,%s,DISCONNECT,,\n",
            os.date("%Y-%m-%d"), os.date("%H:%M:%S"),
            tostring(info.name or ""),
            tostring(info.ucid or ""),
            tostring(info.ipaddr or ""),
            tostring(info.side or ""),
            tostring(info.slot or ""),
            tostring(info.ping or "")
        ))
        f:close()
    end
end

-- ===== Admin List Management =====
local function load_admin_ucids()
    local admin_ucids = {}
    local f = io.open(admin_ucids_path, "r")
    if f then
        for line in f:lines() do
            local u = line:match("^%s*([%w]+)%s*$")
            if u then
                admin_ucids[u] = true
            end
        end
        f:close()
    end
    return admin_ucids
end

local function save_admin_ucids(admin_ucids)
    local f = io.open(admin_ucids_path, "w")
    if f then
        for u, v in pairs(admin_ucids) do
            if v then f:write(u .. "\n") end
        end
        f:close()
    end
end

-- Banlist functions
local function load_banlist()
    local bans = {}
    local f = io.open(banlist_filename, "r")
    if not f then return bans end
    for line in f:lines() do
        -- ucid,name,ban_start,period,reason
        local ucid, name, ban_start, period, reason = line:match("([^,]+),([^,]*),([^,]*),([^,]*),?(.*)")
        if ucid then
            bans[ucid] = {
                name = name or "",
                ban_start = tonumber(ban_start) or 0,
                period = tonumber(period) or 0,
                reason = reason or ""
            }
        end
    end
    f:close()
    return bans
end

local function save_banlist(bans)
    local f = io.open(banlist_filename, "w")
    if f then
        for ucid, data in pairs(bans) do
            f:write(ucid .. "," .. (data.name or "") .. "," .. tostring(data.ban_start or 0) .. "," .. tostring(data.period or 0) .. "," .. (data.reason or "") .. "\n")
        end
        f:close()
    end
end

local function ensure_csv_header()
    local f = io.open(csv_filename, "r")
    if not f then
        f = io.open(csv_filename, "w")
        if f then
            f:write("date,time,name,ucid,ipaddr,side,slot,ping,event,extra1,extra2\n")
            f:close()
        end
    else
        f:close()
    end
end

ensure_csv_header()

-- Check ban on connect
function monitor.onPlayerTryConnect(ipaddr, name, ucid, playerID)
    local bans = load_banlist()
    local ban = bans[ucid]
    if ban then
        local now = os.time()
        if ban.period > 0 then
            if now < (ban.ban_start + ban.period) then
                local remaining = (ban.ban_start + ban.period) - now
                return false, "Banned: " .. (ban.reason or "") .. string.format(" (ban expires in %d seconds)", remaining)
            else
                -- Ban expired, auto-remove
                bans[ucid] = nil
                save_banlist(bans)
            end
        else
            -- Permanent ban
            return false, "Banned: " .. (ban.reason or "")
        end
    end
    return true
end

-- Save connection info
function monitor.onPlayerConnect(playerID)
    local info = net.get_player_info(playerID)
    if info then
        append_player_csv(info)
    end
end

-- Save disconnect info
function monitor.onPlayerDisconnect(playerID, err_code)
    local info = net.get_player_info(playerID)
    if info then
        info.name = info.name or "<unknown>"
        info.ucid = info.ucid or "<unknown>"
        info.ipaddr = info.ipaddr or "<unknown>"
        append_player_disconnect_csv(info)
    end
end


function monitor.onChatMessage(message, from)
    local info = net.get_player_info(from)
    if not info or not info.ucid then return end

    local ucid = info.ucid
    local admin_ucids = load_admin_ucids()
    if not admin_ucids[ucid] then return end

    -- Add admin by [Player Name] (player must be connected)
    local addname = message:match("^!addadmin%s+%[(.-)%]")
    if addname then
        local found_ucid, found_name = nil, nil
        for _, pid in ipairs(net.get_player_list()) do
            local pinfo = net.get_player_info(pid)
            if pinfo and pinfo.name and pinfo.ucid then
                if pinfo.name:lower():find(addname:lower(), 1, true) then
                    found_ucid = pinfo.ucid
                    found_name = pinfo.name
                    break
                end
            end
        end
        if found_ucid then
            if admin_ucids[found_ucid] then
                net.send_chat_to("This player is already an admin (" .. found_name .. " / " .. found_ucid .. ").", from)
                return
            end
            admin_ucids[found_ucid] = true
            save_admin_ucids(admin_ucids)
            net.send_chat_to("Added admin: " .. found_name .. " (UCID: " .. found_ucid .. ")", from)
            net.send_chat("[ADMIN] Added admin: " .. found_name .. " (UCID: " .. found_ucid .. ")", true)
        else
            net.send_chat_to("Player not found (must be connected): " .. addname, from)
        end
        return
    end

        -- Remove admin by [Player Name] (player must be connected)
    local remname = message:match("^!removeadmin%s+%[(.-)%]")
    if remname then
        local found_ucid, found_name = nil, nil
        for _, pid in ipairs(net.get_player_list()) do
            local pinfo = net.get_player_info(pid)
            if pinfo and pinfo.name and pinfo.ucid then
                if pinfo.name:lower():find(remname:lower(), 1, true) then
                    found_ucid = pinfo.ucid
                    found_name = pinfo.name
                    break
                end
            end
        end
        if found_ucid then
            if not admin_ucids[found_ucid] then
                net.send_chat_to("This player is not an admin (" .. found_name .. " / " .. found_ucid .. ").", from)
                return
            end
            admin_ucids[found_ucid] = nil
            save_admin_ucids(admin_ucids)
            net.send_chat_to("Removed admin: " .. found_name .. " (UCID: " .. found_ucid .. ")", from)
            net.send_chat("[ADMIN] Removed admin: " .. found_name .. " (UCID: " .. found_ucid .. ")", true)
        else
            net.send_chat_to("Player not found (must be connected): " .. remname, from)
        end
        return
    end


    -- !ban [player name] duration reason
    local ban_args = message:match("^!ban%s+(.+)")
    if ban_args then
        local name, duration, reason

        local bracket_name, rest = ban_args:match("^%[(.-)%]%s*(.*)")
        if bracket_name then
            name = bracket_name
            local d, r = rest:match("^(%d+)%s*(.*)")
            duration = tonumber(d) or 0
            reason = r or ""
        else
            local pattern = "^(.-)%s+(%d+)%s*(.*)$"
            local m_name, m_duration, m_reason = ban_args:match(pattern)
            if m_name and m_duration then
                name = m_name
                duration = tonumber(m_duration) or 0
                reason = m_reason or ""
            else
                name = ban_args
                duration = 0
                reason = ""
            end
        end

        local matched_id, matched_ucid, matched_name = nil, nil, nil
        for _, pid in ipairs(net.get_player_list()) do
            local pinfo = net.get_player_info(pid)
            if pinfo and pinfo.name and pinfo.ucid then
                if pinfo.name:lower():find(name:lower(), 1, true) then
                    matched_id = pid
                    matched_ucid = pinfo.ucid
                    matched_name = pinfo.name
                    break
                end
            end
        end
        if matched_ucid then
            local bans = load_banlist()
            bans[matched_ucid] = {
                name = matched_name,
                ban_start = os.time(),
                period = duration or 0,
                reason = reason or ""
            }
            save_banlist(bans)
            net.kick(matched_id, "Banned: " .. (reason or ""))
            if duration and duration > 0 then
                net.send_chat_to("Player " .. matched_name .. " has been banned for " .. tostring(duration) .. " seconds.", from)
                net.send_chat("[ADMIN] Player " .. matched_name .. " banned for " .. tostring(duration) .. " seconds.", true)
            else
                net.send_chat_to("Player " .. matched_name .. " has been permanently banned.", from)
                net.send_chat("[ADMIN] Player " .. matched_name .. " has been permanently banned.", true)
            end
        else
            net.send_chat_to("Player not found or not online.", from)
        end
        return
    end

    -- !unban [player name]
    local unban_bracket = message:match("^!unban%s+%[(.-)%]")
    if unban_bracket then
        local unbanname = unban_bracket
        local bans = load_banlist()
        local found_ucid, found_name = nil, nil
        for ucid, data in pairs(bans) do
            if data.name and data.name:lower():find(unbanname:lower(), 1, true) then
                found_ucid = ucid
                found_name = data.name
                break
            end
        end
        if found_ucid then
            bans[found_ucid] = nil
            save_banlist(bans)
            net.send_chat_to("Player unbanned: " .. (found_name or unbanname), from)
            net.send_chat("[ADMIN] Player unbanned: " .. (found_name or unbanname), true)
        else
            net.send_chat_to("Player not found in banlist.", from)
        end
        return
    end

    -- !pause
    if message:match("^!pause$") then
        DCS.setPause(true)
        net.send_chat_to("Mission paused.", from)
        net.send_chat("[ADMIN] Mission paused by admin.", true)
        return
    end

    -- !unpause
    if message:match("^!unpause$") then
        DCS.setPause(false)
        net.send_chat_to("Mission unpaused.", from)
        net.send_chat("[ADMIN] Mission unpaused by admin.", true)
        return
    end
end

-- ===== Mission Add/Queue =====
local function process_mission_queue()
    local f = io.open(missionqueue_path, "r")
    if not f then return end
    for line in f:lines() do
        local mission_file = line:match("([%w%d%_%-%.]+%.miz)")
        if mission_file then
            local mission_path = missions_dir .. mission_file
            local result = net.missionlist_append(mission_path)
            if result then
                net.send_chat("[BOT] Mission '" .. mission_file .. "' added to server mission list.", true)
            else
                net.send_chat("[BOT] Failed to add mission '" .. mission_file .. "' (file missing or error).", true)
            end
        end
    end
    f:close()
    os.remove(missionqueue_path)
    write_mission_list()
end

function write_mission_list()
    local mlist = net.missionlist_get()
    local outf = io.open(missionlist_path, "w")
    if mlist and mlist.missionList and outf then
        for idx, fname in ipairs(mlist.missionList) do
            outf:write(string.format("%d:%s%s\n", idx, fname, (idx == mlist.current) and " [CURRENT]" or ""))
        end
        outf:close()
    end
end

function write_mission_info()
    local mlist = net.missionlist_get()
    local curidx = mlist and mlist.current or 1
    local fname = mlist and mlist.missionList and mlist.missionList[curidx] or "<unknown>"
    local mname = "<unknown>"
    local mdate = "<unknown>"
    local mtheater = "<unknown>"

    local mission_time = "<unavailable>"
    if DCS.getModelTime then
        mission_time = string.format("%.2f seconds", DCS.getModelTime() or 0)
    end

    if DCS.getMissionFilename then
        local mfile = DCS.getMissionFilename()
        if mfile and #mfile > 0 then mname = mfile end
    end
    if DCS.getMissionDate then
        local md = DCS.getMissionDate()
        if md then
            if type(md) == "table" then
                mdate = string.format("%04d-%02d-%02d", md.Year or 0, md.Month or 0, md.Day or 0)
            else
                mdate = tostring(md)
            end
        end
    end
    if DCS.getCurrentMap then
        local theater = DCS.getCurrentMap()
        if theater then mtheater = theater end
    end

    local player_count = 0
    local player_info_list = {}
    for _, pid in ipairs(net.get_player_list() or {}) do
        local info = net.get_player_info(pid)
        if info and info.name and info.ucid then
            player_count = player_count + 1
            table.insert(player_info_list, info.name .. " [" .. info.ucid .. "]")
        end
    end

    local outf = io.open(missioninfo_path, "w")
    if outf then
        outf:write("Mission Name: " .. (mname or fname) .. "\n")
        outf:write("Mission Date: " .. (mdate or "<unknown>") .. "\n")
        outf:write("Mission Time: " .. mission_time .. "\n")
        outf:write("Map: " .. (mtheater or "<unknown>") .. "\n")
        outf:write("Players Connected: " .. tostring(player_count) .. "\n")
        if #player_info_list > 0 then
            outf:write("Players:\n")
            for _, line in ipairs(player_info_list) do
                outf:write(line .. "\n")
            end
        end
        outf:close()
    end
end

local mission_status_pending = nil

local function process_missioncmd()
    local f = io.open(missioncmd_path, "r")
    if not f then return end
    for line in f:lines() do
        local cmd, arg = line:match("^(%w+):?(.*)")
        if cmd == "listmissions" then
            write_mission_list()
        elseif cmd == "loadmission" and tonumber(arg) then
            local idx = tonumber(arg)
            net.missionlist_run(idx)
            net.send_chat("[BOT] Loading mission #" .. idx .. "...", true)
            mission_status_pending = {idx = idx, frames = 0}
        elseif cmd == "missioninfo" then
            write_mission_info()
        elseif cmd == "pause" then
            DCS.setPause(true)
            net.send_chat("[BOT] Server paused by Discord admin", true)
        elseif cmd == "unpause" then
            DCS.setPause(false)
            net.send_chat("[BOT] Server unpaused by Discord admin", true)
        -- elseif cmd == "stop" then
        --     DCS.stopMission()
        --     net.send_chat("[BOT] Mission stopped by Discord admin", true)
        elseif cmd == "restart" then
            if DCS.restartMission then
                DCS.restartMission()
                net.send_chat("[BOT] Mission restarted by Discord admin (native API)", true)
            else
                local mlist = net.missionlist_get()
                if mlist and mlist.current then
                    net.missionlist_run(mlist.current)
                    net.send_chat("[BOT] Mission restarted by Discord admin (safe method)", true)
                end
            end
        -- elseif cmd == "reload" then
        --     local mlist = net.missionlist_get()
        --     if mlist and mlist.current then
        --         net.missionlist_run(mlist.current)
        --         net.send_chat("[BOT] Mission reloaded by Discord admin (safe method)", true)
        --     end
        end
    end
    f:close()
    os.remove(missioncmd_path)
end

local function report_mission_status(idx)
    local mlist = net.missionlist_get()
    local outf = io.open(missionstatus_path, "w")
    if not outf then return end

    if mlist and mlist.missionList and mlist.current then
        if mlist.current == idx then
            outf:write("OK: Mission #" .. tostring(idx) .. " is now running: " .. mlist.missionList[idx] .. "\n")
            write_mission_info()
            write_mission_list()
        elseif not mlist.missionList[idx] then
            outf:write("FAIL: Mission #" .. tostring(idx) .. " was removed (likely unsupported or failed to load)\n")
        else
            outf:write("UNKNOWN: Mission load result unclear (please check server)\n")
        end
    else
        outf:write("ERROR: Could not get mission list or status\n")
    end
    outf:close()
end

local function process_kick_queue()
    local kicklist = {}
    local f = io.open(kickqueue_path, "r")
    if f then
        for line in f:lines() do
            local ucid = line:match("^%s*([%w-]+)%s*$")
            if ucid then
                kicklist[ucid] = true
            end
        end
        f:close()
    end
    if next(kicklist) then
        for _, pid in ipairs(net.get_player_list() or {}) do
            local info = net.get_player_info(pid)
            if info and info.ucid and kicklist[info.ucid] then
                net.kick(pid, "Kicked by Discord admin")
            end
        end
        os.remove(kickqueue_path)
    end
end

local function write_friendly_fire(offender_name, offender_ucid, victim_name, victim_ucid, event)
    local f = io.open(friendlyfire_path, "a")
    if f then
        local msg = string.format(
            "[%s] EVENT:%s OFFENDER:%s|%s VICTIM:%s|%s\n",
            os.date("%Y-%m-%d %H:%M:%S"),
            event or "FRIENDLY_FIRE",
            offender_name or "<unknown>", offender_ucid or "<unknown>",
            victim_name or "<unknown>", victim_ucid or "<unknown>"
        )
        f:write(msg)
        f:close()
    end
end

local function is_player_unit(unit)
    if not unit or not unit.getPlayerName then return false end
    local pname = unit:getPlayerName()
    return pname ~= nil
end

function onEvent(event)
    if not event then return end

    -- === FRIENDLY FIRE DETECTION (unchanged) ===
    if event.id == world.event.S_EVENT_KILL then
        local initiator = event.initiator
        local target = event.target
        if initiator and target and initiator ~= target and is_player_unit(initiator) and is_player_unit(target) then
            local shooter_id = initiator:getPlayerID()
            local victim_id = target:getPlayerID()
            local shooter_info = shooter_id and net.get_player_info(shooter_id)
            local victim_info = victim_id and net.get_player_info(victim_id)
            if shooter_info and victim_info and shooter_info.ucid and victim_info.ucid then
                local shooter_coal = coalition.getCountryCoalition(initiator:getCountry())
                local victim_coal  = coalition.getCountryCoalition(target:getCountry())
                if shooter_coal and shooter_coal == victim_coal then
                    write_friendly_fire(
                        shooter_info.name, shooter_info.ucid,
                        victim_info.name,  victim_info.ucid,
                        "KILL"
                    )
                end
            end
        end
    end

    -- === NEW: LOG PLAYER EVENTS ===
    if event.id == world.event.S_EVENT_KILL then
        if event.initiator and is_player_unit(event.initiator) then
            local info = net.get_player_info(event.initiator:getPlayerID())
            local tgtType = event.target and event.target:getTypeName() or ""
            local tgtCat = event.target and event.target:getCategory() or ""
            append_player_event_csv(info, "KILL", tgtType, tgtCat)
        end
    elseif event.id == world.event.S_EVENT_DEAD then
        if event.initiator and is_player_unit(event.initiator) then
            local info = net.get_player_info(event.initiator:getPlayerID())
            append_player_event_csv(info, "DEATH")
        end
    elseif event.id == world.event.S_EVENT_LAND then
        if event.initiator and is_player_unit(event.initiator) then
            local info = net.get_player_info(event.initiator:getPlayerID())
            append_player_event_csv(info, "LAND")
        end
    elseif event.id == world.event.S_EVENT_EJECTION then
        if event.initiator and is_player_unit(event.initiator) then
            local info = net.get_player_info(event.initiator:getPlayerID())
            append_player_event_csv(info, "EJECT")
        end
    elseif event.id == world.event.S_EVENT_CRASH then
        if event.initiator and is_player_unit(event.initiator) then
            local info = net.get_player_info(event.initiator:getPlayerID())
            append_player_event_csv(info, "CRASH")
        end
    end
end

function onSimulationFrame()
    process_mission_queue()
    process_missioncmd()
    process_kick_queue()
    process_chatcmd_file()
    if mission_status_pending then
        mission_status_pending.frames = mission_status_pending.frames + 1
        if mission_status_pending.frames > 300 then
            report_mission_status(mission_status_pending.idx)
            mission_status_pending = nil
        end
    end
    if not lfs.attributes(missionlist_path) then
        write_mission_list()
    end
end

DCS.setUserCallbacks({
    onSimulationFrame = onSimulationFrame,
    onEvent = onEvent,
    onPlayerTryConnect = monitor.onPlayerTryConnect,
    onPlayerConnect = monitor.onPlayerConnect,
    onPlayerDisconnect = monitor.onPlayerDisconnect,
    onChatMessage = monitor.onChatMessage
})
