from redbot.core import commands
import rivercogutils as utils
import logging
from mhtowinners.mhtowinners_main import MhToWinnersRunner

class MhToWinners(commands.Cog):
	"""Discovers & updates scoreboards on Leaguepedia that are missing vods"""
	
	def __init__(self, bot):
		self.bot = bot
	
	@commands.command(pass_context=True)
	async def mhtowinners(self, ctx):
		site = await utils.login_if_possible(ctx, self.bot, 'lol')

		await ctx.send('Okay, starting now!')
		MhToWinnersRunner(site).run()
		await ctx.send('Okay, done!')