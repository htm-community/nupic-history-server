import sys
import time
import msgpack

import redis

from nupic_history import SpSnapshots as SNAPS



class SpRedisClient(object):

  # Redis keys.
  SP_LIST = "sp_list"
  SP_PARAMS = "{}_params"             # spid
  SP_POT_POOLS = "{}_potentialPools"  # spid
  GLOBAL_VALS = "{}_{}_{}"            # spid, iteration, storage type
  COLUMN_VALS = "{}_{}_col-{}_{}"     # spid, iteration, column index,
                                      #   storage type

  def __init__(self, host="localhost", port=6379):
    self._redis = redis.Redis(host=host, port=port)


  def listSpIds(self):
    return msgpack.loads(self._redis.get(self.SP_LIST))["sps"]


  def saveSpState(self, spid, spParams, iteration, state):
    start = time.time() * 1000

    self._updateRegistry(spid, spParams)
    bytesSaved = 0
    bytesSaved += self._saveSpLayerValues(state, spid, iteration)
    bytesSaved += self._saveSpColumnPermanences(state, spid, iteration)
    bytesSaved += self._saveSpPotentialPools(state, spid)

    end = time.time() * 1000
    print "SP {} iteration {} state serialization of {} bytes took {} ms".format(
      spid, iteration, bytesSaved, (end - start)
    )


  def nuke(self):
    # Nukes absolutely all data saved about SP instances.
    rds = self._redis
    spList = rds.get(self.SP_LIST)
    deleted = 0
    if spList is not None:
      spList = msgpack.loads(spList)["sps"]
      for spid in spList:
        deleted += self.delete(spid)
      deleted += rds.delete(self.SP_LIST)
    print "Deleted {} Redis keys.".format(deleted)


  def delete(self, spid):
    rds = self._redis
    deleted = 0
    print "deleting sp {}".format(spid)
    doomed = rds.keys("{}*".format(spid))
    for key in doomed:
      deleted += rds.delete(key)
    # Also remove the registry entry
    spList = msgpack.loads(rds.get(self.SP_LIST))
    sps = spList["sps"]
    doomed = sps.index(spid)
    del sps[doomed]
    rds.set(self.SP_LIST, msgpack.dumps(spList))
    return deleted


  def getSpParams(self, spid):
    params = msgpack.loads(self._redis.get(self.SP_PARAMS.format(spid)))
    return params["params"]


  def getMaxIteration(self, spid):
    rds = self._redis
    maxIteration = 0
    # We will use active columns keys to find the max iteration.
    keys = rds.keys("{}_?_activeColumns".format(spid))
    if len(keys) > 0:
      maxIteration = max([int(key.split("_")[1]) for key in keys])
    return maxIteration


  def getLayerStateByIteration(self, spid, stateType, iteration):
    key = self.GLOBAL_VALS.format(spid, iteration, stateType)
    return self._getSnapshot(stateType, key)


  def getActiveColumnsByColumn(self, spid, columnIndex, maxIteration):
    print columnIndex
    print type(columnIndex)
    out = []
    searchKey = self.GLOBAL_VALS.format(spid, "*", SNAPS.ACT_COL)
    print "searching for {}".format(searchKey)
    keys = self._redis.keys(searchKey)
    for iteration in xrange(0, maxIteration):
      possibleKey = self.GLOBAL_VALS.format(spid, iteration, SNAPS.ACT_COL)
      print possibleKey
      found = None
      if possibleKey in keys:
        activeColumns = self._getSnapshot(SNAPS.ACT_COL, possibleKey)
        print activeColumns
        if columnIndex in activeColumns["indices"]:
          found = 1
        else:
          found = 0
      else:
        print "** WARNING ** Missing {} data for column {} iteration {} (key: {})"\
          .format(SNAPS.ACT_COL, columnIndex, iteration, possibleKey)
      out.append(found)
    return out


  def getStateByIteration(self, spid, stateType, iteration, numColumns):
    out = []
    # Before making a DB call for every column, let's ensure that there are
    # values stored for this type of snapshot.
    numKeys = len(self._redis.keys(
      self.COLUMN_VALS.format(spid, "*", "*", stateType)
    ))
    if numKeys > 0:
      for columnIndex in xrange(0, numColumns):
        key = self.COLUMN_VALS.format(spid, iteration, columnIndex, stateType)
        column = self._getSnapshot(stateType, key)
        out.append(column)
    return out


  def getStatebyColumn(self, spid, stateType, columnIndex, maxIteration):
    out = []
    searchString = self.COLUMN_VALS.format(spid, "*", columnIndex, stateType)
    keys = self._redis.keys(searchString)
    for iteration in xrange(0, maxIteration):
      possibleKey = self.COLUMN_VALS.format(
        spid, iteration, columnIndex, stateType
      )
      found = None
      if possibleKey in keys:
        found = self._getSnapshot(stateType, possibleKey)
      else:
        print "** WARNING ** Missing {} data for column {} iteration {} (key: {})"\
          .format(stateType, columnIndex, iteration, possibleKey)
      out.append(found)
    return out


  def getPotentialPools(self, spid):
    return self._getSnapshot(SNAPS.POT_POOLS, self.SP_POT_POOLS.format(spid))


  def _getSnapshot(self, stateType, key):
    raw = self._redis.get(key)
    out = []
    if raw is not None:
      out = msgpack.loads(raw)[stateType]
    return out


  def _saveSpLayerValues(self, state, spid, iteration):
    # Active columns and inputs are small, and can be saved in one key for
    # each time step.
    bytesSaved = 0
    # These are always SDRS, so they can be compressed.
    # (Caveat: sometimes the input array is not sparse, but whatevs.)
    for outType in [SNAPS.ACT_COL, SNAPS.INPUT]:
      if outType in state.keys():
        key = self.GLOBAL_VALS.format(spid, iteration, outType)
        payload = dict()
        payload[outType] = state[outType]
        bytesSaved += self._saveObject(key, payload)
    # Overlaps and duty cycles cannot be compressed.
    for outType in [SNAPS.ACT_DC, SNAPS.OVP_DC, SNAPS.OVERLAPS]:
      if outType in state.keys():
        key = self.GLOBAL_VALS.format(spid, iteration, outType)
        payload = dict()
        payload[outType] = state[outType]
        bytesSaved += self._saveObject(key, payload)
    return bytesSaved


  def _saveSpColumnPermanences(self, state, spid, iteration):
    # Permanences are big, so we save them in one key per column for easier
    # extraction by either column or iteration later.
    bytesSaved = 0
    if SNAPS.PERMS in state.keys():
      perms = state[SNAPS.PERMS]
      for columnIndex, permanences in enumerate(perms):
        key = self.COLUMN_VALS.format(spid, iteration, columnIndex, SNAPS.PERMS)
        payload = dict()
        payload[SNAPS.PERMS] = permanences
        bytesSaved += self._saveObject(key, payload)
    return bytesSaved



  def _saveSpPotentialPools(self, state, spid):
    # Potental pool span columns, but they don't change over time. So we check
    # to see if we've saved it before.
    bytesSaved = 0
    if SNAPS.POT_POOLS in state.keys():
      key = self.SP_POT_POOLS.format(spid)
      if len(self._redis.keys(key)) == 0:
        payload = dict()
        payload[SNAPS.POT_POOLS] = state[SNAPS.POT_POOLS]
        bytesSaved += self._saveObject(key, payload)
    return bytesSaved



  def _updateRegistry(self, spid, spParams):
    # All saved Spatial Pooler information is keyed by an index and saved into
    # a key defined by SP_LIST.
    spList = self._redis.get(self.SP_LIST)
    if spList is None:
      spList = {"sps": [spid]}
    else:
      spList = msgpack.loads(spList)
      if spid not in spList["sps"]:
        spList["sps"].append(spid)
    self._saveObject(self.SP_LIST, spList)
    params = {
      "params": spParams
    }
    self._saveObject(self.SP_PARAMS.format(spid), params)



  def _saveObject(self, key, obj):
    # Using explicit separators keeps unnecessary whitespace out of Redis.
    msgpackString = msgpack.dumps(obj)
    size = sys.getsizeof(msgpackString)
    self._redis.set(key, msgpackString)
    return size
