# DiscordDump

**NOTE!!! You can ask for support for this in issues, but it's not intended as user-friendly. Please try to understand the code yourself. I've made it purely for myself.**

Pile of ~~shit~~ scripts to dump all messages of an entire discord user account.

Written using Geniune Stupidity (tm), and AI used only for comments in the code (I don't care about contents of comments, just the fact that they exist.)

PREREQUIREMENTS: [Vesktop](https://vesktop.dev/), NodeJS, Python, MongoDB, mitmproxy.

## DMs

### REOPEN CLOSED DMS

1. Request a Discord data dump in settings with messages.
2. Unpack in `data/package`
3. Do `node scripts/01_visit_dms_prepare_for_nodejs.js`
4. Grab `data/all_recepients.json`. Insert in `scripts/01_visit_dms.js` and run in Vesktop console (Ctrl+Shift+I).
*Disregard previous step, grab `data/all_recepients.json`, insert it in `scripts/01_visit_dms_and_scroll.js` and run, opened DMs won't persist after ctrl+r!*

### DUMP MESSAGES

1. Launch mitmproxy using `aa_fetch_as_user.ps1`.
2. Install the CA certificates to your PC.
3. Run `aa_start_vesktop.bat`
4. Paste `scripts/01_fetch_messages_as_user_dm_scroller.js` in Vesktop console (Ctrl+Shift+I) and AFK for a while.

## Guilds

### DUMP MESSAGEES

1. Create `.env` with at least one `DISCORD_TOKEN=your_bot_token`
2. Create `guilds.txt` with format `guild_id : priority`, where priority is a number. If priority > 2, then multiple tokens will be used to avoid ratelimits (tested with 5 bot tokens with achieved speed 150 messages per second, could optimized further but I didn't bother).
3. Run `python 01_fetch_messages_as_bot.py`
