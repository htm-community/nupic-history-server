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
    if sp is None:
      params =self._redisClient.getSpParams(self.getId())
    else:
      params ={
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
    return params


  def compute(self, input, learn=False, save=False):
    sp = self._sp
    columns = np.zeros(sp.getNumColumns(), dtype="uint32")
    sp.compute(input, learn, columns)
    self._input = input.tolist()
    self._activeColumns = columns.tolist()
    self._advance()
    if save: self.save()


  def getState(self, *args, **kwargs):
    start = time.time() * 1000
    iteration = None
    if "iteration" in kwargs:
      iteration = kwargs["iteration"]
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
    print "SP state extraction (iteration {}) took {} ms".format(
      stateIter, (end - start)
    )
    return out


  def save(self):
    self._redisClient.saveSpState(self)


  def delete(self):
    self._redisClient.delete(self.getId())


  def getNumColumns(self):
    return self.getParams()["numColumns"]


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
    if iteration is None or iteration == self.getIteration():
      return self._input
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.INPUT, iteration
      )


  def _conjureActiveColumns(self, iteration=None):
    if iteration is None or iteration == self.getIteration():
      return self._activeColumns
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.ACT_COL, iteration
      )


  def _conjureOverlaps(self, iteration=None):
    if iteration is None or iteration == self.getIteration():
      return self._sp.getOverlaps().tolist()
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.OVERLAPS, iteration
      )


  def _conjurePotentialPools(self, iteration=None):
    if self._potentialPools is None:
      if iteration is None or iteration == self.getIteration():
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
      else:
        self._potentialPools = self._redisClient.getPotentialPools(self.getId())
    return self._potentialPools


  def _conjureConnectedSynapses(self, iteration=None):
    columns = []
    if iteration is None or iteration == self.getIteration():
      sp = self._sp
      for colIndex in range(0, sp.getNumColumns()):
        connectedSynapses = np.zeros(shape=(sp.getInputDimensions(),))
        sp.getConnectedSynapses(colIndex, connectedSynapses)
        columns.append(np.nonzero(connectedSynapses)[0].tolist())
    else:
      perms = self._conjurePermanences(iteration=iteration)
      threshold = self.getParams()["synPermConnected"]
      for columnPerms in perms:
        colConnections = []
        for perm in columnPerms:
          bit = 0
          if perm > threshold:
            bit = 1
          colConnections.append(bit)
        columns.append(colConnections)
    return columns


  def _conjurePermanences(self, iteration=None):
    columns = []
    numColumns = self.getNumColumns()
    inputDims = self.getParams()["numInputs"]
    sp = self._sp
    if iteration is None or iteration == self.getIteration():
      for colIndex in range(0, numColumns):
        perms = np.zeros(shape=(inputDims,))
        sp.getPermanence(colIndex, perms)
        columns.append([round(perm, 2) for perm in perms.tolist()])
    else:
        columns = self._redisClient.getPerColumnState(self.getId(), SNAPS.PERMS, iteration, numColumns)
    return columns


  def _conjureActiveDutyCycles(self, iteration=None):
    if iteration is None or iteration == self.getIteration():
      sp = self._sp
      dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
      sp.getActiveDutyCycles(dutyCycles)
      return dutyCycles.tolist()
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.ACT_DC, iteration
      )


  def _conjureOverlapDutyCycles(self, iteration=None):
    if iteration is None or iteration == self.getIteration():
      sp = self._sp
      dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
      sp.getOverlapDutyCycles(dutyCycles)
      return dutyCycles.tolist()
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.OVP_DC, iteration
      )
