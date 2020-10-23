from .menascrape import MenaScrape


def setup(bot):
    bot.add_cog(MenaScrape(bot))
