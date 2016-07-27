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

    print "{} bytes saved".format(bytesSaved)
    end = time.time() * 1000
    print("\tSP state serialization took %g ms" % (end - start))


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
    rds = self._redis
    spList = rds.get(self.SP_LIST)
    spId = spHistory.getId()
    entry = {
      "id": spId,
      "created": time.time()
    }
    if spList is None:
      spList = {"sps": [entry]}
    else:
      spList = json.loads(spList)
      if spId not in [saved["id"] for saved in spList["sps"]]:
        spList["sps"].append(entry)
    rds.set(self.SP_LIST, json.dumps(spList))



  def cleanAll(self):
    rds = self._redis
    spList = rds.get(self.SP_LIST)
    deleted = 0
    if spList is not None:
      spList = json.loads(spList)["sps"]
      for entry in spList:
        spId = entry["id"]
        print "deleting sp {}".format(spId)
        doomed = rds.keys("{}*".format(spId))
        for key in doomed:
          deleted += rds.delete(key)
      deleted += rds.delete(self.SP_LIST)
    print "Deleted {} Redis keys.".format(deleted)


  def _saveObject(self, key, obj):
    str = json.dumps(obj)
    size = sys.getsizeof(str)
    # print "Saving {} ({} bytes)".format(key, size)
    self._redis.set(key, str)
    return size
