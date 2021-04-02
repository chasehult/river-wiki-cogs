import asyncio
import json
import re
from functools import wraps, partial
from typing import Optional

import aiohttp
import rivercogutils as utils
from redbot.core import commands
from river_mwclient.template_modifier import TemplateModifierBase
from river_mwclient.wiki_client import WikiClient

DDRAGON_V = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON = "http://ddragon.leagueoflegends.com/cdn/{}/data/en_US/{}.json"

restrip = lambda x: re.sub(r'[^A-Za-z]', '', capspace(x.strip()))
capfirst = lambda x: re.sub(r'^.', lambda x: x.group().upper(), x)
capspace = lambda x: re.sub(r'\s.|^.', lambda x: x.group().upper(), x.lower())
ifinelse = lambda d, k: d[k] if k and k in d else ''
strperc = lambda i: '' if not i else str(int(float(i) * 100)) + '%' if float(i * 100) % 1 == 0 else str(
    float(i * 100)) + '%'


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    
    return run

class Formatter:
    @classmethod
    def format(cls, d):
        raise NotImplementedError()

    @classmethod
    def extras(cls, d, t):
        return

class ChampionFormatter(Formatter):
    @classmethod
    def format(cls, d):
        return {
            'name': d['name'],
            'title': capfirst(d['title']),

            'key_int': d['key'],

            'resource': d['partype'],
            'attribute': d['tags'][0],
            'attribute2': d['tags'][1] if len(d['tags']) > 1 else '',

            'hp': d['stats']['hp'],
            'hp_lvl': d['stats']['hpperlevel'],
            'hpregen': d['stats']['hpregen'],
            'hpregen_lvl': d['stats']['hpregenperlevel'],
            'mana': d['stats']['mp'] if d['partype'] == 'Mana' else '',
            'mana_lvl': d['stats']['mpperlevel'] if d['partype'] == 'Mana' else '',
            'mregen': d['stats']['mpregen'] if d['partype'] == 'Mana' else '',
            'mregen_lvl': d['stats']['mpregenperlevel'] if d['partype'] == 'Mana' else '',
            'range': d['stats']['attackrange'],
            'ad': d['stats']['attackdamage'],
            'ad_lvl': d['stats']['attackdamageperlevel'],
            'as': d['stats']['attackspeed'],
            'as_lvl': d['stats']['attackspeedperlevel'],
            'armor': d['stats']['armor'],
            'armor_lvl': d['stats']['armorperlevel'],
            'mr': d['stats']['spellblock'],
            'mr_lvl': d['stats']['spellblockperlevel'],
            'ms': d['stats']['movespeed'],

            'extras': cls.extras,
        }


class ItemFormatter(Formatter):
    @classmethod
    def format(cls, d):
        return {
            'name': d['name'],
            'item_code': None,

            'ad': ifinelse(d['stats'], 'FlatPhysicalDamageMod'),
            'ls': strperc(ifinelse(d['stats'], 'PercentLifeStealMod')),
            'hp': ifinelse(d['stats'], 'FlatHPPoolMod'),
            'hpregen': ifinelse(d['stats'], 'FlatHPRegenMod'),
            'armor': ifinelse(d['stats'], 'FlatArmorMod'),
            'mr': ifinelse(d['stats'], 'FlatSpellBlockMod'),
            'crit': ifinelse(d['stats'], 'FlatCritChanceMod'),
            'as': strperc(ifinelse(d['stats'], 'PercentAttackSpeedMod')),
            # 'armorpen': ifinelse(d['stats'], ''),
            # 'range': ifinelse(d['stats'], ''),
            # 'mana': ifinelse(d['stats'], ''),
            # 'manaregen': ifinelse(d['stats'], ''),
            # 'energy': ifinelse(d['stats'], ''),
            # 'energyregen': ifinelse(d['stats'], ''),
            # 'ap': ifinelse(d['stats'], ''),
            # 'cdr': ifinelse(d['stats'], ''),
            # 'spellvamp': ifinelse(d['stats'], ''),
            # 'magicpen': ifinelse(d['stats'], ''),
            # 'ms': ifinelse(d['stats'], ''),
            # 'tenacity': ifinelse(d['stats'], ''),
            # 'goldgen': ifinelse(d['stats'], ''),
            # 'onhit': ifinelse(d['stats'], ''),
            # 'bonushp': ifinelse(d['stats'], ''),
            # 'healing': ifinelse(d['stats'], ''),

            'totalgold': d['gold']['total'],
            'sold': d['gold']['sell'],

            'extras': cls.extras,
        }

    @classmethod
    def extras(cls, d, t):
        usedin = []
        index = 1
        while t.has("used in " + str(index)):
            usedin.append(t.get("used in " + str(index)).value.strip())
            index += 1
        t.add("used_in", ','.join(usedin))


SPEC_ITEMS = ['extras']


class TemplateModifier(TemplateModifierBase):
    def __init__(self, site: WikiClient, template, data, formatter, page_list=None,
                 title_list=None, limit=-1, summary=None, quiet=False, lag=0,
                 tags=None, skip_pages=None, startat_page=None):
        self.data = data
        self.formatter = formatter
        self.tba = set()
        super().__init__(site, template, page_list=page_list, title_list=title_list,
                         limit=limit, summary=summary, quiet=quiet, lag=lag, tags=tags,
                         skip_pages=skip_pages,
                         startat_page=startat_page)
    
    @async_wrap
    def fakesync_run(self):
        self.run()
    
    def update_template(self, template):
        key = [k for k,v in self.data.items() if v.get('name') == template.get('name', '').value.strip()]
        if len(key)==1:
            template.add('ddragon_key', key[0])
            data = self.formatter.format(self.data.get(key[0]))
        else:
            self.site.log_error_content(self.current_page.name, "Duplicate or missing DDragon data")
            return

        for key, value in data:
            if key in SPEC_ITEMS:
                continue
            if str(value):
                template.add(key, str(value))
            else:
                if template.has(key) and not template.get(key).value.strip():
                    template.remove(key, True)
        for spec in SPEC_ITEMS:
            if spec in data:
                data[spec](self.data, template)


class PatchUpdate(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    @commands.group()
    async def patchupdate(self, ctx):
        pass
    
    async def updatestats(self, ctx, version: Optional[str], section: str, formatter: Formatter):
        async with aiohttp.ClientSession() as session, ctx.typing():
            if version is None:
                async with session.get(DDRAGON_V) as resp:
                    version = json.loads(await resp.text())[0]
            elif not re.match(r'\d+\.\d+\.\d+', version):
                version += ".1"
            await ctx.send("Okay, starting!")
            async with session.get(DDRAGON.format(version, section.lower())) as resp:
                data = json.loads(await resp.text())['data']
            site = await utils.login_if_possible(ctx, self.bot, 'lol')
            tm = TemplateModifier(site, "Infobox " + section, data, formatter,
                                  summary=section + " Update for " + version)
            await tm.fakesync_run()
            site.report_all_errors('patchupdate')
        await ctx.send("Okay, done!")
    
    @patchupdate.command()
    async def championstats(self, ctx, version=None):
        await self.updatestats(ctx, version, 'Champion', ChampionFormatter)
    
    @patchupdate.command()
    async def itemstats(self, ctx, version=None):
        await self.updatestats(ctx, version, 'Item', ItemFormatter)
