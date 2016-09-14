from nupic_history.sp_facade import SpFacade
from nupic_history.sp_redis_client import SpRedisClient


class NupicHistory(object):


  def __init__(self):
    """
    Provides top-level control over the SP History Facades.
    """
    # TODO: Provide way for user to specific Redis connection details.
    self._redisClient = SpRedisClient()


  def list(self):
    """
    Gets all the SpFacades that have history in Redis.
    :return: [SpFacade[]]
    """
    return [
      SpFacade(spid, self._redisClient)
      for spid in self._redisClient.listSpIds()
    ]


  def create(self, sp, save=None):
    """
    Creates a new active SP Facade for the given SP. Does not actually save
    anything yet.
    :param sp: SpatialPooler instance
    :param save: list of Snapshots to save with each compute step
    :return: [SpFacade] complete with a default redis client
    """
    return SpFacade(sp, self._redisClient, save=save)


  def get(self, spId):
    """
    Get an inactive SP Facade by id, which can be used to playback the SP
    history.
    :param spId:
    :return: [SpFacade]
    """
    return SpFacade(spId, self._redisClient)


  def nuke(self):
    """
    Removes all traces of SP History from Redis.
    :return:
    """
    self._redisClient.nuke()
