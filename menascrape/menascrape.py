from redbot.core import commands
import rivercogutils as utils
from toornament_scraper.mena_creator import MenaCreator
from toornament_scraper.mena_updater import MenaUpdater


class MenaScrape(commands.Cog):
	"""Scrapes and updates MENA events"""
	
	def __init__(self, bot):
		self.bot = bot
		self.summary = 'Moving page + associated subpages'

	@commands.command()
	async def menascrape(self, ctx, action, title):
		site = await utils.login_if_possible(ctx, self.bot, 'lol')
		await ctx.send('Okay, starting now!')
		if action == 'update':
			MenaUpdater(site, title).run()
		elif action == 'create':
			MenaCreator(site, title).run()
		else:
			await ctx.send('Sorry, unknown action!')
		await ctx.send('Okay, done!')
