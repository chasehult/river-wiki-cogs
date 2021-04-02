import asyncio
import json
import re
from functools import wraps, partial

import aiohttp
import rivercogutils as utils
from redbot.core import commands
from river_mwclient.template_modifier import TemplateModifierBase
from river_mwclient.wiki_client import WikiClient

DDRAGON_V = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON = "http://ddragon.leagueoflegends.com/cdn/{}/data/en_US/{}.json"

restrip = lambda x: re.sub(r'[^A-Za-z]', '', capspace(x.strip()))
capfirst = lambda x: re.sub(r"^.", lambda x: x.group().upper(), x)
capspace = lambda x: re.sub(r"\s.|^.", lambda x: x.group().upper(), x.lower())
ifinelse = lambda d, k: d[k] if k and k in d else ''
strperc = lambda i: '' if not i else str(int(float(i) * 100)) + "%" if float(i * 100) % 1 == 0 else str(
    float(i * 100)) + "%"


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    
    return run


DD_CHAMPION_FORMAT = {
    "name": lambda d: d['name'],
    "title": lambda d: capfirst(d['title']),
    
    "key_int": lambda d: d['key'],
    
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


def item_extras(d, t):
    usedin = []
    index = 1
    while t.has("used in " + str(index)):
        usedin.append(t.get("used in " + str(index)).value.strip())
        index += 1
    t.add("used_in", ','.join(usedin))


DD_ITEM_FORMAT = {
    "name": lambda d: d['name'],
    "item_code": lambda d: None,
    
    "ad": lambda d: ifinelse(d['stats'], 'FlatPhysicalDamageMod'),
    "ls": lambda d: strperc(ifinelse(d['stats'], 'PercentLifeStealMod')),
    "hp": lambda d: ifinelse(d['stats'], 'FlatHPPoolMod'),
    "hpregen": lambda d: ifinelse(d['stats'], 'FlatHPRegenMod'),
    "armor": lambda d: ifinelse(d['stats'], 'FlatArmorMod'),
    "mr": lambda d: ifinelse(d['stats'], 'FlatSpellBlockMod'),
    "crit": lambda d: ifinelse(d['stats'], 'FlatCritChanceMod'),
    "as": lambda d: strperc(ifinelse(d['stats'], 'PercentAttackSpeedMod')),
    # "armorpen": lambda d: ifinelse(d['stats'], ''),
    # "range": lambda d: ifinelse(d['stats'], ''),
    # "mana": lambda d: ifinelse(d['stats'], ''),
    # "manaregen": lambda d: ifinelse(d['stats'], ''),
    # "energy": lambda d: ifinelse(d['stats'], ''),
    # "energyregen": lambda d: ifinelse(d['stats'], ''),
    # "ap": lambda d: ifinelse(d['stats'], ''),
    # "cdr": lambda d: ifinelse(d['stats'], ''),
    # "spellvamp": lambda d: ifinelse(d['stats'], ''),
    # "magicpen": lambda d: ifinelse(d['stats'], ''),
    # "ms": lambda d: ifinelse(d['stats'], ''),
    # "tenacity": lambda d: ifinelse(d['stats'], ''),
    # "goldgen": lambda d: ifinelse(d['stats'], ''),
    # "onhit": lambda d: ifinelse(d['stats'], ''),
    # "bonushp": lambda d: ifinelse(d['stats'], ''),
    # "healing": lambda d: ifinelse(d['stats'], ''),
    
    "totalgold": lambda d: d['gold']['total'],
    "sold": lambda d: d['gold']['sell'],
    
    "extras": item_extras,
}

SPEC_ITEMS = ['extras']


class TemplateModifier(TemplateModifierBase):
    def __init__(self, site: WikiClient, template, data, data_format, page_list=None,
                 title_list=None, limit=-1, summary=None, quiet=False, lag=0,
                 tags=None, skip_pages=None, startat_page=None):
        self.data = data
        self.data_format = data_format
        self.tba = set()
        super().__init__(site, template, page_list=page_list, title_list=title_list,
                         limit=limit, summary=summary, quiet=quiet, lag=lag, tags=tags,
                         skip_pages=skip_pages,
                         startat_page=startat_page)
    
    @async_wrap
    def fakesync_run(self):
        self.run()
    
    def update_template(self, template):
        # key = [k for k,v in self.data.items() if v['name'] == template.get("name").value.strip()]
        # if len(key)==1:
        #     template.add("ddragon_key", key[0])
        # elif len(key)>1:
        #     print(template, key)
        if not (template.has("ddragon_key")):
            template.add('ddragon_key', template.get('name').value.strip().replace(' ', '').replace("'", ''))
        formdata = self.data.get(template.get("ddragon_key").value.strip())
        if not formdata:
            self.site.log_error_content(self.current_page.name, 'Could not load Ddragon data')
            return
        for item, func in self.data_format.items():
            if item in SPEC_ITEMS:
                continue
            newval = str(func(formdata))
            if newval:
                template.add(item, str(func(formdata)))
            elif newval is None:
                template.remove(item, True)
            # else:
            #     if template.has(item) and not template.get(item).value.strip():
            #         template.remove(item, True)
        for spec in SPEC_ITEMS:
            if spec in self.data_format:
                self.data_format[spec](self.data, template)


class PatchUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group()
    async def patchupdate(self, ctx):
        pass
    
    async def updatestats(self, ctx, version, section, formatdict):
        async with aiohttp.ClientSession() as session:
            if version is None:
                async with session.get(DDRAGON_V) as resp:
                    version = json.loads(await resp.text())[0]
            elif not re.match(r"\d+\.\d+\.\d+", version):
                version += ".1"
            await ctx.send("Okay, starting!")
            async with session.get(DDRAGON.format(version, section.lower())) as resp:
                data = json.loads(await resp.text())['data']
        async with ctx.typing():
            site = await utils.login_if_possible(ctx, self.bot, 'lol')
            tm = TemplateModifier(site, 'Infobox ' + section, data, formatdict,
                                  summary=section + " Update for " + version)
            await tm.fakesync_run()
            site.report_all_errors()
            print(tm.tba)
        print("Done")
        await ctx.send("Okay, done!")
    
    @patchupdate.command()
    async def championstats(self, ctx, version=None):
        await self.updatestats(ctx, version, "Champion", DD_CHAMPION_FORMAT)
    
    @patchupdate.command()
    async def itemstats(self, ctx, version=None):
        await self.updatestats(ctx, version, "Item", DD_ITEM_FORMAT)
