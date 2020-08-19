import json
import re

import aiohttp
import rivercogutils as utils
from redbot.core import commands
from river_mwclient.wiki_client import WikiClient
from river_mwclient.template_modifier import TemplateModifierBase

DDRAGON = "http://ddragon.leagueoflegends.com/cdn/{}/data/en_US/champion.json"

restrip = lambda x: re.sub(r'[^A-Za-z]', '', capspace(x.strip()))
capfirst = lambda x: re.sub("^.", lambda x: x.group().upper(), x)
capspace = lambda x: re.sub("\s.|^.", lambda x: x.group().upper(), x.lower())

DDRAGON_FORMAT = {
    "name": lambda d: d['name'],
    "title": lambda d: capfirst(d['title']),
    
    "resource": lambda d: d['partype'],
    "attribute": lambda d: d['tags'][0],
    "attribute2": lambda d: d['tags'][1] if len(d['tags']) > 1 else '',
    
    "hp": lambda d: d['stats']['hp'],
    "hp_lvl": lambda d: d['stats']['hpperlevel'],
    "hpregen": lambda d: d['stats']['hpregen'],
    "hpregen_lvl": lambda d: d['stats']['hpregenperlevel'],
    "mana": lambda d: d['stats']['mp'] if d['partype'] == "Mana" else '',
    "mana_lvl": lambda d: d['stats']['mpperlevel'] if d['partype'] == "Mana" else '',
    "mregen": lambda d: d['stats']['mpregen'] if d['partype'] == "Mana" else '',
    "mregen_lvl": lambda d: d['stats']['mpregenperlevel'] if d['partype'] == "Mana" else '',
    "range": lambda d: d['stats']['attackrange'],
    "ad": lambda d: d['stats']['attackdamage'],
    "ad_lvl": lambda d: d['stats']['attackdamageperlevel'],
    "as": lambda d: d['stats']['attackspeed'],
    "as_lvl": lambda d: d['stats']['attackspeedperlevel'],
    "armor": lambda d: d['stats']['armor'],
    "armor_lvl": lambda d: d['stats']['armorperlevel'],
    "mr": lambda d: d['stats']['spellblock'],
    "mr_lvl": lambda d: d['stats']['spellblockperlevel'],
    "ms": lambda d: d['stats']['movespeed'],
}


class TemplateModifier(TemplateModifierBase):
    def __init__(self, site: WikiClient, template, data, page_list=None, title_list=None,
                 limit=-1, summary=None, quiet=False, lag=0, tags=None, skip_pages=None,
                 startat_page=None):
        self.data = data
        super().__init__(site, template, page_list=page_list, title_list=title_list,
                         limit=limit, summary=summary, quiet=quiet, lag=lag, tags=tags,
                         skip_pages=skip_pages,
                         startat_page=startat_page)
    
    def update_template(self, template):
        champdata = self.data[template.get("ddragon_key").value.strip()]
        for item, func in DDRAGON_FORMAT.items():
            template.add(item, str(func(champdata)))


class PatchUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group()
    async def patchupdate(self, ctx):
        pass
    
    @patchupdate.command()
    async def championstats(self, ctx, version):
        if not re.match(r"\d+\.\d+\.\d+", version): version += ".1"
        await ctx.send("Okay, starting!")
        async with aiohttp.ClientSession() as session:
            async with session.get(DDRAGON.format(version)) as resp:
                data = json.loads(await resp.text())['data']
        async with ctx.typing():
            site = await utils.login_if_possible(ctx, self.bot, 'lol')
            self.champion_modifier = TemplateModifier(site, 'Infobox Champion', data,
                                                      summary="Champion Update").run()
        await ctx.send("Okay, done!")
