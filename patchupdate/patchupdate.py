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


class TemplateModifier(TemplateModifierBase):
    section = "None"

    @async_wrap
    def fakesync_run(self):
        self.run()

    def update_template(self, template):
        key = [k for k, v in self.data['data'].items()
               if v.get('name') == self.current_template.get('name', '').value.strip()]
        if len(key) == 1:
            ddid = key[0]
            self.current_template.add('ddragon_key', ddid)
        else:
            self.site.log_error_content(self.current_page.name, "Duplicate or missing DDragon data")
            return

        self.format_template(ddid)

    def format_template(self, ddid):
        raise NotImplementedError()

    def put(self, key, value):
        if str(value):
            self.current_template.add(key, str(value))
        else:
            if self.current_template.has(key) and not self.current_template.get(key).value.strip():
                self.current_template.remove(key, True)


class ChampionModifier(TemplateModifier):
    section = "Champion"

    def format_template(self, ddid):
        data = self.data['data']

        self.put('name', data[ddid]['name'])
        self.put('title', capfirst(data[ddid]['title']))

        self.put('key_int', data[ddid]['key'])

        self.put('resource', data[ddid]['partype'])
        self.put('attribute', data[ddid]['tags'][0])
        self.put('attribute2', data[ddid]['tags'][1] if len(data[ddid]['tags']) > 1 else '')

        self.put('hp', data[ddid]['stats']['hp'])
        self.put('hp_lvl', data[ddid]['stats']['hpperlevel'])
        self.put('hpregen', data[ddid]['stats']['hpregen'])
        self.put('hpregen_lvl', data[ddid]['stats']['hpregenperlevel'])
        self.put('mana', data[ddid]['stats']['mp'] if data[ddid]['partype'] == 'Mana' else '')
        self.put('mana_lvl', data[ddid]['stats']['mpperlevel'] if data[ddid]['partype'] == 'Mana' else '')
        self.put('mregen', data[ddid]['stats']['mpregen'] if data[ddid]['partype'] == 'Mana' else '')
        self.put('mregen_lvl', data[ddid]['stats']['mpregenperlevel'] if data[ddid]['partype'] == 'Mana' else '')
        self.put('range', data[ddid]['stats']['attackrange'])
        self.put('ad', data[ddid]['stats']['attackdamage'])
        self.put('ad_lvl', data[ddid]['stats']['attackdamageperlevel'])
        self.put('as', data[ddid]['stats']['attackspeed'])
        self.put('as_lvl', data[ddid]['stats']['attackspeedperlevel'])
        self.put('armor', data[ddid]['stats']['armor'])
        self.put('armor_lvl', data[ddid]['stats']['armorperlevel'])
        self.put('mr', data[ddid]['stats']['spellblock'])
        self.put('mr_lvl', data[ddid]['stats']['spellblockperlevel'])
        self.put('ms', data[ddid]['stats']['movespeed'])


class ItemModifier(TemplateModifier):
    section = "Item"

    def format_template(self, ddid):
        data = self.data['data']

        self.put('name', data[ddid]['name'])
        self.put('item_code', None)

        self.put('ad', ifinelse(data[ddid]['stats'], 'FlatPhysicalDamageMod'))
        self.put('ls', strperc(ifinelse(data[ddid]['stats'], 'PercentLifeStealMod')))
        self.put('hp', ifinelse(data[ddid]['stats'], 'FlatHPPoolMod'))
        self.put('hpregen', ifinelse(data[ddid]['stats'], 'FlatHPRegenMod'))
        self.put('armor', ifinelse(data[ddid]['stats'], 'FlatArmorMod'))
        self.put('mr', ifinelse(data[ddid]['stats'], 'FlatSpellBlockMod'))
        self.put('crit', ifinelse(data[ddid]['stats'], 'FlatCritChanceMod'))
        self.put('as', strperc(ifinelse(data[ddid]['stats'], 'PercentAttackSpeedMod')))
        self.put('totalgold', data[ddid]['gold']['total'])
        self.put('sold', data[ddid]['gold']['sell'])

        items = []
        for item_id in data[ddid]['into']:
            items.append(data[item_id]['name'])
        self.put('used_in', ','.join(items))


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
            await tm.fakesync_run()
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
