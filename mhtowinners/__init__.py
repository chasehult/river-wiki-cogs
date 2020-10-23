from .mhtowinners import MhToWinners


def setup(bot):
    bot.add_cog(MhToWinners(bot))
