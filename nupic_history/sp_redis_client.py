import sys
import time
import json

import redis

from nupic_history import SpSnapshots as SNAPS



def compressSdr(sdr):
  out = {
    "length": len(sdr),
    "indices": []
  }
  indices = out["indices"]
  for i, bit in enumerate(sdr):
    if bit == 1:
      indices.append(i)
  return out



class SpRedisClient(object):

  # Redis keys.
  SP_LIST = "sp_list"
  SP_PARAMS = "{}_params" # spid
  GLOBAL_VALS = "{}_{}_{}" # spid, iteration, storage type
  COLUMN_VALS = "{}_{}_col-{}_{}" # spid, iteration, column index, storage type

  def __init__(self, host="localhost", port=6379):
    self._redis = redis.Redis(host=host, port=port)


  def saveSpState(self, spHistory):
    start = time.time() * 1000

    self._updateRegistry(spHistory)

    bytesSaved = 0
    spid = spHistory.getId()
    iteration = spHistory.getIteration()

    if spHistory.getInput() is None:
      raise ValueError("Cannot save SP state because it has never seen input.")

    state = spHistory.getState(
      SNAPS.INPUT,
      SNAPS.POT_POOLS,
      SNAPS.CON_SYN,
      SNAPS.PERMS,
      SNAPS.ACT_COL,
      SNAPS.OVERLAPS,
      SNAPS.ACT_DC,
      SNAPS.OVP_DC
    )

    bytesSaved += self._saveSpGlobalValues(state, spid, iteration)
    bytesSaved += self._saveSpColumnPermanences(state, spid, iteration)

    end = time.time() * 1000
    print "SP state serialization of {} bytes took {} ms".format(bytesSaved, (end - start))


  def nuke(self):
    # Nukes absolutely all data saved about SP instances.
    rds = self._redis
    spList = rds.get(self.SP_LIST)
    deleted = 0
    if spList is not None:
      spList = json.loads(spList)["sps"]
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
    spList = json.loads(rds.get(self.SP_LIST))
    sps = spList["sps"]
    doomed = sps.index(spid)
    del sps[doomed]
    rds.set(self.SP_LIST, json.dumps(spList))
    return deleted


  def getMaxIteration(self, spid):
    rds = self._redis
    # We will use active columns keys to find the max iteration.
    keys = rds.keys("{}_?_activeColumns".format(spid))
    return max([int(key.split("_")[1]) for key in keys])


  def getGlobalState(self, spid, stateType, iteration):
    state = self._redis.get(self.GLOBAL_VALS.format(spid, iteration, stateType))
    return json.loads(state)


  def _saveSpGlobalValues(self, state, spid, iteration):
    # Active columns and overlaps are small, and can be saved in one key for
    # each time step.
    bytesSaved = 0
    # These are always SDRS, so they can be compressed.
    # (Caveat: sometimes the input array is not sparse, but whatevs.)
    for outType in [SNAPS.ACT_COL, SNAPS.INPUT]:
      key = self.GLOBAL_VALS.format(spid, iteration, outType)
      payload = dict()
      payload[outType] = compressSdr(state[outType])
      bytesSaved += self._saveObject(key, payload)
    # Overlaps and duty cycles cannot be compressed.
    for outType in [SNAPS.ACT_DC, SNAPS.OVP_DC]:
      key = self.GLOBAL_VALS.format(spid, iteration, outType)
      payload = dict()
      payload[outType] = state[outType]
      bytesSaved += self._saveObject(key, payload)
    return bytesSaved


  def _saveSpColumnPermanences(self, state, spid, iteration):
    # Permanences are big, so we save them in one key per column for easier
    # extraction by either column or iteration later.
    bytesSaved = 0
    perms = state[SNAPS.PERMS]
    for columnIndex, permanences in enumerate(perms):
      key = self.COLUMN_VALS.format(spid, iteration, columnIndex, SNAPS.PERMS)
      payload = dict()
      payload[SNAPS.PERMS] = perms[columnIndex]
      bytesSaved += self._saveObject(key, payload)
    return bytesSaved



  def _updateRegistry(self, spHistory):
    # All saved Spatial Pooler information is keyed by an index and saved into
    # a key defined by SP_LIST.
    spList = self._redis.get(self.SP_LIST)
    spid = spHistory.getId()
    if spList is None:
      spList = {"sps": [spid]}
    else:
      spList = json.loads(spList)
      if spid not in spList["sps"]:
        spList["sps"].append(spid)
    self._saveObject(self.SP_LIST, spList)
    params = {
      "params": spHistory.getParams()
    }
    self._saveObject(self.SP_PARAMS.format(spid), params)


  def _saveObject(self, key, obj):
    # Using explicit separators keeps unnecessary whitespace out of Redis.
    str = json.dumps(obj, separators=(',',':'))
    size = sys.getsizeof(str)
    self._redis.set(key, str)
    return size
