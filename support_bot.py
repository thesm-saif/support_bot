import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# ===== INTENTS =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== CONFIG =====
SUPPORT_ROLE_NAME = "Support Crew"              # CHANGE IF NEEDED
SUPPORT_ROLE_ID = 1463147930360746086           # CHANGE THIS
SUPPORT_GUILD_ID = 1462547101442506754          # CHANGE THIS
SUPPORT_CHANNEL_ID = 1463587424511988006        # CHANGE THIS
SERVER_NAME = "Saudia Virtual"                  # CHANGE THIS
# ==================

tickets = {}   # user_id -> thread_id
claimed = {}   # thread_id -> (staff_name, staff_role)


# ===== READY =====
@bot.event
async def on_ready():
    guild = discord.Object(id=SUPPORT_GUILD_ID)
    await bot.tree.sync(guild=guild)
    print(f"🟢 Logged in as {bot.user}")


# ===== MESSAGE HANDLER =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # ===== USER DM =====
    if isinstance(message.channel, discord.DMChannel):
        guild = bot.get_guild(SUPPORT_GUILD_ID)
        support_channel = guild.get_channel(SUPPORT_CHANNEL_ID)
        support_role = guild.get_role(SUPPORT_ROLE_ID)

        if message.author.id in tickets:
            thread = bot.get_channel(tickets[message.author.id])
            if thread:
                await thread.send(
                    f"👤 **{message.author.name}:**\n{message.content}"
                )
            return

        thread = await support_channel.create_thread(
            name=f"ticket-{message.author.name}",
            type=discord.ChannelType.private_thread
        )

        tickets[message.author.id] = thread.id

        await thread.send(
            f"{support_role.mention}\n"
            f"✈️ **NEW SUPPORT TICKET**\n"
            f"**User:** {message.author.name} (`{message.author.id}`)\n\n"
            f"**Message:**\n{message.content}"
        )

        await message.author.send(
            "**Thank you for your message!**\n"
            "**Our moderation team will reply to you here as soon as possible.**"
        )

    # ===== STAFF MESSAGE IN THREAD =====
    elif message.guild and isinstance(message.channel, discord.Thread):

        # Ticket not claimed
        if message.channel.id not in claimed:
            await message.delete()
            warn = await message.channel.send(
                f"{message.author.mention}\n**Please claim this ticket before replying.**"
            )
            await asyncio.sleep(5)
            await warn.delete()
            return

        claimer_name, staff_role = claimed[message.channel.id]

        # Claimed by someone else
        if message.author.display_name != claimer_name:
            await message.delete()
            warn = await message.channel.send(
                f"{message.author.mention}\n**This ticket is currently handled by another staff member.**"
            )
            await asyncio.sleep(5)
            await warn.delete()
            return

        # Forward staff message to user
        user_id = next((u for u, t in tickets.items() if t == message.channel.id), None)
        if not user_id:
            return

        user = await bot.fetch_user(user_id)

        await user.send(
            f"**{staff_role} {claimer_name}**\n\n"
            f"**Dear Member,**\n\n"
            f"{message.content}\n\n"
            f"**Regards,**\n"
            f"**{staff_role}**\n"
            f"**{SERVER_NAME}**"
        )

    await bot.process_commands(message)


# ===== REACTION HANDLER (WITH QUOTE) =====
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    msg = reaction.message
    content = msg.content if msg.content else "[No text content]"
    emoji = reaction.emoji

    # USER reacts in DM → notify thread
    if isinstance(msg.channel, discord.DMChannel):
        if user.id in tickets:
            thread = bot.get_channel(tickets[user.id])
            if thread:
                await thread.send(
                    f"👤 **USER {user.name} reacted {emoji} to:**\n"
                    f"> {content}"
                )

    # STAFF reacts in thread → notify user
    elif msg.guild and isinstance(msg.channel, discord.Thread):
        if msg.channel.id in claimed:
            staff_name, staff_role = claimed[msg.channel.id]
            user_id = next((u for u, t in tickets.items() if t == msg.channel.id), None)
            if user_id:
                target = await bot.fetch_user(user_id)
                await target.send(
                    f"🧑‍✈️ **STAFF {staff_name} reacted {emoji} to:**\n"
                    f"> {content}"
                )


# ===== SUPPORT CHECK =====
def is_support(interaction: discord.Interaction):
    return any(role.name == SUPPORT_ROLE_NAME for role in interaction.user.roles)


# ===== SLASH COMMANDS =====
@bot.tree.command(name="claim", description="Claim this ticket", guild=discord.Object(id=SUPPORT_GUILD_ID))
async def claim(interaction: discord.Interaction):
    if not is_support(interaction):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    claimed[interaction.channel.id] = (
        interaction.user.display_name,
        SUPPORT_ROLE_NAME
    )

    await interaction.response.send_message("✅ **Ticket claimed.**")


@bot.tree.command(
    name="transfer",
    description="Transfer this ticket to another staff member",
    guild=discord.Object(id=SUPPORT_GUILD_ID)
)
@app_commands.describe(staff="Staff member to transfer ticket to")
async def transfer(interaction: discord.Interaction, staff: discord.Member):
    if not is_support(interaction):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    if interaction.channel.id not in claimed:
        await interaction.response.send_message("❌ Ticket not claimed.", ephemeral=True)
        return

    if not (
        any(role.name == SUPPORT_ROLE_NAME for role in staff.roles)
        or staff.guild_permissions.administrator
    ):
        await interaction.response.send_message(
            "**You can only transfer tickets to Support Crew or Administrators.**",
            ephemeral=True
        )
        return

    claimed[interaction.channel.id] = (
        staff.display_name,
        SUPPORT_ROLE_NAME
    )

    await interaction.response.send_message(
        f"✅ **Ticket transferred to {staff.display_name}.**"
    )


@bot.tree.command(name="close", description="Close this ticket", guild=discord.Object(id=SUPPORT_GUILD_ID))
async def close(interaction: discord.Interaction):
    if not is_support(interaction):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return

    staff_name, staff_role = claimed.get(
        interaction.channel.id, ("Support Team", "Support Team")
    )

    user_id = next((u for u, t in tickets.items() if t == interaction.channel.id), None)
    if user_id:
        user = await bot.fetch_user(user_id)
        await user.send(
            f"**{staff_role} {staff_name}**\n\n"
            f"**Dear Member,**\n\n"
            f"**This ticket will be closed now. Should you have any further inquiries, "
            f"feel free to open a new ticket by sending a message to this bot.**\n\n"
            f"**Kindly do not reply to this message.**\n\n"
            f"**Kind Regards,**\n"
            f"**Support Team**\n"
            f"**{SERVER_NAME}**"
        )
        del tickets[user_id]

    await interaction.response.send_message("🛑 **Ticket closed.**")
    await interaction.channel.delete()

# ===== RUN =====
bot.run("MTQ2MzU4NzExNjUyMzk3ODc1Mw.GoEIJo.s3znwFDoyMdjIuy8OOy7NUKoPVIa32hP18fpVc")
