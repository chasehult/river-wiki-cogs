from .fncheckresults import FnCheckResults


def setup(bot):
    bot.add_cog(FnCheckResults(bot))
