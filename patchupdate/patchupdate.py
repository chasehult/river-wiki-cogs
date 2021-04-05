import asyncio
import json
import re
from typing import Optional, Type

import aiohttp
import rivercogutils as utils
from redbot.core import commands
from mwrogue.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient

from patchupdate.champion_modifier import ChampionModifier
from patchupdate.item_modifier import ItemModifier
from patchupdate.template_modifier import TemplateModifier

DDRAGON_V = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON = "http://ddragon.leagueoflegends.com/cdn/{}/data/en_US/{}.json"


class PatchUpdate(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.group()
    async def patchupdate(self, ctx):
        pass

    @staticmethod
    async def updatestats(site: EsportsClient, template_modifier: Type[TemplateModifier],
                          version: Optional[str] = None):
        async with aiohttp.ClientSession() as session:
            if version is None:
                async with session.get(DDRAGON_V) as resp:
                    version = json.loads(await resp.text())[0]
            elif not re.match(r'\d+\.\d+\.\d+', version):
                version += ".1"
            async with session.get(DDRAGON.format(version, template_modifier.section.lower())) as resp:
                data = json.loads(await resp.text())['data']
            tm = template_modifier(site, "Infobox " + template_modifier.section, data=data,
                                   summary=template_modifier.section + " Update for " + version)

            await asyncio.get_event_loop().run_in_executor(None, tm.run)
            site.report_all_errors('patchupdate')

    @patchupdate.command()
    async def championstats(self, ctx, version=None):
        await ctx.send("Okay, starting!")
        site = await utils.login_if_possible(ctx, self.bot, 'lol')
        async with ctx.typing():
            await self.updatestats(site, ChampionModifier, version)
        await ctx.send("Okay, done!")

    @patchupdate.command()
    async def itemstats(self, ctx, version=None):
        await ctx.send("Okay, starting!")
        site = await utils.login_if_possible(ctx, self.bot, 'lol')
        async with ctx.typing():
            await self.updatestats(site, ItemModifier, version)
        await ctx.send("Okay, done!")


if __name__ == "__main__":
    lolsite = EsportsClient('lol', credentials=AuthCredentials(user_file='me'))
    asyncio.run(PatchUpdate.updatestats(lolsite, ChampionModifier))
    # asyncio.run(PatchUpdate.updatestats(lolsite, ItemModifier))
