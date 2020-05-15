from redbot.core import commands
from river_mwclient.esports_client import EsportsClient
from river_mwclient.auth_credentials import AuthCredentials


class CargoCreate(commands.Cog):
	"""Creates needed pages for a new Cargo table, and also creates the Cargo table"""
	
	
	def __init__(self, bot):
		self.bot = bot
	
	@commands.command(pass_context=True)
	async def cargocreate(self, ctx, wiki, table):
		gamepedia_keys = await self.bot.get_shared_api_tokens("gamepedia")
		if gamepedia_keys.get("account") is None:
			return await ctx.send("Sorry, you haven't set a Gamepedia bot account yet.")
		username = "{}@{}".format(gamepedia_keys.get("account"), gamepedia_keys.get("bot"))
		password = gamepedia_keys.get("password")
		credentials = AuthCredentials(username=username, password=password)
		site = EsportsClient(wiki, credentials=credentials)
		await ctx.send('Okay, starting!')
		site.setup_tables(table)
		await ctx.send('Okay, done!')