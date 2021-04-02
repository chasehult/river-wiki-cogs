import asyncio
import json
import re
from functools import wraps, partial
from typing import Optional, Type, Callable, List

import aiohttp
import rivercogutils as utils
from redbot.core import commands
from river_mwclient.template_modifier import TemplateModifierBase
from river_mwclient.wiki_client import WikiClient

DDRAGON_V = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON = "http://ddragon.leagueoflegends.com/cdn/{}/data/en_US/{}.json"


def capspace(s):
    """Capitalize each word in a string"""
    return re.sub(r'\s.|^.', lambda x: x.group().upper(), s.lower())


def restrip(s):
    """Remove non-alpha characters from a string"""
    return re.sub(r'[^A-Za-z]', '', capspace(s.strip()))


def capfirst(s):
    """Capitalize the very first character of a string"""
    return re.sub(r'^.', lambda x: x.group().upper(), s)


def ifinelse(d, k):
    """Return d[k] only if d exists in k, otherwise return an empty string"""
    return d[k] if k and k in d else ''


def strperc(i):
    """Nicely turn a decimal into a percent"""
    if not i:
        return ''
    elif float(i * 100) % 1 == 0:
        return str(int(float(i) * 100)) + '%'
    else:
        return str(float(i * 100)) + '%'


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


class Formatter:
    def __init__(self, data):
        self.data = data

    def format(self):
        raise NotImplementedError()


class ChampionFormatter(Formatter):
    def format(self):
        return {
            'name': self.data['name'],
            'title': capfirst(self.data['title']),

            'key_int': self.data['key'],

            'resource': self.data['partype'],
            'attribute': self.data['tags'][0],
            'attribute2': self.data['tags'][1] if len(self.data['tags']) > 1 else '',

            'hp': self.data['stats']['hp'],
            'hp_lvl': self.data['stats']['hpperlevel'],
            'hpregen': self.data['stats']['hpregen'],
            'hpregen_lvl': self.data['stats']['hpregenperlevel'],
            'mana': self.data['stats']['mp'] if self.data['partype'] == 'Mana' else '',
            'mana_lvl': self.data['stats']['mpperlevel'] if self.data['partype'] == 'Mana' else '',
            'mregen': self.data['stats']['mpregen'] if self.data['partype'] == 'Mana' else '',
            'mregen_lvl': self.data['stats']['mpregenperlevel'] if self.data['partype'] == 'Mana' else '',
            'range': self.data['stats']['attackrange'],
            'ad': self.data['stats']['attackdamage'],
            'ad_lvl': self.data['stats']['attackdamageperlevel'],
            'as': self.data['stats']['attackspeed'],
            'as_lvl': self.data['stats']['attackspeedperlevel'],
            'armor': self.data['stats']['armor'],
            'armor_lvl': self.data['stats']['armorperlevel'],
            'mr': self.data['stats']['spellblock'],
            'mr_lvl': self.data['stats']['spellblockperlevel'],
            'ms': self.data['stats']['movespeed'],
        }


class ItemFormatter(Formatter):
    def format(self):
        return {
            'name': self.data['name'],
            'item_code': None,

            'ad': ifinelse(self.data['stats'], 'FlatPhysicalDamageMod'),
            'ls': strperc(ifinelse(self.data['stats'], 'PercentLifeStealMod')),
            'hp': ifinelse(self.data['stats'], 'FlatHPPoolMod'),
            'hpregen': ifinelse(self.data['stats'], 'FlatHPRegenMod'),
            'armor': ifinelse(self.data['stats'], 'FlatArmorMod'),
            'mr': ifinelse(self.data['stats'], 'FlatSpellBlockMod'),
            'crit': ifinelse(self.data['stats'], 'FlatCritChanceMod'),
            'as': strperc(ifinelse(self.data['stats'], 'PercentAttackSpeedMod')),
            'totalgold': self.data['gold']['total'],
            'sold': self.data['gold']['sell'],

            'used_in': ','.join(self.data['into'])
        }


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
        key = [k for k, v in self.data.items() if v.get('name') == template.get('name', '').value.strip()]
        if len(key) == 1:
            template.add('ddragon_key', key[0])
            data = self.formatter(self.data.get(key[0])).format()
        else:
            self.site.log_error_content(self.current_page.name, "Duplicate or missing DDragon data")
            return

        for key, value in data:
            if str(value):
                template.add(key, str(value))
            else:
                if template.has(key) and not template.get(key).value.strip():
                    template.remove(key, True)
        for meth in self.formatter.EXTRA_METHODS:
            meth(self.data, template)


class PatchUpdate(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.group()
    async def patchupdate(self, ctx):
        pass

    async def updatestats(self, ctx, version: Optional[str], section: str, formatter: Type[Formatter]):
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
