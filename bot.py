import os
import logging
from datetime import datetime, timezone
from typing import List, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from parsing import extract_time_candidates
from storage import get_user_settings, set_user_timezone
from time_convert import compute_unix_timestamp_for_candidate, load_timezone_data, resolve_timezone_choice


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("timely-bot")


class TimelyBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(command_prefix="!", intents=intents)

        # Pre-load timezone data so parsing/conversion is fast.
        load_timezone_data()

    async def setup_hook(self) -> None:
        # Sync slash commands on startup.
        await self.tree.sync()
        logger.info("Synced application commands.")


bot = TimelyBot()


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s (%s)", bot.user, bot.user and bot.user.id)
    await bot.change_presence(activity=discord.Game(name="Converting times"))


@bot.tree.command(name="timely", description="Set your timezone for time conversion.")
@app_commands.describe(
    timezone="Your timezone, e.g. 'PST', 'London', 'UTC+2', or a code from the list."
)
async def timely_command(interaction: discord.Interaction, timezone: str) -> None:
    """
    Slash command to let a user set their preferred timezone.
    """
    # Immediately acknowledge so Discord doesn't time out the interaction.
    # We'll send the real result via followup.
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True, thinking=True)

    tz_code = resolve_timezone_choice(timezone)
    if tz_code is None:
        await interaction.followup.send(
            "I couldn't recognize that timezone. "
            "Try something like `PST`, `EST`, `London`, `Tokyo`, or `UTC+2`.",
            ephemeral=True,
        )
        return

    set_user_timezone(interaction.user.id, tz_code)
    await interaction.followup.send(
        "Your timezone has been set. I will now convert bare times from your local time.",
        ephemeral=True,
    )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    logger.exception("App command error: %s", error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                f"An error occurred while handling that command: `{error}`",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"An error occurred while handling that command: `{error}`",
                ephemeral=True,
            )
    except discord.HTTPException:
        # If even the error response fails, just swallow.
        pass


@bot.event
async def on_message(message: discord.Message) -> None:
    # Ignore messages from bots (including ourselves).
    if message.author.bot:
        return

    user_settings = get_user_settings(message.author.id)
    user_tz_code = user_settings.get("timezone")

    candidates = extract_time_candidates(message.content)
    if not candidates:
        return

    # Limit how many matches we process per message to avoid spam.
    MAX_RESULTS = 10
    results: List[Tuple[str, int]] = []

    now_utc = datetime.now(timezone.utc)

    for candidate in candidates:
        if len(results) >= MAX_RESULTS:
            break

        unix_ts = compute_unix_timestamp_for_candidate(
            candidate, user_tz_code=user_tz_code, now_utc=now_utc
        )
        if unix_ts is not None:
            results.append((candidate.original_text, unix_ts))

    if not results:
        return

    lines = [
        f"**{original}** - <t:{unix_ts}:t>"
        for (original, unix_ts) in results
    ]
    reply = "\n".join(lines)

    try:
        await message.reply(reply)
    except discord.HTTPException as exc:
        logger.warning("Failed to send reply: %s", exc)


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Create a .env file with DISCORD_TOKEN=your_token_here."
        )

    bot.run(token)


if __name__ == "__main__":
    main()

