import time
import uuid

import numpy as np

from nupic_history import SpSnapshots as SNAPS


class SpFacade(object):

  def __init__(self, sp, redisClient):
    """
    A wrapper around the HTM Spatial Pooler that can save SP state to Redis for
    each compute cycle. Adds a "save=" kwarg to compute().

    :param sp: Either an instance of Spatial Pooler or a SP id string
    :param redisClient: Instantiated Redis client
    """
    self._redisClient = redisClient
    self._state = None
    self._input = None
    self._activeColumns = None
    self._potentialPools = None

    if isinstance(sp, basestring):
      self._sp = None
      self._id = sp
      self._iteration = self._redisClient.getMaxIteration(self._id)
    else:
      self._sp = sp
      self._id = str(uuid.uuid4()).split('-')[0]
      self._iteration = -1


  def __str__(self):
    return "SP {} has seen {} iterations".format(
      self.getId(), self.getIteration()
    )


  def isActive(self):
    """
    Returns True if this facade contains a live spatial pooler. If False, the
    facade cannot compute(), but can be used for history playback.
    :return: has active Spatial Pooler
    """
    return self._sp is not None


  def getId(self):
    """
    Unique id used for storage and retrieval in Redis.
    :return: id
    """
    return self._id


  def getIteration(self):
    """
    Represents the current iteration of data the SP has seen. If this facade is
    not active, this also will be the last data point it saw before being
    deactivated.
    :return: int
    """
    return self._iteration


  def getInput(self):
    """
    :return: last seen input encoding
    """
    return self._input


  def getParams(self):
    """
    Utility to collect the SP params used at creation into a dict.
    :return: [dict] parameters
    """
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


  def compute(self, encoding, learn=False, save=False):
    """
    Pass-through to Spatial Pooler's compute() function, with the addition of
    the save option.
    :param encoding: encoding to pass to the sp
    :param learn: whether sp will learn on this compute cycle
    :param save: whether the sp state will be saved to Redis after the cycle
    """
    sp = self._sp
    columns = np.zeros(sp.getNumColumns(), dtype="uint32")
    sp.compute(encoding, learn, columns)
    self._input = encoding.tolist()
    self._activeColumns = columns.tolist()
    self._advance()
    if save:
      self.save()


  def getState(self, *args, **kwargs):
    """
    Returns the requested state of the spatial pooler. This will either get the
    state from the sp instance itself and cache it in memory for further calls,
    or if the facade is inactive, it will fetch the state from redis.

    This function can be used to retrieve any saved state snapshots from Redis
    for any iteration the SP has seen. It will work for active and inactive
    facades.

    For example, to get the column overlaps at iteration 10:

      sp.getState(SpSnapshots.OVERLAPS, iteration=10)

    Will return an array of column overlaps (each being an array).

    The following snapshots can be retrieved:

      SpSnapshots.INPUT = "input"
      SpSnapshots.POT_POOLS = "potentialPools"
      SpSnapshots.CON_SYN = "connectedSynapses"
      SpSnapshots.PERMS = "permanences"
      SpSnapshots.ACT_COL = "activeColumns"
      SpSnapshots.OVERLAPS = "overlaps"
      SpSnapshots.ACT_DC = "activeDutyCycles"
      SpSnapshots.OVP_DC = "overlapDutyCycles"

    :param args:
    :param kwargs:
    :return:
    """
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
    """
    Saves the current state of the SP to Redis.
    """
    if not self.isActive():
      raise RuntimeError("Cannot save an inactive SP Facade.")
    self._redisClient.saveSpState(self)


  def delete(self):
    """
    Deletes all traces of this SP instance from Redis.
    """
    self._redisClient.delete(self.getId())


  def getNumColumns(self):
    """
    Pass-through to getParams()
    :return: [int] number of columns in the SP
    """
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


  # None of the "_conjureXXX" functions below are directly called. They are all
  # called via string name by the _getSnapshot function, depending on what type
  # of snapshot data is being requested. They are called "conjureXXX" because
  # we won't really be sure where the information is coming from until the
  # function is called. It could come from the SpFacade instance, the
  # SpatialPooler instance, or Redis. It depends on whether the facade is active
  # or not, and whether an iteration is specified. In all cases where an
  # iteration in the past is specified, Redis will be the data source.


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
    if self.isActive() and iteration is None:
      return self._sp.getOverlaps().tolist()
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.OVERLAPS, iteration
      )


  def _conjurePotentialPools(self, **kwargs):
    if self._potentialPools is None:
      if self.isActive():
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
    if self.isActive() and iteration is None:
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
    if self.isActive() and iteration is None:
      for colIndex in range(0, numColumns):
        perms = np.zeros(shape=(inputDims,))
        sp.getPermanence(colIndex, perms)
        columns.append([round(perm, 2) for perm in perms.tolist()])
    else:
      columns = self._redisClient.getPerColumnState(
        self.getId(), SNAPS.PERMS, iteration, numColumns
      )
    return columns


  def _conjureActiveDutyCycles(self, iteration=None):
    if self.isActive() and iteration is None:
      sp = self._sp
      dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
      sp.getActiveDutyCycles(dutyCycles)
      return dutyCycles.tolist()
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.ACT_DC, iteration
      )


  def _conjureOverlapDutyCycles(self, iteration=None):
    if self.isActive() and iteration is None:
      sp = self._sp
      dutyCycles = np.zeros(shape=(sp.getNumColumns(),))
      sp.getOverlapDutyCycles(dutyCycles)
      return dutyCycles.tolist()
    else:
      return self._redisClient.getLayerState(
        self.getId(), SNAPS.OVP_DC, iteration
      )
