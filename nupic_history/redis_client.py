import sys
import time
import msgpack

import redis

from nupic_history import SpSnapshots as SP_SNAPS



class RedisClient(object):

  # Redis keys.
  MODEL_LIST = "model_list"
  SP_PARAMS = "{}_sp_params"          # spid
  TM_PARAMS = "{}_tm_params"          # tmid
  SP_POT_POOLS = "{}_potentialPools"  # spid
  SP_INH_MASKS = "{}_inhibitionMasks" # spid
  GLOBAL_VALS = "{}_{}_{}"            # spid, iteration, storage type
  COLUMN_VALS = "{}_{}_col-{}_{}"     # spid, iteration, column index,
                                      # storage type

  def __init__(self, host="localhost", port=6379):
    self._redis = redis.Redis(host=host, port=port)


  def listSpIds(self):
    return msgpack.loads(self._redis.get(self.MODEL_LIST))["sps"]


  def saveSpState(self, spid, spParams, iteration, state):
    start = time.time() * 1000

    self._updateSpRegistry(spid, spParams)
    bytesSaved = 0
    bytesSaved += self._saveSpLayerValues(state, spid, iteration)
    bytesSaved += self._saveSpColumnPermanences(state, spid, iteration)
    bytesSaved += self._saveSpPotentialPools(state, spid)
    bytesSaved += self._saveSpColumnInhibitionMasks(state, spid)

    end = time.time() * 1000
    print "SP {} iteration {} state serialization of {} bytes took {} ms".format(
      spid, iteration, bytesSaved, (end - start)
    )


  def saveTmState(self, tmid, tmParams, iteration, state):
    start = time.time() * 1000

    self._updateTmRegistry(tmid, tmParams)
    bytesSaved = 0
    bytesSaved += self._saveSpLayerValues(state, tmid, iteration)
    bytesSaved += self._saveSpColumnPermanences(state, tmid, iteration)
    bytesSaved += self._saveSpPotentialPools(state, tmid)
    bytesSaved += self._saveSpColumnInhibitionMasks(state, tmid)

    end = time.time() * 1000
    print "TM {} iteration {} state serialization of {} bytes took {} ms".format(
      tmid, iteration, bytesSaved, (end - start)
    )


  def nuke(self):
    # Nukes absolutely all data saved about SP instances.
    rds = self._redis
    models = rds.get(self.MODEL_LIST)
    deleted = 0
    if models is not None:
      models = msgpack.loads(models)["models"]
      for modelId in models:
        deleted += self.delete(modelId)
      deleted += rds.delete(self.MODEL_LIST)
    print "Deleted {} Redis keys.".format(deleted)


  def delete(self, modelId):
    rds = self._redis
    deleted = 0
    print "deleting model {}".format(modelId)
    doomed = rds.keys("{}*".format(modelId))
    for key in doomed:
      deleted += rds.delete(key)
    # Also remove the registry entry
    modelList = msgpack.loads(rds.get(self.MODEL_LIST))
    models = modelList["models"]
    doomed = models.index(modelId)
    del models[doomed]
    rds.set(self.MODEL_LIST, msgpack.dumps(modelList))
    return deleted


  def getSpParams(self, modelId):
    params = msgpack.loads(self._redis.get(self.SP_PARAMS.format(modelId)))
    return params["params"]


  def getTmParams(self, modelId):
    params = msgpack.loads(self._redis.get(self.TM_PARAMS.format(modelId)))
    return params["params"]


  def getMaxIteration(self, modelId):
    rds = self._redis
    maxIteration = 0
    # We will use active columns keys to find the max iteration.
    keys = rds.keys("{}_?_activeColumns".format(modelId))
    if len(keys) > 0:
      maxIteration = max([int(key.split("_")[1]) for key in keys])
    return maxIteration


  def getLayerStateByIteration(self, modelId, stateType, iteration):
    key = self.GLOBAL_VALS.format(modelId, iteration, stateType)
    return self._getSnapshot(stateType, key)


  def getActiveColumnsByColumn(self, modelId, columnIndex, maxIteration):
    out = []
    searchKey = self.GLOBAL_VALS.format(modelId, "*", SP_SNAPS.ACT_COL)
    keys = self._redis.keys(searchKey)
    for iteration in xrange(0, maxIteration):
      possibleKey = self.GLOBAL_VALS.format(modelId, iteration, SP_SNAPS.ACT_COL)
      found = None
      if possibleKey in keys:
        activeColumns = self._getSnapshot(SP_SNAPS.ACT_COL, possibleKey)
        if columnIndex in activeColumns["indices"]:
          found = 1
        else:
          found = 0
      else:
        print "** WARNING ** Missing {} data for column {} iteration {} (key: {})"\
          .format(SP_SNAPS.ACT_COL, columnIndex, iteration, possibleKey)
      out.append(found)
    return out


  def getStateByIteration(self, modelId, stateType, iteration, numColumns):
    out = []
    # Before making a DB call for every column, let's ensure that there are
    # values stored for this type of snapshot.
    numKeys = len(self._redis.keys(
      self.COLUMN_VALS.format(modelId, "*", "*", stateType)
    ))
    if numKeys > 0:
      for columnIndex in xrange(0, numColumns):
        key = self.COLUMN_VALS.format(modelId, iteration, columnIndex, stateType)
        column = self._getSnapshot(stateType, key)
        out.append(column)
    return out


  def getStatebyColumn(self, modelId, stateType, columnIndex, maxIteration):
    out = []
    searchString = self.COLUMN_VALS.format(modelId, "*", columnIndex, stateType)
    keys = self._redis.keys(searchString)
    for iteration in xrange(0, maxIteration):
      possibleKey = self.COLUMN_VALS.format(
        modelId, iteration, columnIndex, stateType
      )
      found = None
      if possibleKey in keys:
        found = self._getSnapshot(stateType, possibleKey)
      else:
        print "** WARNING ** Missing {} data for column {} iteration {} (key: {})"\
          .format(stateType, columnIndex, iteration, possibleKey)
      out.append(found)
    return out


  def getPotentialPools(self, modelId):
    return self._getSnapshot(SP_SNAPS.POT_POOLS, self.SP_POT_POOLS.format(modelId))


  def _getSnapshot(self, stateType, key):
    raw = self._redis.get(key)
    out = []
    if raw is not None:
      out = msgpack.loads(raw)[stateType]
    return out


  def _saveSpLayerValues(self, state, modelId, iteration):
    # Active columns and inputs are small, and can be saved in one key for
    # each time step.
    bytesSaved = 0
    # These are always SDRS, so they can be compressed.
    # (Caveat: sometimes the input array is not sparse, but whatevs.)
    for outType in [SP_SNAPS.ACT_COL, SP_SNAPS.INPUT]:
      if outType in state.keys():
        key = self.GLOBAL_VALS.format(modelId, iteration, outType)
        payload = dict()
        payload[outType] = state[outType]
        bytesSaved += self._saveObject(key, payload)
    # Overlaps and duty cycles cannot be compressed.
    for outType in [SP_SNAPS.ACT_DC, SP_SNAPS.OVP_DC, SP_SNAPS.OVERLAPS]:
      if outType in state.keys():
        key = self.GLOBAL_VALS.format(modelId, iteration, outType)
        payload = dict()
        payload[outType] = state[outType]
        bytesSaved += self._saveObject(key, payload)
    return bytesSaved


  def _saveSpColumnPermanences(self, state, modelId, iteration):
    # Permanences are big, so we save them in one key per column for easier
    # extraction by either column or iteration later.
    bytesSaved = 0
    if SP_SNAPS.PERMS in state.keys():
      perms = state[SP_SNAPS.PERMS]
      for columnIndex, permanences in enumerate(perms):
        key = self.COLUMN_VALS.format(modelId, iteration, columnIndex, SP_SNAPS.PERMS)
        payload = dict()
        payload[SP_SNAPS.PERMS] = permanences
        bytesSaved += self._saveObject(key, payload)
    return bytesSaved



  def _saveSpPotentialPools(self, state, modelId):
    # Potental pool span columns, but they don't change over time. So we check
    # to see if we've saved it before.
    bytesSaved = 0
    if SP_SNAPS.POT_POOLS in state.keys():
      key = self.SP_POT_POOLS.format(modelId)
      if len(self._redis.keys(key)) == 0:
        payload = dict()
        payload[SP_SNAPS.POT_POOLS] = state[SP_SNAPS.POT_POOLS]
        bytesSaved += self._saveObject(key, payload)
    return bytesSaved



  def _saveSpColumnInhibitionMasks(self, state, modelId):
    # Inhibition masks span columns, but they don't change over time. So we
    # check to see if we've saved it before.
    bytesSaved = 0
    if SP_SNAPS.INH_MASKS in state.keys():
      key = self.SP_INH_MASKS.format(modelId)
      if len(self._redis.keys(key)) == 0:
        payload = dict()
        payload[SP_SNAPS.INH_MASKS] = state[SP_SNAPS.INH_MASKS]
        bytesSaved += self._saveObject(key, payload)
    return bytesSaved



  def _updateRegistry(self, modelId):
    models = self._redis.get(self.MODEL_LIST)
    if models is None:
      models = {"models": [modelId]}
    else:
      models = msgpack.loads(models)
      if modelId not in models["models"]:
        models["models"].append(modelId)
    self._saveObject(self.MODEL_LIST, models)



  def _updateSpRegistry(self, modelId, spParams):
    self._updateRegistry(modelId)
    self._saveObject(self.SP_PARAMS.format(modelId), {
      "params": spParams
    })



  def _updateTmRegistry(self, modelId, tmParams):
    self._updateRegistry(modelId)
    self._saveObject(self.TM_PARAMS.format(modelId), {
      "params": tmParams
    })



  def _saveObject(self, key, obj):
    msgpackString = msgpack.dumps(obj)
    size = sys.getsizeof(msgpackString)
    self._redis.set(key, msgpackString)
    return size
