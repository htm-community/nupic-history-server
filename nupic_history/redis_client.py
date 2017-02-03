import sys
import os
import time
import json

import capnp
import redis

from nupic_history import SpSnapshots as SP_SNAPS
from nupic_history import TmSnapshots as TM_SNAPS

from nupic.proto import SpatialPoolerProto_capnp
from nupic.research.spatial_pooler import SpatialPooler


class FileIoClient(object):

  # File names.
  SP_KEY = "htm_sp_{}_{}.npc"               # modelId, iteration
  SP_ITER = "htm_sp_{}_?.npc"               # modelId
  ENCODING = "htm_encoding_{}_{}.npc"       # modelId, iteration
  SP_ACT_COL = "htm_spac_{}_{}.npc"        # modelId, iteration
  # MODEL_LIST = "model_list"
  # SP_PARAMS = "{}_sp_params"          # spid
  # TM_PARAMS = "{}_tm_params"          # tmid
  # SP_POT_POOLS = "{}_potentialPools"  # spid
  # SP_INH_MASKS = "{}_inhibitionMasks" # spid
  # GLOBAL_VALS = "{}_{}_{}"            # spid, iteration, storage type
  # COLUMN_VALS = "{}_{}_col-{}_{}"     # spid, iteration, column index,
  #                                     # storage type

  def __init__(self, workingDir=None):
    if workingDir is None:
      workingDir = "/tmp"
    self._workingDir = workingDir


  def _writeData(self, key, data):
    path = self._workingDir + "/" + key
    with open(path, "w") as fileout:
      fileout.write(json.dumps(data))


  def _readData(self, key):
    path = self._workingDir + "/" + key
    with open(path, "r") as f:
      return json.loads(f.read())


  def _writePrototype(self, key, proto):
    path = self._workingDir + "/" + key
    with open(path, "w") as fileout:
      proto.write(fileout)


  def saveEncoding(self, encoding, id, iteration):
    start = time.time() * 1000
    size = sys.getsizeof(encoding)
    key = self.ENCODING.format(id, iteration)
    self._writeData(key, encoding)
    end = time.time() * 1000
    print "{} input serialization of {} bytes into {} took {} ms".format(
      id, size, key, (end - start)
    )


  def saveActiveColumns(self, activeColumns, id, iteration):
    start = time.time() * 1000
    size = sys.getsizeof(activeColumns)
    key = self.SP_ACT_COL.format(id, iteration)
    self._writeData(key, activeColumns)
    end = time.time() * 1000
    print "{} activeColumns serialization of {} bytes into {} took {} ms".format(
      id, size, key, (end - start)
    )


  def saveSpatialPooler(self, sp, id, iteration=None):
    """
    :param iteration: If not provided that means the SP is not running yet (-1).
    """
    start = time.time() * 1000

    if iteration is None:
      iteration = -1
    proto = SpatialPoolerProto_capnp.SpatialPoolerProto.new_message()
    sp.write(proto)
    key = self.SP_KEY.format(id, iteration)
    self._writePrototype(key, proto)

    end = time.time() * 1000
    print "{} SP storage into {} took {} ms".format(
      id, key, (end - start)
    )


  def loadSpatialPooler(self, id, iteration=None):
    start = time.time() * 1000

    if iteration is None:
      iteration = self.getMaxIteration(id)
    key = self.SP_KEY.format(id, iteration)
    path = self._workingDir + "/" + key
    with open(path, "r") as spFile:
      proto = SpatialPoolerProto_capnp.SpatialPoolerProto.read(spFile)

    sp = SpatialPooler.read(proto)

    end = time.time() * 1000
    print "{} SP de-serialization from {} took {} ms".format(
      id, key, (end - start)
    )
    return sp, iteration


  def getMaxIteration(self, modelId):
    maxIteration = -1
    # We will use active columns keys to find the max iteration.
    keys = os.listdir(self._workingDir)
    if len(keys) > 0:
      maxIteration = max([int(key.split("_")[3].split(".")[0]) for key in keys])
    return maxIteration


  def nuke(self):
    folder = self._workingDir
    for f in os.listdir(folder):
      p = os.path.join(folder, f)
      try:
        if os.path.isfile(p):
          os.unlink(p)
      except Exception as e:
        print(e)



      # def saveInput(self, id, input, step):
  #   compressedInput = compressSdr(input)
  #   size = sys.getsizeof(compressedInput)
  #   print("Saving Input Encoding ({}) at step {}".format(id, step))
  #   self._write('htm_input_{}_{}'.format(id, step), compressedInput)
  #   return size
  #
  # def loadInput(self, id, step):
  #   return self._read('htm_input_{}_{}'.format(id, step))
  #
  # def saveSp(self, id, sp, step):
  #   proto = SpatialPoolerProto_capnp.SpatialPoolerProto.new_message()
  #   sp.write(proto)
  #   bytes = proto.to_bytes_packed()
  #   size = sys.getsizeof(bytes)
  #   print("Saving Spatial Pooler ({}) at step {}".format(id, step))
  #   self._write('htm_sp_{}_{}'.format(id, step), bytes)
  #   return size
  #
  # def deleteModel(self, id):
  #   rds = self._redis
  #   keys = rds.keys("htm_*_{}_*".format(id))
  #   deleted = 0
  #   if keys is not None:
  #     for modelId in keys:
  #       deleted += self.delete(modelId)
  #     deleted += rds.delete(self.MODEL_LIST)
  #   print "Deleted Model {} ({} redis keys)".format(id, deleted)



      # def listSpIds(self):
  #   return msgpack.loads(self._read(self.MODEL_LIST))["sps"]
  #
  #
  # def saveSpState(self, spid, spParams, iteration, state):
  #   start = time.time() * 1000
  #
  #   self._updateSpRegistry(spid, spParams)
  #   bytesSaved = 0
  #   bytesSaved += self._saveSpLayerValues(state, spid, iteration)
  #   bytesSaved += self._saveSpColumnPermanences(state, spid, iteration)
  #   bytesSaved += self._saveSpPotentialPools(state, spid)
  #   bytesSaved += self._saveSpColumnInhibitionMasks(state, spid)
  #
  #   end = time.time() * 1000
  #   print "SP {} iteration {} state serialization of {} bytes took {} ms".format(
  #     spid, iteration, bytesSaved, (end - start)
  #   )
  #
  #
  # def saveTmState(self, modelId, tmParams, iteration, state):
  #   start = time.time() * 1000
  #
  #   self._updateTmRegistry(modelId, tmParams)
  #   bytesSaved = 0
  #   bytesSaved += self._saveTmLayerValues(state, modelId, iteration)
  #   # bytesSaved += self._saveSpColumnPermanences(state, modelId, iteration)
  #   # bytesSaved += self._saveSpPotentialPools(state, modelId)
  #   # bytesSaved += self._saveSpColumnInhibitionMasks(state, modelId)
  #
  #   end = time.time() * 1000
  #   print "TM {} iteration {} state serialization of {} bytes took {} ms".format(
  #     modelId, iteration, bytesSaved, (end - start)
  #   )
  #
  #
  # def delete(self, modelId):
  #   rds = self._redis
  #   deleted = 0
  #   print "deleting model {}".format(modelId)
  #   doomed = rds.keys("{}*".format(modelId))
  #   for key in doomed:
  #     deleted += rds.delete(key)
  #   # Also remove the registry entry
  #   modelList = msgpack.loads(rds.get(self.MODEL_LIST))
  #   models = modelList["models"]
  #   doomed = models.index(modelId)
  #   del models[doomed]
  #   rds.set(self.MODEL_LIST, msgpack.dumps(modelList))
  #   return deleted
  #
  #
  # def getSpParams(self, modelId):
  #   params = msgpack.loads(self._read(self.SP_PARAMS.format(modelId)))
  #   return params["params"]
  #
  #
  # def getTmParams(self, modelId):
  #   params = msgpack.loads(self._read(self.TM_PARAMS.format(modelId)))
  #   return params["params"]
  #
  #
  # def getMaxIteration(self, modelId):
  #   rds = self._redis
  #   maxIteration = 0
  #   # We will use active columns keys to find the max iteration.
  #   keys = rds.keys("{}_?_activeColumns".format(modelId))
  #   if len(keys) > 0:
  #     maxIteration = max([int(key.split("_")[1]) for key in keys])
  #   return maxIteration
  #
  #
  # def getLayerStateByIteration(self, modelId, stateType, iteration):
  #   key = self.GLOBAL_VALS.format(modelId, iteration, stateType)
  #   return self._getSnapshot(stateType, key)
  #
  #
  # def getActiveColumnsByColumn(self, modelId, columnIndex, maxIteration):
  #   out = []
  #   searchKey = self.GLOBAL_VALS.format(modelId, "*", SP_SNAPS.ACT_COL)
  #   keys = self._redis.keys(searchKey)
  #   for iteration in xrange(0, maxIteration):
  #     possibleKey = self.GLOBAL_VALS.format(modelId, iteration, SP_SNAPS.ACT_COL)
  #     found = None
  #     if possibleKey in keys:
  #       activeColumns = self._getSnapshot(SP_SNAPS.ACT_COL, possibleKey)
  #       if columnIndex in activeColumns["indices"]:
  #         found = 1
  #       else:
  #         found = 0
  #     else:
  #       print "** WARNING ** Missing {} data for column {} iteration {} (key: {})"\
  #         .format(SP_SNAPS.ACT_COL, columnIndex, iteration, possibleKey)
  #     out.append(found)
  #   return out
  #
  #
  # def getStateByIteration(self, modelId, stateType, iteration, numColumns):
  #   out = []
  #   # Before making a DB call for every column, let's ensure that there are
  #   # values stored for this type of snapshot.
  #   numKeys = len(self._redis.keys(
  #     self.COLUMN_VALS.format(modelId, "*", "*", stateType)
  #   ))
  #   if numKeys > 0:
  #     for columnIndex in xrange(0, numColumns):
  #       key = self.COLUMN_VALS.format(modelId, iteration, columnIndex, stateType)
  #       column = self._getSnapshot(stateType, key)
  #       out.append(column)
  #   return out
  #
  #
  # def getStatebyColumn(self, modelId, stateType, columnIndex, maxIteration):
  #   out = []
  #   searchString = self.COLUMN_VALS.format(modelId, "*", columnIndex, stateType)
  #   keys = self._redis.keys(searchString)
  #   for iteration in xrange(0, maxIteration):
  #     possibleKey = self.COLUMN_VALS.format(
  #       modelId, iteration, columnIndex, stateType
  #     )
  #     found = None
  #     if possibleKey in keys:
  #       found = self._getSnapshot(stateType, possibleKey)
  #     else:
  #       print "** WARNING ** Missing {} data for column {} iteration {} (key: {})"\
  #         .format(stateType, columnIndex, iteration, possibleKey)
  #     out.append(found)
  #   return out
  #
  #
  # def getPotentialPools(self, modelId):
  #   return self._getSnapshot(SP_SNAPS.POT_POOLS, self.SP_POT_POOLS.format(modelId))
  #
  #
  # def _getSnapshot(self, stateType, key):
  #   raw = self._read(key)
  #   out = []
  #   if raw is not None:
  #     out = msgpack.loads(raw)[stateType]
  #   return out
  #
  #
  # def _saveSpLayerValues(self, state, modelId, iteration):
  #   # Active columns and inputs are small, and can be saved in one key for
  #   # each time step.
  #   bytesSaved = 0
  #   stateKeys = [
  #     SP_SNAPS.ACT_COL, SP_SNAPS.INPUT, SP_SNAPS.ACT_DC,
  #     SP_SNAPS.OVP_DC, SP_SNAPS.OVERLAPS
  #   ]
  #   for outType in stateKeys:
  #     if outType in state.keys():
  #       key = self.GLOBAL_VALS.format(modelId, iteration, outType)
  #       payload = dict()
  #       payload[outType] = state[outType]
  #       bytesSaved += self._saveObject(key, payload)
  #   return bytesSaved
  #
  #
  # def _saveTmLayerValues(self, state, modelId, iteration):
  #   # Active cells are small, and can be saved in one key for each time step.
  #   bytesSaved = 0
  #   for outType in [TM_SNAPS.ACT_CELLS]:
  #     if outType in state.keys():
  #       key = self.GLOBAL_VALS.format(modelId, iteration, outType)
  #       payload = dict()
  #       payload[outType] = state[outType]
  #       bytesSaved += self._saveObject(key, payload)
  #   return bytesSaved
  #
  #
  # def _saveSpColumnPermanences(self, state, modelId, iteration):
  #   # Permanences are big, so we save them in one key per column for easier
  #   # extraction by either column or iteration later.
  #   bytesSaved = 0
  #   if SP_SNAPS.PERMS in state.keys():
  #     perms = state[SP_SNAPS.PERMS]
  #     for columnIndex, permanences in enumerate(perms):
  #       key = self.COLUMN_VALS.format(modelId, iteration, columnIndex, SP_SNAPS.PERMS)
  #       payload = dict()
  #       payload[SP_SNAPS.PERMS] = permanences
  #       bytesSaved += self._saveObject(key, payload)
  #   return bytesSaved
  #
  #
  #
  # def _saveSpPotentialPools(self, state, modelId):
  #   # Potental pool span columns, but they don't change over time. So we check
  #   # to see if we've saved it before.
  #   bytesSaved = 0
  #   if SP_SNAPS.POT_POOLS in state.keys():
  #     key = self.SP_POT_POOLS.format(modelId)
  #     if len(self._redis.keys(key)) == 0:
  #       payload = dict()
  #       payload[SP_SNAPS.POT_POOLS] = state[SP_SNAPS.POT_POOLS]
  #       bytesSaved += self._saveObject(key, payload)
  #   return bytesSaved
  #
  #
  #
  # def _saveSpColumnInhibitionMasks(self, state, modelId):
  #   # Inhibition masks span columns, but they don't change over time. So we
  #   # check to see if we've saved it before.
  #   bytesSaved = 0
  #   if SP_SNAPS.INH_MASKS in state.keys():
  #     key = self.SP_INH_MASKS.format(modelId)
  #     if len(self._redis.keys(key)) == 0:
  #       payload = dict()
  #       payload[SP_SNAPS.INH_MASKS] = state[SP_SNAPS.INH_MASKS]
  #       bytesSaved += self._saveObject(key, payload)
  #   return bytesSaved
  #
  #
  #
  # def _updateRegistry(self, modelId):
  #   models = self._read(self.MODEL_LIST)
  #   if models is None:
  #     models = {"models": [modelId]}
  #   else:
  #     models = msgpack.loads(models)
  #     if modelId not in models["models"]:
  #       models["models"].append(modelId)
  #   self._saveObject(self.MODEL_LIST, models)
  #
  #
  #
  # def _updateSpRegistry(self, modelId, spParams):
  #   self._updateRegistry(modelId)
  #   self._saveObject(self.SP_PARAMS.format(modelId), {
  #     "params": spParams
  #   })
  #
  #
  #
  # def _updateTmRegistry(self, modelId, tmParams):
  #   self._updateRegistry(modelId)
  #   self._saveObject(self.TM_PARAMS.format(modelId), {
  #     "params": tmParams
  #   })
  #
  #
  #
  # def _saveObject(self, key, obj):
  #   msgpackString = msgpack.dumps(obj)
  #   size = sys.getsizeof(msgpackString)
  #   self._write(key, msgpackString)
  #   return size
