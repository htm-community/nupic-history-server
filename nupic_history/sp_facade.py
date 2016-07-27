import time
import uuid

import numpy as np

from nupic_history import SpSnapshots as SNAPS


class SpFacade(object):


  _potentialPools = None


  def __init__(self, sp, redisClient):
    self._redisClient = redisClient
    self._state = None
    self._input = None
    self._activeColumns = None
    self._overlaps = None
    if isinstance(sp, basestring):
      self._sp = None
      self._id = sp
      self._iteration = self._redisClient.getMaxIteration(self._id)
    else:
      self._sp = sp
      self._id = str(uuid.uuid4()).split('-')[0]
      self._iteration = -1


  def isActive(self):
    return self._sp is not None


  def getId(self):
    return self._id


  def getIteration(self):
    return self._iteration


  def getInput(self):
    return self._input


  def getParams(self):
    sp = self._sp
    return {
      "numInputs": sp.getNumInputs(),
      "numColumns": sp.getNumColumns(),
      "columnDimensions": sp.getColumnDimensions().tolist(),
      "numActiveColumnsPerInhArea": sp.getNumActiveColumnsPerInhArea(),
      "potentialPct": sp.getPotentialPct(),
      "globalInhibition": sp.getGlobalInhibition(),
      "localAreaDensity": sp.getLocalAreaDensity(),
      "stimulusThreshold": sp.getStimulusThreshold(),
      "synPermActiveInc": sp.getSynPermActiveInc(),
      "synPermInactiveDec": sp.getSynPermInactiveDec(),
      "synPermConnected": sp.getSynPermConnected(),
      "minPctOverlapDutyCycle": sp.getMinPctOverlapDutyCycles(),
      "minPctActiveDutyCycle": sp.getMinPctActiveDutyCycles(),
      "dutyCyclePeriod": sp.getDutyCyclePeriod(),
      "maxBoost": sp.getMaxBoost(),
    }


  def compute(self, input, learn=False):
    sp = self._sp
    columns = np.zeros(sp.getNumColumns(), dtype="uint32")
    sp.compute(input, learn, columns)
    self._input = input.tolist()
    self._activeColumns = columns.tolist()
    self._advance()


  def getState(self, *args, **kwargs):
    iteration = None
    if "iteration" in kwargs:
      iteration = kwargs["iteration"]
    start = time.time() * 1000
    if self._state is None:
      self._state = {}
    out = dict()
    for snap in args:
      if not SNAPS.contains(snap):
        raise ValueError("{} is not available in SP History.".format(snap))
      out[snap] = self._getSnapshot(snap, iteration=iteration)
    stateIter = iteration
    if stateIter is None:
      stateIter = self.getIteration()
    end = time.time() * 1000
    print "SP state calculation (iteration {}) took {} ms".format(
      stateIter, (end - start)
    )
    return out


  def save(self):
    self._redisClient.saveSpState(self)


  def delete(self):
    self._redisClient.delete(self.getId())


  def _getSnapshot(self, name, iteration=None):
    if name in self._state and iteration == self._iteration:
      # print "returning cached {}".format(name)
      return self._state[name]
    else:
      # print "conjuring {}".format(name)
      funcName = "_conjure{}".format(name[:1].upper() + name[1:])
      func = getattr(self, funcName)
      result = func(iteration=iteration)
      self._state[name] = result
      return result


  def _advance(self):
    self._state = None
    self._iteration += 1


  def _conjureInput(self, iteration=None):
    if iteration is None or iteration == self._iteration:
      return self._input
    else:
      return self._redisClient.getGlobalState(
        self.getId(), SNAPS.INPUT, iteration
      )


  def _conjureActiveColumns(self, iteration=None):
    if iteration is None or iteration == self._iteration:
      return self._activeColumns
    else:
      return self._redisClient.getGlobalState(
        self.getId(), SNAPS.ACT_COL, iteration
      )


  def _conjureOverlaps(self, iteration=None):
    if self._overlaps is None:
      self._overlaps = self._sp.getOverlaps().tolist()
    return self._overlaps


  def _conjurePotentialPools(self, iteration=None):
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


  def _conjureConnectedSynapses(self, iteration=None):
    sp = self._sp
    columns = []
    for colIndex in range(0, sp.getNumColumns()):
      connectedSynapses = np.zeros(shape=(sp.getInputDimensions(),))
      sp.getConnectedSynapses(colIndex, connectedSynapses)
      columns.append(np.nonzero(connectedSynapses)[0].tolist())
    return columns


  def _conjurePermanences(self, iteration=None):
    sp = self._sp
    columns = []
    for colIndex in range(0, sp.getNumColumns()):
      perms = np.zeros(shape=(sp.getInputDimensions(),))
      sp.getPermanence(colIndex, perms)
      columns.append([round(perm, 2) for perm in perms.tolist()])
    return columns


  def _conjureActiveDutyCycles(self, iteration=None):
    sp = self._sp
    dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
    sp.getActiveDutyCycles(dutyCycles)
    return dutyCycles.tolist()


  def _conjureOverlapDutyCycles(self, iteration=None):
    sp = self._sp
    dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
    sp.getOverlapDutyCycles(dutyCycles)
    return dutyCycles.tolist()
