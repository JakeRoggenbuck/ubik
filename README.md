# ubik

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
