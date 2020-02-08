from .redirects import Redirects


def setup(bot):
	bot.add_cog(Redirects(bot))
