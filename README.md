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

## Example birthdays TOML

```toml
birthdays = [
  { month = 1, day = 23, user_id = 12345, name = "Ubik" },
]
```

## Notification streams

Notification streams are configured in `notification_streams.toml`.
Each stream points to a Python script that must implement:

```python
def get_new_events() -> list[str] | list[dict]:
    ...
```

That script is responsible for deduplication (for example by storing event-name hashes in a local file) so only new events are returned on each run.

### Commands

- `>notify list`
- `>notify signup <stream> [dm|channel]`
- `>notify unsubscribe <stream>`
- `>notify run` (manual run for testing)

The bot runs notification stream checks once per day and sends notifications to subscribers either by DM or in the signup channel.
