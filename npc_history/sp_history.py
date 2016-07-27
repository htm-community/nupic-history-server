import time
import uuid
import json
import sys

import numpy as np

from npc_history import SpSnapshots


class SpHistory(object):

  _potentialPools = None


  def __init__(self, sp, redis=None):
    self._sp = sp
    self._redis = redis
    self._iteration = -1
    self._state = None
    self._input = None
    self._activeColumns = None
    self._overlaps = None
    self._id = str(uuid.uuid4()).split('-')[0]


  def compute(self, input, learn=False):
    sp = self._sp
    columns = np.zeros(sp.getNumColumns(), dtype="uint32")
    sp.compute(input, learn, columns)
    self._input = input.tolist()
    self._activeColumns = columns.tolist()
    self._advance()


  def getState(self, *args):
    start = time.time() * 1000
    if self._state is None:
      self._state = {}
    out = dict()
    for snap in args:
      if not SpSnapshots.contains(snap):
        raise ValueError("{} is not available in SP History.".format(snap))
      out[snap] = self._getSnapshot(snap)
    end = time.time() * 1000
    print("\tSP state calculation took %g ms" % (end - start))
    return out


  def save(self):
    start = time.time() * 1000
    bytesSaved = 0

    if self._redis is None:
      print "Skipping snapshot (no redis client)"
      return

    if self._input is None:
      raise ValueError("Cannot save SP state because it has never seen input.")

    state = self.getState(
      SpSnapshots.INPUT,
      SpSnapshots.POT_POOLS,
      SpSnapshots.CON_SYN,
      SpSnapshots.PERMS,
      SpSnapshots.ACT_COL,
      SpSnapshots.OVERLAPS,
      SpSnapshots.ACT_DC,
      SpSnapshots.OVP_DC
    )

    # Active columns and overlaps are small, and can be saved in one key for
    # each time step.
    for outType in [SpSnapshots.ACT_COL, SpSnapshots.OVERLAPS, SpSnapshots.INPUT]:
      key = "{}_{}_{}".format(self._id, self._iteration, outType)
      payload = dict()
      payload[outType] = state[outType]
      bytesSaved += self._saveObject(key, payload)

    # Connected synapses are big, and will be broken out and saved in one value
    # per column, so they can be retrieved more efficiently by column by the
    # client later.
    columnSynapses = state[SpSnapshots.CON_SYN]
    for columnIndex, connections in enumerate(columnSynapses):
      key = "{}_{}_col-{}_{}".format(self._id, self._iteration,
                                     columnIndex, SpSnapshots.CON_SYN)
      bytesSaved += self._saveObject(key, columnSynapses[columnIndex])

    # Permanences are also big, so same thing.
    perms = state[SpSnapshots.PERMS]
    for columnIndex, permanences in enumerate(perms):
      key = "{}_{}_col-{}_{}".format(self._id, self._iteration,
                                     columnIndex, SpSnapshots.PERMS)
      bytesSaved += self._saveObject(key, perms[columnIndex])

    print "{} bytes saved".format(bytesSaved)
    end = time.time() * 1000
    print("\tSP state serialization took %g ms" % (end - start))


  def _saveObject(self, key, obj):
    str = json.dumps(obj)
    size = sys.getsizeof(str)
    # print "Saving {} ({} bytes)".format(key, size)
    self._redis.set(key, str)
    return size



  def _getSnapshot(self, name):
    if name in self._state:
      print "returning cached {}".format(name)
      return self._state[name]
    else:
      print "calculating {}".format(name)
      funcName = "_calculate{}".format(name[:1].upper() + name[1:])
      func = getattr(self, funcName)
      result = func()
      self._state[name] = result
      return result


  def _advance(self):
    self._state = None
    self._iteration += 1


  def _calculateInput(self):
    return self._input


  def _calculateActiveColumns(self):
    return self._activeColumns


  def _calculateOverlaps(self):
    if self._overlaps is None:
      self._overlaps = self._sp.getOverlaps().tolist()
    return self._overlaps


  def _calculatePotentialPools(self):
    if self._potentialPools is None:
      sp = self._sp
      self._potentialPools = []
      for colIndex in range(0, sp.getNumColumns()):
        potentialPools = []
        potentialPoolsIndices = []
        sp.getPotential(colIndex, potentialPools)
        for i, pool in enumerate(potentialPools):
          if np.asscalar(pool) == 1.0:
            potentialPoolsIndices.append(i)
        self._potentialPools.append(potentialPoolsIndices)
    return self._potentialPools


  def _calculateConnectedSynapses(self):
    sp = self._sp
    columns = []
    for colIndex in range(0, sp.getNumColumns()):
      connectedSynapses = np.zeros(shape=(sp.getInputDimensions(),))
      sp.getConnectedSynapses(colIndex, connectedSynapses)
      columns.append(np.nonzero(connectedSynapses)[0].tolist())
    return columns


  def _calculatePermanences(self):
    sp = self._sp
    columns = []
    for colIndex in range(0, sp.getNumColumns()):
      perms = np.zeros(shape=(sp.getInputDimensions(),))
      sp.getPermanence(colIndex, perms)
      columns.append([round(perm, 2) for perm in perms.tolist()])
    return columns


  def _calculateActiveDutyCycles(self):
    sp = self._sp
    dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
    sp.getActiveDutyCycles(dutyCycles)
    return dutyCycles.tolist()


  def _calculateOverlapDutyCycles(self):
    sp = self._sp
    dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
    sp.getOverlapDutyCycles(dutyCycles)
    return dutyCycles.tolist()
