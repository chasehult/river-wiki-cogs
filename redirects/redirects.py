from redbot.core import commands
from esportswiki_editing import login, EsportsSite
import rivercogutils as utils
import mwparserfromhell, re


class Redirects(commands.Cog):
	"""Discovers & updates scoreboards on Leaguepedia that are missing vods"""
	
	def __init__(self, bot):
		self.bot = bot
		self.summary = 'Fixing double redirect'
	
	@commands.group(pass_context=True)
	async def redirects(self, ctx):
		pass
	
	@redirects.command(pass_context=True)
	async def double(self, ctx, wiki):
		site = await utils.login_if_possible(ctx, self.bot, wiki)
		if site is None:
			return
		result = site.api(action="query", list="querypage", qppage="DoubleRedirects")
		for item in result['query']['querypage']['results']:
			source_page = site.pages[item['title']]
			target_title = item['databaseResult']['c_title']
			source_page.save('#redirect[[%s]]' % target_title)
		return await ctx.send("Okay, should be done!")
