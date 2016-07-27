from nupic_history.sp_facade import SpFacade
from nupic_history.sp_redis_client import SpRedisClient


class SpHistory(object):


  def __init__(self):
    self._redisClient = SpRedisClient()


  def create(self, sp):
    return SpFacade(sp, self._redisClient)


  def get(self, spId):
    return SpFacade(spId, self._redisClient)


  def nuke(self):
    self._redisClient.nuke()
