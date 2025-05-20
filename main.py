from twitchAPI.chat import Chat, EventData, ChatMessage, ChatCommand
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch
import aiohttp
import asyncio
import credentials
import time

APP_ID = credentials.client_id
APP_SECRET = credentials.client_secret
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.CHANNEL_MANAGE_BROADCAST, AuthScope.CLIPS_EDIT]
TARGET_CHANNEL = 'spesta_'

twitch = None
clip_cooldown_seconds = 60  # Default cooldown time
user_last_clip_time = {}

async def on_message(msg: ChatMessage):
    print(f'{msg.user.display_name} - {msg.text}')

async def on_ready(ready_event: EventData):
    await ready_event.chat.join_room(TARGET_CHANNEL)
    print('Bot Ready')

async def get_user_id(username, oauth_token, client_id):
    url = f"https://api.twitch.tv/helix/users?login={username}"
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {oauth_token}'
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if 'data' in data and len(data['data']) > 0:
                return data['data'][0]['id']
            else:
                return None

async def easter_egg(cmd: ChatCommand):
    await cmd.reply("You found the easter egg")

async def create_clip(cmd: ChatCommand):
    global twitch, user_last_clip_time, clip_cooldown_seconds

    user = cmd.user.name.lower()

    # Check cooldown
    current_time = time.time()
    if user in user_last_clip_time:
        elapsed = current_time - user_last_clip_time[user]
        if elapsed < clip_cooldown_seconds:
            await cmd.reply(f"{user}, you need to wait {int(clip_cooldown_seconds - elapsed)}s before creating another clip.")
            return

    broadcaster_id = None
    async for user_info in twitch.get_users(logins=[TARGET_CHANNEL]):
        broadcaster_id = user_info.id

    if broadcaster_id is None:
        await cmd.reply("Couldn't get broadcaster ID.")
        return

    clip_resp = await twitch.create_clip(broadcaster_id)

    if clip_resp is not None and clip_resp.id is not None:
        clip_url = f"https://clips.twitch.tv/{clip_resp.id}"

        clip_title = cmd.parameter if cmd.parameter else "Untitled"

        response_message = f'Clip created: "{clip_title} | {cmd.user.name}" → {clip_url}'
        await cmd.reply(response_message)

        # Set cooldown time
        user_last_clip_time[user] = current_time

    else:
        await cmd.reply("Couldn't create a clip.")

async def set_clip_cooldown(cmd: ChatCommand):
    global clip_cooldown_seconds

    if cmd.user.name.lower() != TARGET_CHANNEL.lower():
        await cmd.reply("Only the streamer can change the clip cooldown.")
        return

    if not cmd.parameter or not cmd.parameter.isdigit():
        await cmd.reply("Please provide a cooldown in seconds, e.g. !setclipcooldown 30")
        return

    clip_cooldown_seconds = int(cmd.parameter)
    await cmd.reply(f"Clip cooldown set to {clip_cooldown_seconds} seconds.")

async def run_bot():
    global twitch

    twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE)
    token, refresh_token = await auth.authenticate()

    await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)

    chat = await Chat(twitch)

    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)

    chat.register_command('easteregg', easter_egg)
    chat.register_command('clip', create_clip)
    chat.register_command('setclipcooldown', set_clip_cooldown)

    chat.start()

    try:
        input('Press ENTER to stop\n')
    finally:
        await chat.disconnect()
        await twitch.close()

asyncio.run(run_bot())
