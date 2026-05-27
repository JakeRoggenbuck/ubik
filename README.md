# ubik

🤖🟣 A general use-case discord bot

<img width="102.4" height="153.6" alt="zany ubik" src="https://github.com/user-attachments/assets/2f59fec4-652d-4284-87af-718fe4e5ad5f" />

## Setup

1. Create an application in the Discord Developer Portal.
2. Go to the Bot page and select the correct toggles.
3. Go to OAuth and select Bot in the check boxes.
4. Then select Admin.
5. Copy the URL and add to a server.

## Python setup (uv)

1. Install `uv` from https://docs.astral.sh/uv/.
2. Install dependencies with `uv sync`.

## Run

```bash
python3 main.py
```

To enable the `>update` command (git pull + restart), launch via the wrapper instead:

```bash
./run.sh
```

The wrapper relaunches the bot when it exits with code 42, which is what `>update` does after pulling. Set `admin_id` in `bot.toml` to the Discord user ID allowed to run `>update`.

## Commands

### Ping

Ping a computed set of members using set-algebra expressions.

**Slash command (recommended):**

```
/ping expression:<expr> message:<text>
```

The `expression` field has autocomplete — type a role name or `@here` and select from the dropdown. Operators (`&`, `|`, `^`, `!`) must be typed manually between selections.

```
/ping expression:@here & Rusty Minecraft message:can someone review my PR
/ping expression:@here | Mods message:Hey there!
/ping expression:!(@here) message:you all missed it
```

**Operands:**

| Token       | Members                                           |
| ----------- | ------------------------------------------------- |
| `@here`     | members currently online                          |
| `@everyone` | every member of the server                        |
| `@<role>`   | members with that role (names may contain spaces) |
| `<@&id>`    | a role mention                                    |
| `<@id>`     | a single member mention                           |

**Operators** (loosest to tightest precedence):

| Operator | Meaning                       |
| -------- | ----------------------------- |
| `\|`     | union — in either group       |
| `^`      | symmetric difference — in exactly one group |
| `&`      | intersection — in both groups |
| `!`      | complement — everyone **not** in the group |
| `( )`    | grouping                      |

Bots are never pinged. `@here` requires the **Presence Intent** enabled in the Discord Developer Portal.

### Activity

```
>activity [limit]
```

Shows message counts per member in the server. `limit` defaults to 1000 messages scanned.

### Birthdays

```
>birthdays
>birthday channel check
```

Lists everyone's birthday (channel-restricted). `>birthday channel check` sends a test message to the configured announcements channel.

Configure birthdays in `birthdays.toml`:

```toml
birthdays = [
  { month = 1, day = 23, user_id = 12345, name = "Ubik" },
]
```

### Notifications

Notification streams are configured in `notification_streams.toml`. Each stream points to a Python script implementing:

```python
def get_new_events() -> list[str] | list[dict]: ...
```

The script handles deduplication so only new events are returned each run. The bot checks streams once daily.

```
>notify list                          — list available streams
>notify signup <stream> [dm|channel]  — subscribe
>notify unsubscribe <stream>          — unsubscribe
>notify run                           — manually trigger all streams
```

### LaTeX

```
>latex <expression>
```

Renders a LaTeX expression as an image. Example: `>latex e^{i\pi} + 1 = 0`

### Kronicler

```
>kronicler
```

Shows a runtime plot from kronicler data.

### Utility

```
>commit   — show the latest git commit hash and date
>source   — show the GitHub repository link
>link     — show the bot invite link
>update   — git pull and restart (admin only)
>eval     — evaluate Hy (Lisp) code (admin only)
```
