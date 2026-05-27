"""Set-algebra pings for the /ping slash command.

Operands resolve to a *set* of members:

    @here / here    members currently online
    @everyone       every (non-bot) member of the server
    @<role> / role  members with that role (names may contain spaces)
    <@&id>          a role mention
    <@id>           a single member mention

Operators (lowest to highest precedence): | ^ & ! ( )
"""

import discord
from discord import app_commands


def tokenize(expr: str):
    """Turn a target expression into a list of ``(kind, value)`` tokens."""
    tokens = []
    i = 0
    n = len(expr)
    while i < n:
        char = expr[i]
        if char.isspace():
            i += 1
        elif char == "(":
            tokens.append(("lparen", "("))
            i += 1
        elif char == ")":
            tokens.append(("rparen", ")"))
            i += 1
        elif char == "&":
            tokens.append(("op", "&"))
            i += 1
        elif char == "|":
            tokens.append(("op", "|"))
            i += 1
        elif char == "^":
            tokens.append(("op", "^"))
            i += 1
        elif char == "!":
            tokens.append(("not", "!"))
            i += 1
        elif char == "<":
            # A raw Discord mention like <@&123> (role) or <@123> (user).
            end = expr.find(">", i)
            if end == -1:
                raise ValueError("Unterminated mention (missing '>').")
            tokens.append(("operand", expr[i : end + 1]))
            i = end + 1
        elif char == "@":
            # A textual operand: read until the next operator/paren/mention.
            j = i + 1
            while j < n and expr[j] not in "&|^!()<":
                j += 1
            name = expr[i + 1 : j].strip()
            if not name:
                raise ValueError("Empty target after '@'.")
            tokens.append(("operand", "@" + name))
            i = j
        elif char.isalpha() or char == "_":
            # A bare role name without '@' prefix (e.g. from the slash command).
            j = i
            while j < n and expr[j] not in "&|^!()<@":
                j += 1
            name = expr[i:j].strip()
            if name:
                tokens.append(("operand", "@" + name))
            i = j
        else:
            raise ValueError(f"Unexpected character {char!r} in target expression.")
    return tokens


class Parser:
    """Recursive-descent parser.

    Precedence, loosest to tightest: ``|`` then ``^`` then ``&`` then unary ``!``.
    """

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def parse(self):
        if not self.tokens:
            raise ValueError("Empty target expression.")
        node = self._parse_or()
        if self.pos != len(self.tokens):
            raise ValueError("Unexpected trailing input in target expression.")
        return node

    def _parse_or(self):
        node = self._parse_xor()
        while self._peek() == ("op", "|"):
            self.pos += 1
            node = ("|", node, self._parse_xor())
        return node

    def _parse_xor(self):
        node = self._parse_and()
        while self._peek() == ("op", "^"):
            self.pos += 1
            node = ("^", node, self._parse_and())
        return node

    def _parse_and(self):
        node = self._parse_unary()
        while self._peek() == ("op", "&"):
            self.pos += 1
            node = ("&", node, self._parse_unary())
        return node

    def _parse_unary(self):
        if self._peek()[0] == "not":
            self.pos += 1
            return ("!", self._parse_unary())
        return self._parse_atom()

    def _parse_atom(self):
        kind, value = self._peek()
        if kind == "lparen":
            self.pos += 1
            node = self._parse_or()
            if self._peek()[0] != "rparen":
                raise ValueError("Missing closing parenthesis.")
            self.pos += 1
            return node
        if kind == "operand":
            self.pos += 1
            return ("operand", value)
        raise ValueError("Expected a target, '!' or '(' in target expression.")


def resolve_operand(value: str, guild: discord.Guild):
    """Resolve a single operand token to a set of ``discord.Member``."""
    members = guild.members

    if value.startswith("<@&") and value.endswith(">"):
        role_id = int(value[3:-1])
        role = guild.get_role(role_id)
        if role is None:
            raise ValueError(f"Could not find the role {value}.")
        return set(role.members)

    if value.startswith("<@") and value.endswith(">"):
        member_id = int(value[2:-1].lstrip("!"))
        member = guild.get_member(member_id)
        if member is None:
            raise ValueError(f"Could not find the member {value}.")
        return {member}

    name = value[1:] if value.startswith("@") else value
    lowered = name.lower()

    if lowered == "here":
        return {m for m in members if m.status is not discord.Status.offline}
    if lowered == "everyone":
        return set(members)

    role = discord.utils.find(lambda r: r.name.lower() == lowered, guild.roles)
    if role is None:
        raise ValueError(f"Could not find a role named '{name}'.")
    return set(role.members)


def evaluate(node, guild: discord.Guild):
    """Evaluate a parsed expression to a set of members."""
    kind = node[0]
    if kind == "operand":
        return resolve_operand(node[1], guild)
    if kind == "!":
        return set(guild.members) - evaluate(node[1], guild)
    left = evaluate(node[1], guild)
    right = evaluate(node[2], guild)
    if kind == "&":
        return left & right
    if kind == "|":
        return left | right
    if kind == "^":
        return left ^ right
    raise ValueError(f"Unknown operator {kind!r}.")



def _expression_prefix(current: str) -> tuple[str, str]:
    """Split current expression into (typed_prefix, partial_operand).

    The typed_prefix is everything up to and including the last operator/paren
    (plus trailing spaces); partial_operand is the token being typed right now.
    """
    last_op = -1
    for i, c in enumerate(current):
        if c in "&|^!()":
            last_op = i
    if last_op == -1:
        return "", current
    split = last_op + 1
    while split < len(current) and current[split] == " ":
        split += 1
    return current[:split], current[split:]


def get_autocomplete_choices(
    guild: discord.Guild | None, current: str
) -> list[app_commands.Choice[str]]:
    """Return up to 25 role/operand choices matching the token being typed."""
    prefix, partial = _expression_prefix(current)
    search = partial.lstrip("@").lower()

    candidates = ["@here", "@everyone"]
    if guild:
        for role in guild.roles:
            if not role.is_default():
                candidates.append(role.name)

    matched = [c for c in candidates if search in c.lstrip("@").lower()]
    return [
        app_commands.Choice(name=(prefix + c)[:100], value=(prefix + c)[:100])
        for c in matched[:25]
    ]


async def send_pings_interaction(
    interaction: discord.Interaction, members, message: str
):
    """Ping members via a slash command interaction, splitting at 2000 chars."""
    allowed = discord.AllowedMentions(users=True, roles=False, everyone=False)

    chunks: list[str] = []
    current = ""
    for member in members:
        mention = member.mention
        addition = mention if not current else " " + mention
        if len(current) + len(addition) > 1900:
            chunks.append(current)
            current = mention
        else:
            current += addition
    if current:
        chunks.append(current)

    if message:
        if chunks and len(chunks[-1]) + 1 + len(message) <= 2000:
            chunks[-1] += " " + message
        else:
            chunks.append(message)

    first = True
    for chunk in chunks:
        if first:
            await interaction.followup.send(chunk, allowed_mentions=allowed)
            first = False
        else:
            await interaction.followup.send(chunk, allowed_mentions=allowed)


async def handle_slash_ping(
    interaction: discord.Interaction, expression: str, message: str
):
    """Handle the /ping application command."""
    await interaction.response.defer()

    if interaction.guild is None:
        await interaction.followup.send("This command can only be used in a server.")
        return

    try:
        node = Parser(tokenize(expression)).parse()
        members = evaluate(node, interaction.guild)
    except ValueError as exc:
        await interaction.followup.send(f"⚠️ {exc}")
        return

    members = {m for m in members if not m.bot}
    if not members:
        await interaction.followup.send("No members matched that expression.")
        return

    ordered = sorted(members, key=lambda m: m.display_name.lower())
    await send_pings_interaction(interaction, ordered, message)


