from discord.ext import commands
import discord
from datetime import datetime, timedelta, timezone
import json
import os
from collections import defaultdict, deque

CEZALAR_KANAL_ID = 1515031746935132243
GECMIS_KANAL_ID = 1515031747774120101
UYARI_DOSYASI = os.path.join(os.path.dirname(__file__), "..", "data", "warnings.json")


def uyarilari_yukle():
    os.makedirs(os.path.dirname(UYARI_DOSYASI), exist_ok=True)
    if not os.path.exists(UYARI_DOSYASI):
        return {}
    with open(UYARI_DOSYASI, "r", encoding="utf-8") as f:
        return json.load(f)


def uyarilari_kaydet(data):
    os.makedirs(os.path.dirname(UYARI_DOSYASI), exist_ok=True)
    with open(UYARI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def ceza_log(guild, baslik, renk, avatar_url=None, **alanlar):
    if not CEZALAR_KANAL_ID:
        return
    kanal = guild.get_channel(CEZALAR_KANAL_ID)
    if not kanal:
        try:
            kanal = await guild.fetch_channel(CEZALAR_KANAL_ID)
        except Exception:
            return
    embed = discord.Embed(title=baslik, color=renk, timestamp=datetime.now(timezone.utc))
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    for name, value in alanlar.items():
        embed.add_field(name=name, value=value, inline=True)
    embed.set_footer(text="Aetheris Moderasyon Sistemi")
    await kanal.send(embed=embed)


SPAM_LIMIT = 5
SPAM_MUTE_DAKIKA = 10


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._spam_gecmis: dict = defaultdict(lambda: deque(maxlen=SPAM_LIMIT))
        self._spam_muted: set = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.author.guild_permissions.manage_messages:
            return

        user_id = message.author.id
        icerik = message.content.strip().lower()

        if not icerik:
            return

        gecmis = self._spam_gecmis[user_id]
        gecmis.append(icerik)

        if len(gecmis) == SPAM_LIMIT and len(set(gecmis)) == 1:
            if user_id in self._spam_muted:
                return
            self._spam_muted.add(user_id)
            gecmis.clear()

            sure = timedelta(minutes=SPAM_MUTE_DAKIKA)
            try:
                await message.author.timeout(sure, reason="Spam — aynı mesaj 5 kez gönderildi")
            except (discord.Forbidden, discord.HTTPException):
                self._spam_muted.discard(user_id)
                return

            embed = discord.Embed(
                title="Spam Tespit Edildi",
                description=(
                    f"{message.author.mention} aynı mesajı {SPAM_LIMIT} kez gönderdiği için "
                    f"**{SPAM_MUTE_DAKIKA} dakika** susturuldu."
                ),
                color=0xFF6600,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.add_field(name="Mesaj", value=f"`{message.content[:100]}`", inline=False)
            embed.set_footer(text="A R T A K S #TR")
            await message.channel.send(embed=embed, delete_after=15)

            if GECMIS_KANAL_ID:
                gecmis_kanal = message.guild.get_channel(GECMIS_KANAL_ID)
                if gecmis_kanal:
                    log_embed = discord.Embed(
                        title="Spam — Otomatik Susturma",
                        color=0xFF6600,
                        timestamp=datetime.now(timezone.utc),
                    )
                    log_embed.add_field(name="Kullanıcı", value=f"{message.author.mention} (`{user_id}`)", inline=True)
                    log_embed.add_field(name="Süre", value=f"{SPAM_MUTE_DAKIKA} dakika", inline=True)
                    log_embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
                    log_embed.add_field(name="Mesaj", value=f"`{message.content[:200]}`", inline=False)
                    log_embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                    log_embed.set_footer(text="A R T A K S #TR")
                    await gecmis_kanal.send(embed=log_embed)

            await ceza_log(
                message.guild,
                "Spam — Otomatik Susturma",
                0xFF6600,
                Kullanıcı=f"{message.author} (`{user_id}`)",
                Sure=f"{SPAM_MUTE_DAKIKA} dakika",
                Sebep="Aynı mesaj 5 kez gönderildi",
                Kanal=message.channel.mention,
            )

    @commands.command(name="ban", aliases=["yasakla"])
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
        avatar = uye.display_avatar.url
        await uye.ban(reason=sebep)
        embed = discord.Embed(description=f"🔨 {uye.mention} başarıyla yasaklandı. **Sebep:** {sebep}", color=0xFF0000)
        embed.set_author(name=str(uye), icon_url=avatar)
        await ctx.send(embed=embed, delete_after=8)
        await ceza_log(ctx.guild, "🔨 Kullanıcı Yasaklandı", 0xFF0000,
                       avatar_url=avatar,
                       Kullanıcı=f"{uye} (`{uye.id}`)", Yetkili=f"{ctx.author.mention}", Sebep=sebep)

    @commands.command(name="unban", aliases=["yasakkaldir"])
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, kullanici_id: int):
        try:
            kullanici = await self.bot.fetch_user(kullanici_id)
            await ctx.guild.unban(kullanici)
            embed = discord.Embed(description=f"✅ {kullanici} yasağı kaldırıldı.", color=0x57F287)
            embed.set_author(name=str(kullanici), icon_url=kullanici.display_avatar.url)
            await ctx.send(embed=embed, delete_after=8)
        except discord.NotFound:
            await ctx.send("❌ Bu ID ile yasaklı kullanıcı bulunamadı.")

    @commands.command(name="kick", aliases=["at"])
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
        avatar = uye.display_avatar.url
        await uye.kick(reason=sebep)
        embed = discord.Embed(description=f"👢 {uye.mention} sunucudan atıldı. **Sebep:** {sebep}", color=0xFF0000)
        embed.set_author(name=str(uye), icon_url=avatar)
        await ctx.send(embed=embed, delete_after=8)
        await ceza_log(ctx.guild, "👢 Kullanıcı Atıldı", 0xFF0000,
                       avatar_url=avatar,
                       Kullanıcı=f"{uye} (`{uye.id}`)", Yetkili=f"{ctx.author.mention}", Sebep=sebep)

    @commands.command(name="mute", aliases=["sustur", "timeout"])
    @commands.has_permissions(moderate_members=True)
    async def sustur(self, ctx, uye: discord.Member, dakika: int = 5, *, sebep: str = "Sebep belirtilmedi"):
        if dakika < 1 or dakika > 40320:
            await ctx.send("❌ Süre 1 ile 40320 dakika (28 gün) arasında olmalı.")
            return
        bitis = datetime.now(timezone.utc) + timedelta(minutes=dakika)
        await uye.timeout(bitis, reason=sebep)
        embed = discord.Embed(description=f"🔇 {uye.mention} susturuldu. **Süre:** {dakika} dk | **Sebep:** {sebep}", color=0xFF0000)
        embed.set_author(name=str(uye), icon_url=uye.display_avatar.url)
        await ctx.send(embed=embed, delete_after=8)
        await ceza_log(ctx.guild, "🔇 Kullanıcı Susturuldu", 0xFF0000,
                       avatar_url=uye.display_avatar.url,
                       Kullanıcı=f"{uye} (`{uye.id}`)", Yetkili=f"{ctx.author.mention}",
                       Süre=f"{dakika} dakika", Sebep=sebep)

    @commands.command(name="unmute", aliases=["suskaldir", "untimeout", "susturkaldir"])
    @commands.has_permissions(moderate_members=True)
    async def suskaldir(self, ctx, uye: discord.Member):
        await uye.timeout(None)
        embed = discord.Embed(description=f"🔊 {uye.mention} susturması kaldırıldı.", color=0x57F287)
        embed.set_author(name=str(uye), icon_url=uye.display_avatar.url)
        await ctx.send(embed=embed, delete_after=8)

    @commands.command(name="yavaşmod", aliases=["yavasmod", "slowmode"])
    @commands.has_permissions(manage_channels=True)
    async def yavasmod(self, ctx, saniye: int = 0):
        if saniye < 0 or saniye > 21600:
            await ctx.send("❌ Süre 0 ile 21600 saniye arasında olmalı.")
            return
        await ctx.channel.edit(slowmode_delay=saniye)
        if saniye == 0:
            await ctx.send("✅ Yavaş mod kapatıldı.", delete_after=5)
        else:
            await ctx.send(f"✅ Yavaş mod **{saniye}** saniyeye ayarlandı.", delete_after=5)

    @commands.command(name="uyar")
    @commands.has_permissions(manage_messages=True)
    async def uyar(self, ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
        data = uyarilari_yukle()
        guild_id = str(ctx.guild.id)
        user_id = str(uye.id)
        if guild_id not in data:
            data[guild_id] = {}
        if user_id not in data[guild_id]:
            data[guild_id][user_id] = []
        data[guild_id][user_id].append({
            "sebep": sebep,
            "yetkili": str(ctx.author),
            "tarih": datetime.now(timezone.utc).isoformat(),
        })
        uyarilari_kaydet(data)
        adet = len(data[guild_id][user_id])

        try:
            dm_embed = discord.Embed(
                title="⚠️ Uyarı Aldın",
                description=f"**{ctx.guild.name}** sunucusunda uyarıldın.",
                color=0xFFA500,
                timestamp=datetime.now(timezone.utc),
            )
            dm_embed.add_field(name="Sebep", value=sebep)
            dm_embed.add_field(name="Toplam Uyarı", value=f"{adet}")
            await uye.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            description=f"⚠️ {uye.mention} uyarıldı. **Sebep:** {sebep} (Toplam: {adet})",
            color=0xFF0000,
        )
        embed.set_author(name=str(uye), icon_url=uye.display_avatar.url)
        await ctx.send(embed=embed, delete_after=8)
        await ceza_log(ctx.guild, "⚠️ Kullanıcı Uyarıldı", 0xFF0000,
                       avatar_url=uye.display_avatar.url,
                       Kullanıcı=f"{uye} (`{uye.id}`)", Yetkili=f"{ctx.author.mention}",
                       Sebep=sebep, **{"Toplam Uyarı": str(adet)})

    @commands.command(name="uyarılar", aliases=["uyarilar", "warnings"])
    @commands.has_permissions(manage_messages=True)
    async def uyarilar(self, ctx, uye: discord.Member):
        data = uyarilari_yukle()
        liste = data.get(str(ctx.guild.id), {}).get(str(uye.id), [])
        if not liste:
            await ctx.send(f"✅ {uye.mention} adlı kullanıcının uyarısı yok.")
            return
        embed = discord.Embed(title=f"⚠️ {uye.display_name} — Uyarılar", color=0xFFA500)
        for i, u in enumerate(liste, 1):
            embed.add_field(
                name=f"#{i} — {u['tarih'][:10]}",
                value=f"**Sebep:** {u['sebep']}\n**Yetkili:** {u['yetkili']}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.command(name="uyarısil", aliases=["uyarisil", "clearwarnings"])
    @commands.has_permissions(manage_messages=True)
    async def uyarisil(self, ctx, uye: discord.Member):
        data = uyarilari_yukle()
        guild_id = str(ctx.guild.id)
        user_id = str(uye.id)
        if guild_id in data and user_id in data[guild_id]:
            data[guild_id][user_id] = []
            uyarilari_kaydet(data)
        embed = discord.Embed(description=f"🗑️ {uye.mention} uyarıları silindi.", color=0x57F287)
        embed.set_author(name=str(uye), icon_url=uye.display_avatar.url)
        await ctx.send(embed=embed, delete_after=8)

    @commands.command(name="sil", aliases=["temizle", "clear"])
    @commands.has_permissions(manage_messages=True)
    async def sil(self, ctx, adet: int = 5):
        if adet < 1 or adet > 100:
            await ctx.send("❌ 1 ile 100 arasında bir sayı gir.", delete_after=5)
            return
        await ctx.message.delete()
        silinen = await ctx.channel.purge(limit=adet)
        embed = discord.Embed(color=0xFF4444, timestamp=datetime.now(timezone.utc))
        embed.set_author(name=f"{ctx.author.display_name} mesajları sildi", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Silinen Mesaj", value=f"`{len(silinen)}`", inline=True)
        embed.add_field(name="Kanal", value=ctx.channel.mention, inline=True)
        embed.add_field(name="Yetkili", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed, delete_after=4)

    @commands.command(name="kilitle", aliases=["lock"])
    @commands.has_permissions(manage_channels=True)
    async def kilitle(self, ctx, *, sebep="Belirtilmedi"):
        await ctx.message.delete()
        kanal = ctx.channel
        default_role = ctx.guild.default_role

        overwrite = kanal.overwrites_for(default_role)
        overwrite.send_messages = False
        overwrite.send_messages_in_threads = False
        overwrite.create_public_threads = False
        overwrite.create_private_threads = False
        overwrite.add_reactions = False
        await kanal.set_permissions(default_role, overwrite=overwrite)

        if hasattr(kanal, 'threads'):
            for thread in kanal.threads:
                try:
                    await thread.edit(locked=True, archived=False)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        embed = discord.Embed(
            title="Kanal Kilitlendi",
            description="Bu kanal ve tüm alt başlıkları kilitlendi.\nSadece görüntüleme aktif.",
            color=0xFF0000,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Kanal", value=kanal.mention, inline=True)
        embed.add_field(name="Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        embed.set_footer(text="A R T A K S #TR")
        await kanal.send(embed=embed)
        await ceza_log(ctx.guild, "Kanal Kilitlendi", 0xFF0000,
                       Kanal=kanal.mention, Yetkili=ctx.author.mention, Sebep=sebep)

    @commands.command(name="aç", aliases=["ac", "unlock", "kilidiac"])
    @commands.has_permissions(manage_channels=True)
    async def ac(self, ctx, *, sebep="Belirtilmedi"):
        await ctx.message.delete()
        kanal = ctx.channel
        default_role = ctx.guild.default_role

        overwrite = kanal.overwrites_for(default_role)
        overwrite.send_messages = None
        overwrite.send_messages_in_threads = None
        overwrite.create_public_threads = None
        overwrite.create_private_threads = None
        overwrite.add_reactions = None
        await kanal.set_permissions(default_role, overwrite=overwrite)

        if hasattr(kanal, 'threads'):
            for thread in kanal.threads:
                try:
                    await thread.edit(locked=False, archived=False)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        embed = discord.Embed(
            title="Kanal Açıldı",
            description="Bu kanal ve tüm alt başlıkları tekrar aktif.",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Kanal", value=kanal.mention, inline=True)
        embed.add_field(name="Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        embed.set_footer(text="A R T A K S #TR")
        await kanal.send(embed=embed)
        await ceza_log(ctx.guild, "Kanal Açıldı", 0x57F287,
                       Kanal=kanal.mention, Yetkili=ctx.author.mention, Sebep=sebep)

    @ban.error
    @kick.error
    @sustur.error
    @suskaldir.error
    @uyar.error
    @uyarilar.error
    @uyarisil.error
    @unban.error
    @kilitle.error
    @ac.error
    async def mod_hata(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Bu komutu kullanmak için yetkin yok.", delete_after=5)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Kullanıcı bulunamadı.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Eksik argüman: `{error.param.name}`", delete_after=5)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Geçersiz argüman.", delete_after=5)

    @sil.error
    async def sil_hata(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Mesaj silmek için yetkin yok.", delete_after=5)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
