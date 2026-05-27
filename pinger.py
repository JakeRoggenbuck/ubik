"""Set-algebra pings.

Lets a user ping the result of set operations over groups of members, e.g.

    >ping (@here & @Rusty Minecraft) Hey there!
    >ping (@here | @Rusty Minecraft) Hey there!

Operands resolve to a *set* of members:

    @here       members that are currently online
    @everyone   every (non-bot) member of the server
    @<role>     members that have the named role (names may contain spaces)
    <@&id>      a role mention (what Discord sends when you autocomplete a role)
    <@id>       a single member mention

Operators (lowest to highest precedence):

    |   union                 (members in either group)
    ^   symmetric difference  (members in exactly one group)
    &   intersection          (members in both groups)
    !   complement            (everyone not in the group), unary prefix

Parentheses group sub-expressions, e.g. `!(@here)` is everyone who is not
online. The resolved members are pinged with the trailing message.
"""

import discord
import kronicler


HELP_TEXT = """\
**Set-algebra pings**
Ping the result of set operations over groups of members.

**Usage:** `>ping (<expression>) your message`

**Operands** (each resolves to a set of members):
```
@here        members that are currently online
@everyone    every member of the server
@<role>      members with that role (names may contain spaces)
<@&id>       a role mention (Discord's autocompleted role)
<@id>        a single member mention
```
**Operators** (loosest to tightest precedence):
```
|   union                 in either group
^   symmetric difference  in exactly one group
&   intersection          in both groups
!   complement            everyone NOT in the group (prefix)
( ) grouping
```
**Examples:**
```
>ping (@here & @Rusty Minecraft) can someone review my PR
>ping (@here | @Rusty Minecraft) Hey there!
>ping !(@here) you all missed it
>ping (@Mods ^ @here) Hi
>ping ((@here | @Mods) & @Rusty Minecraft) ping!
```
Bots are never pinged. Plain `>ping` replies "pong"."""


def extract_group(text: str):
    """Split ``(expr) message`` into the parenthesised expression and the rest.

    Returns ``(expr, message)``. Raises ``ValueError`` when the leading group is
    missing or unbalanced.
    """
    text = text.lstrip()
    if not text.startswith("("):
        raise ValueError("Expected the targets in parentheses, e.g. `(@here & @Role)`.")

    depth = 0
    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[1:i], text[i + 1 :].strip()

    raise ValueError("Unbalanced parentheses in the target expression.")


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


async def send_pings(ctx, members, message: str):
    """Ping the given members, splitting across messages to stay under 2000 chars."""
    allowed = discord.AllowedMentions(users=True, roles=False, everyone=False)

    chunks = []
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

    for chunk in chunks:
        await ctx.send(chunk, allowed_mentions=allowed)


@kronicler.capture
async def handle_ping(ctx, args: str):
    """Parse a target expression and ping the resulting set of members."""
    if args.strip().lower() == "help":
        await ctx.send(HELP_TEXT)
        return

    if ctx.guild is None:
        await ctx.send("This command can only be used in a server.")
        return

    usage = "Usage: `>ping (@here & @Role) your message` — see `>ping help`."

    try:
        expr, message = extract_group(args)
        node = Parser(tokenize(expr)).parse()
        members = evaluate(node, ctx.guild)
    except ValueError as exc:
        await ctx.send(f"⚠️ {exc}\n{usage}")
        return

    members = {m for m in members if not m.bot}
    if not members:
        await ctx.send("No members matched that expression.")
        return

    ordered = sorted(members, key=lambda m: m.display_name.lower())
    await send_pings(ctx, ordered, message)
