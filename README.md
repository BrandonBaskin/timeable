## Timely-style Time Converter Bot

This is a Python Discord bot inspired by [`timely-bot`](https://github.com/TheBobbyLlama/timely-bot) that converts times in chat messages into Discord timestamps so everyone sees them in their local time.

It supports relaxed formats such as:

- `8:00p`
- `"8:00a"`
- `'8:00a'`
- `*8:00a`
- `8:00p PST`
- `13:00 UTC`
- `1AM (London)`

When it finds matching times, it replies with lines like:

`**8:00p PST** - <t:1646172000:t>`

### Features

- **Flexible time formats**: 12-hour, 24-hour, and compact times with or without AM/PM.
- **Loose wrappers**: Accepts bare times, quoted times, and times prefixed with `*` (Markdown italics).
- **Per-user timezone**: Users set their timezone once with `/timely`, and bare times will be interpreted in their local zone.
- **Explicit zones**: Suffixes like `PST`, `London`, `Tokyo`, or `Vancouver` are mapped via `timezone_overrides.json`.

---

### Prerequisites

- Python 3.9+
- A Discord application and bot token from the Discord Developer Portal.

---

### Setup

1. **Install dependencies**

   In the project directory run:

   ```bash
   pip install -r requirements.txt
   ```

2. **Create a `.env` file**

   In the project root, create a file named `.env`:

   ```env
   DISCORD_TOKEN=your_bot_token_here
   ```

3. **Enable message content intent**

   In the Discord Developer Portal for your application:

   - Go to **Bot** → **Privileged Gateway Intents**.
   - Enable **Message Content Intent**.
   - Save changes.

4. **Run the bot**

   ```bash
   python bot.py
   ```

---

### Usage

- **Set your timezone**

  Use the slash command in any server where the bot is present:

  ```text
  /timely timezone: "PST"
  ```

  You can pass things like:

  - `PST`, `EST`, `CET`
  - City names like `London`, `Tokyo`, `Vancouver`
  - Codes from the internal list such as `R` (US Eastern), `U` (US Pacific), etc.

- **Post a time**

  After setting your timezone, just type times naturally in messages, for example:

  - `Let's meet at 8:00p`
  - `"8:00a"` works too
  - `*8:00a` (Markdown italic)
  - `Standup at 13:00 UTC`
  - `Raid at 1AM (London)`

  The bot will reply with one line per time it finds, using Discord's `<t:unix:t>` timestamp so everyone sees the correct local time.

---

### Notes

- The bot uses `timezones.json` and `timezone_overrides.json` (ported from `timely-bot`) to map human-friendly labels and abbreviations into fixed UTC offsets.
- Daylight savings rules are approximated via offsets and aliases; this is intended for convenience, not as a precise calendaring system.

