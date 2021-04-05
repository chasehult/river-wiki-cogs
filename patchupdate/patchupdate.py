import asyncio
import json
import re
from functools import wraps, partial
from typing import Optional, Type

import aiohttp
import rivercogutils as utils
from redbot.core import commands
from mwrogue.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient
from mwcleric.template_modifier import TemplateModifierBase
from mwcleric.wiki_client import WikiClient

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
    def __init__(self, ddid, data):
        self.ddid = ddid
        self.data = data

    def format(self):
        raise NotImplementedError()

    @property
    def stats(self):
        return self.data[self.ddid]


class ChampionFormatter(Formatter):
    def format(self):
        return {
            'name': self.stats['name'],
            'title': capfirst(self.stats['title']),

            'key_int': self.stats['key'],

            'resource': self.stats['partype'],
            'attribute': self.stats['tags'][0],
            'attribute2': self.stats['tags'][1] if len(self.stats['tags']) > 1 else '',

            'hp': self.stats['stats']['hp'],
            'hp_lvl': self.stats['stats']['hpperlevel'],
            'hpregen': self.stats['stats']['hpregen'],
            'hpregen_lvl': self.stats['stats']['hpregenperlevel'],
            'mana': self.stats['stats']['mp'] if self.stats['partype'] == 'Mana' else '',
            'mana_lvl': self.stats['stats']['mpperlevel'] if self.stats['partype'] == 'Mana' else '',
            'mregen': self.stats['stats']['mpregen'] if self.stats['partype'] == 'Mana' else '',
            'mregen_lvl': self.stats['stats']['mpregenperlevel'] if self.stats['partype'] == 'Mana' else '',
            'range': self.stats['stats']['attackrange'],
            'ad': self.stats['stats']['attackdamage'],
            'ad_lvl': self.stats['stats']['attackdamageperlevel'],
            'as': self.stats['stats']['attackspeed'],
            'as_lvl': self.stats['stats']['attackspeedperlevel'],
            'armor': self.stats['stats']['armor'],
            'armor_lvl': self.stats['stats']['armorperlevel'],
            'mr': self.stats['stats']['spellblock'],
            'mr_lvl': self.stats['stats']['spellblockperlevel'],
            'ms': self.stats['stats']['movespeed'],
        }


class ItemFormatter(Formatter):
    def format(self):
        return {
            'name': self.stats['name'],
            'item_code': None,

            'ad': ifinelse(self.stats['stats'], 'FlatPhysicalDamageMod'),
            'ls': strperc(ifinelse(self.stats['stats'], 'PercentLifeStealMod')),
            'hp': ifinelse(self.stats['stats'], 'FlatHPPoolMod'),
            'hpregen': ifinelse(self.stats['stats'], 'FlatHPRegenMod'),
            'armor': ifinelse(self.stats['stats'], 'FlatArmorMod'),
            'mr': ifinelse(self.stats['stats'], 'FlatSpellBlockMod'),
            'crit': ifinelse(self.stats['stats'], 'FlatCritChanceMod'),
            'as': strperc(ifinelse(self.stats['stats'], 'PercentAttackSpeedMod')),
            'totalgold': self.stats['gold']['total'],
            'sold': self.stats['gold']['sell'],

            'used_in': self.get_used_in()
        }

    def get_used_in(self):
        items = []
        for item_id in self.stats['into']:
            items.append(self.data[item_id]['name'])
        return ','.join(items)


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
            data = self.formatter(key[0], self.data).format()
        else:
            self.site.log_error_content(self.current_page.name, "Duplicate or missing DDragon data")
            return

        for key, value in data.items():
            if str(value):
                template.add(key, str(value))
            else:
                if template.has(key) and not template.get(key).value.strip():
                    template.remove(key, True)


class PatchUpdate(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.group()
    async def patchupdate(self, ctx):
        pass

    @staticmethod
    async def updatestats(site: WikiClient, section: str, formatter: Type[Formatter], version: Optional[str] = None):
        async with aiohttp.ClientSession() as session:
            if version is None:
                async with session.get(DDRAGON_V) as resp:
                    version = json.loads(await resp.text())[0]
            elif not re.match(r'\d+\.\d+\.\d+', version):
                version += ".1"
            async with session.get(DDRAGON.format(version, section.lower())) as resp:
                data = json.loads(await resp.text())['data']
            tm = TemplateModifier(site, "Infobox " + section, data, formatter,
                                  summary=section + " Update for " + version)
            await tm.fakesync_run()
            site.report_all_errors('patchupdate')

    @patchupdate.command()
    async def championstats(self, ctx, version=None):
        await ctx.send("Okay, starting!")
        site = await utils.login_if_possible(ctx, self.bot, 'lol')
        async with ctx.typing():
            await self.updatestats(site, 'Champion', ChampionFormatter, version)
        await ctx.send("Okay, done!")

    @patchupdate.command()
    async def itemstats(self, ctx, version=None):
        await ctx.send("Okay, starting!")
        site = await utils.login_if_possible(ctx, self.bot, 'lol')
        async with ctx.typing():
            await self.updatestats(site, 'Item', ItemFormatter, version)
        await ctx.send("Okay, done!")


if __name__ == "__main__":
    lolsite = EsportsClient('lol', credentials=AuthCredentials(user_file='me'))
    asyncio.run(PatchUpdate.updatestats(lolsite, 'Champion', ChampionFormatter))
    # asyncio.run(PatchUpdate.updatestats(lolsite, 'Item', ItemFormatter))
