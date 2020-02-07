from redbot.core import commands
from esportswiki_editing import login
import mwparserfromhell, re


class VodsToSb(commands.Cog):
	"""Discovers & updates scoreboards on Leaguepedia that are missing vods"""
	
	def __init__(self, bot):
		self.bot = bot
		self.summary = 'Discover & auto-add vods to SB'
		self.vod_params = ['vodpb', 'vodstart', 'vod']
	
	@commands.command(pass_context=True)
	async def vodstosb(self, ctx):
		gamepedia_keys = await self.bot.get_shared_api_tokens("gamepedia")
		if gamepedia_keys.get("account") is None:
			return await ctx.send("Sorry, you haven't set a Gamepedia bot account yet.")
		username = "{}@{}".format(gamepedia_keys.get("account"), gamepedia_keys.get("bot"))
		password = gamepedia_keys.get("password")
		site = login('me', 'lol', username=username, pwd=password)
		await ctx.send('Okay, starting!')
		result = site.cargoquery(
			tables="MatchScheduleGame=MSG,ScoreboardGame=SG",
			join_on="MSG.ScoreboardID_Wiki=SG.ScoreboardID_Wiki",
			where="SG.VOD IS NULL AND SG._pageName IS NOT NULL AND (MSG.Vod IS NOT NULL OR MSG.VodPostgame IS NOT NULL OR MSG.VodPB IS NOT NULL) AND MSG.MatchHistory IS NOT NULL",
			fields="SG._pageName=SBPage,MSG._pageName=MSGPage",
			group_by="SG._pageName",
			limit=5000
		)
		
		for item in result:
			self.process_pages(site, item['MSGPage'], item['SBPage'])
		await ctx.send('Okay, done!')
		
	def process_pages(self, site, data_page_name, sb_page_name):
		data_page = site.pages[data_page_name]
		data_text = data_page.text()
		data_wikitext = mwparserfromhell.parse(data_text)
		sb_page = site.pages[sb_page_name]
		sb_text = sb_page.text()
		sb_wikitext = mwparserfromhell.parse(sb_text)
		for template in sb_wikitext.filter_templates():
			if template.has('statslink'):
				mh = template.get('statslink').value.strip()
				re_match = re.search(r'match-details/([A-Za-z0-9]+/[0-9]+)', mh)
				if not re_match:
					continue
				match_id = re_match[1]
				print(match_id)
				for tl in data_wikitext.filter_templates():
					if tl.has('mh'):
						if match_id in tl.get('mh').value.strip():
							for vod in self.vod_params:
								if tl.has(vod) and tl.get(vod).value.strip() != '':
									print('has: %s' % vod)
									self.add_vod(template, tl, vod)
									break
							break
		if str(sb_wikitext) != sb_text:
			sb_page.save(str(sb_wikitext), summary=self.summary)
		
	@staticmethod
	def data_suffix(n):
		if n == 1:
			return ''
		return '/' + str(n)

	@staticmethod
	def add_vod(template, tl, arg):
		template.add('vodlink', tl.get(arg).value.strip())
