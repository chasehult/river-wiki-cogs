from redbot.core import commands
from river_mwclient.esports_client import EsportsClient
from river_mwclient.auth_credentials import AuthCredentials
from vodstosb.vodstosb_main import VodsToSbRunner

class VodsToSb(commands.Cog):
	"""Discovers & updates scoreboards on Leaguepedia that are missing vods"""
	
	def __init__(self, bot):
		self.bot = bot
		self.vod_params = ['VodPB', 'VodGameStart', 'Vod', 'VodPostgame']
		self.pages_to_save = {}
	
	@commands.command(pass_context=True)
	async def vodstosb(self, ctx):
		gamepedia_keys = await self.bot.get_shared_api_tokens("gamepedia")
		if gamepedia_keys.get("account") is None:
			return await ctx.send("Sorry, you haven't set a Gamepedia bot account yet.")
		username = "{}@{}".format(gamepedia_keys.get("account"), gamepedia_keys.get("bot"))
		password = gamepedia_keys.get("password")
		credentials = AuthCredentials(username=username, password=password)
		site = EsportsClient('lol', credentials=credentials)
		await ctx.send('Okay, starting!')
		VodsToSbRunner(site, self.vod_params).run()
		await ctx.send('Okay, done!')