from redbot.core import commands
import rivercogutils as utils
from .menascrape_main import MenaScraper


class MenaScrape(commands.Cog):
	"""Scrapes and updates MENA events"""
	
	def __init__(self, bot):
		self.bot = bot
		self.summary = 'Moving page + associated subpages'

	@commands.command()
	async def menascrape(self, ctx, title):
		site = await utils.login_if_possible(ctx, self.bot, 'lol')
		await ctx.send('Okay, starting now!')
		MenaScraper(site, title).run()
		await ctx.send('Okay, done!')
