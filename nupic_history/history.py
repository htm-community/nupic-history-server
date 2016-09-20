from nupic_history.sp_facade import SpFacade
from nupic_history.tm_facade import TmFacade
from nupic_history.redis_client import RedisClient


class NupicHistory(object):


  def __init__(self):
    """
    Provides top-level control over the SP History Facades.
    """
    # TODO: Provide way for user to specific Redis connection details.
    self._redisClient = RedisClient()


  def list(self):
    """
    Gets all the SpFacades that have history in Redis.
    :return: [SpFacade[]]
    """
    return [
      SpFacade(spid, self._redisClient)
      for spid in self._redisClient.listSpIds()
    ]


  def createSpFacade(self, sp, save=None, modelId=None):
    """
    Creates a new active SP Facade for the given SP. Does not actually save
    anything yet.
    :param modelId: (string) pre-defined model id
    :param sp: SpatialPooler instance
    :param save: list of Snapshots to save with each compute step
    :return: [SpFacade] complete with a default redis client
    """
    return SpFacade(sp, self._redisClient, save=save, modelId=modelId)


  def getSpFacade(self, spId):
    """
    Get an inactive SP Facade by id, which can be used to playback the SP
    history.
    :param spId:
    :return: [SpFacade]
    """
    return SpFacade(spId, self._redisClient)


  def createTmFacade(self, tm, save=None, modelId=None):
    """
    Creates a new active TM Facade for the given TM. Does not actually save
    anything yet.
    :param modelId: (string) pre-defined model id
    :param tm: TemporalMemory instance
    :param save: list of Snapshots to save with each compute step
    :return: [SpFacade] complete with a default redis client
    """
    return TmFacade(tm, self._redisClient, save=save, modelId=modelId)


  def getTmFacade(self, tmId):
    """
    Get an inactive TM Facade by id, which can be used to playback the TM
    history.
    :param tmId:
    :return: [TmFacade]
    """
    return TmFacade(tmId, self._redisClient)


  def nuke(self):
    """
    Removes all traces of NuPIC History from Redis.
    :return:
    """
    self._redisClient.nuke()
