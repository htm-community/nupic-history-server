import time
import uuid

import numpy as np

from nupic_history import SpSnapshots
from nupic_history.sp_redis_client import SpRedisClient


class SpHistory(object):

  _potentialPools = None


  def __init__(self, sp):
    self._sp = sp
    self._redisClient = SpRedisClient()
    self._iteration = -1
    self._state = None
    self._input = None
    self._activeColumns = None
    self._overlaps = None
    self._id = str(uuid.uuid4()).split('-')[0]


  def getId(self):
    return self._id


  def getIteration(self):
    return self._iteration


  def getInput(self):
    return self._input


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
    self._redisClient.saveSpState(self)


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
