from redbot.core import commands
import rivercogutils as utils
from toornament_scraper.mena_creator import MenaCreator
from toornament_scraper.mena_updater import MenaUpdater


class MenaScrape(commands.Cog):
	"""Scrapes and updates MENA events."""
	
	def __init__(self, bot):
		self.bot = bot
		self.summary = 'Moving page + associated subpages'

	@commands.group()
	async def menascrape(self, ctx):
		"""Scrapes and updates MENA events from Toornament website"""
	
	@menascrape.command()
	async def create(self, ctx, *, title):
		"""Creates MatchSchedule code that you can then copy to Data namespace"""
		site = await utils.login_if_possible(ctx, self.bot, 'lol')
		await ctx.send('Okay, starting now!')
		page_updated = MenaCreator(site, title).run()
		await ctx.send('Okay, done! See page <{}>'.format(page_updated))
	
	@menascrape.command()
	async def update(self, ctx, *, title):
		"""Updates a live Data namespace page in place"""
		site = await utils.login_if_possible(ctx, self.bot, 'lol')
		await ctx.send('Okay, starting now!')
		page_updated = MenaUpdater(site, title).run()
		await ctx.send('Okay, done! See page <{}>'.format(page_updated))
