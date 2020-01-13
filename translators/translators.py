from redbot.core import commands, Config, checks
import itertools


class Translators(commands.Cog):
	"""Keeps track of users who can provide translation help for Leaguepedia"""
	
	def __init__(self, bot):
		self.bot = bot
		self.config = Config.get_conf(self, identifier=1700)
		default_global = {
			"languages": {},
			"translators": {}
		}
		self.config.register_global(**default_global)
	
	@commands.group(pass_context=True)
	async def translators(self, ctx):
		pass
	
	@translators.command(pass_context=True)
	@checks.is_owner()
	async def resetall(self, ctx, to_reset):
		if to_reset == 'all' or to_reset == 'translators':
			await self.config.translators.set({})
		if to_reset == 'all' or to_reset == 'languages':
			await self.config.languages.set({})
		await ctx.send('Ok, I deleted all translation & language info! I hope you didn\'t run this in prod on accident!')
	
	# Commands for managing languages
	@translators.command(pass_context=True)
	async def addlanguage(self, ctx, short, long):
		"""Adds a language
		"""
		languages = await self.config.languages()
		if short.lower() in languages:
			await ctx.send("That language is already recognized! You can edit with editlanguage")
			return
		languages[short.lower()] = long.lower()
		languages[long.lower()] = long.lower()
		await self.config.languages.set(languages)
		await ctx.send('ok! done')
	
	@translators.command(pass_context=True)
	async def editlanguage(self, ctx, short, long):
		"""Edits a language. Expects 2 params, short name & long name.
		
		All short names associated to the same long name may be used interchangeably (along with the long name)
		"""
		languages = await self.config.languages()
		if short.lower() not in languages:
			await ctx.send("That language is not recognized! You can add with addlanguage")
			return
		languages[short.lower()] = long.lower()
		await self.config.languages.set(languages)
		await ctx.send('ok! done')
		
	@translators.command(pass_context=True)
	async def rmlanguage(self, ctx, short):
		"""Removes a language
		"""
		languages = await self.config.languages()
		if short.lower() not in languages:
			await ctx.send("That language is not recognized! Maybe it was already deleted")
			return
		long = languages[short.lower()]
		languages.pop(short.lower())
		if long == short.lower():
			remaining_entries = [_ for _ in languages if languages[_] == long]
			await self.config.languages.set(languages)
			if len(remaining_entries) > 0:
				await ctx.send("ok! done! But there's still {} more entires for {}: {}".format(
					len(remaining_entries),
					long,
					' '.join(remaining_entries)
				))
				return
			await ctx.send('ok! done!')
			return
		await self.config.languages.set(languages)
		await ctx.send('ok! done!')
	
	@translators.command(pass_context=True)
	async def languages(self, ctx):
		"""Lists all languages
		"""
		languages = await self.config.languages()
		languages_by_group = {}
		language_groups = []
		for k, v in languages.items():
			if v not in languages_by_group.keys():
				languages_by_group[v] = []
				language_groups.append(v)
			languages_by_group[v].append(k)
		language_groups.sort()
		printed_language_groups = ['{}: {}'.format(
			lang,
			', '.join(sorted(languages_by_group[lang]))
		) for lang in language_groups]
		output_string = "\n".join(printed_language_groups)
		await ctx.send(output_string)
	
	# Commands for managing translators
	@translators.command(pass_context=True)
	async def itranslate(self, ctx, lang_input):
		"""Adds a user as a translator for a language
		"""
		languages = await self.config.languages()
		if lang_input.lower() not in languages:
			await ctx.send("Sorry, that language isn't recognized. An admin can add it for you using [p]addlanguage")
			return
		language = languages[lang_input.lower()]
		translators = await self.config.translators()
		if language not in translators:
			translators[language] = []
		author_id = ctx.author.id
		translators[language].append(author_id)
		await self.config.translators.set(translators)
		await ctx.send('Okay, added you as a translator for {}'.format(languages[language]))
	
	@translators.command(pass_context=True)
	async def idonttranslate(self, ctx, lang_input):
		"""Adds a user as a translator for a language
		"""
		languages = await self.config.languages()
		if lang_input.lower() not in languages:
			await ctx.send("Sorry, that language isn't recognized. An admin can add it for you using [p]addlanguage")
			return
		language = languages[lang_input.lower()]
		translators = await self.config.translators()
		author_id = ctx.author.id
		if language not in translators or author_id not in translators[language]:
			await ctx.send("Actually, you already aren't registered for {}".format(language))
			return
		translators[language].remove(author_id)
		await self.config.translators.set(translators)
		await ctx.send('Okay, removed you as a translator for {}'.format(languages[language]))
	
	# Usage command
	@translators.command(pass_context=True)
	async def helpme(self, ctx, lang_input):
		languages = await self.config.languages()
		if lang_input.lower() not in languages:
			await ctx.send('Sorry, that language isn\'t recognized! Maybe you are misspelling it?')
			return
		language = languages[lang_input.lower()]
		all_translators = await self.config.translators()
		if language not in all_translators or len(all_translators[language]) == 0:
			await ctx.send("Sorry, there aren't any registered translators for {}".format(language))
			return
		language_translators = all_translators[language]
		message = ' '.join(['<@{}>'.format(_) for _ in language_translators])
		await ctx.send("""<@{}> is requesting translation help for {} for Leaguepedia! Can one of you help? {}
		To stop receiving pings, type ```^translators idonttranslate {}```
						"""
						.format(
							ctx.author.id,
							language,
							message,
							language
						))
