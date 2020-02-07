from .vodstosb import VodsToSb


def setup(bot):
	bot.add_cog(VodsToSb(bot))
