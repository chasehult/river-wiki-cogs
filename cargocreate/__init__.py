from .cargocreate import CargoCreate


def setup(bot):
    bot.add_cog(CargoCreate(bot))
