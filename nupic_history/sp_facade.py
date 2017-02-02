import uuid
import multiprocessing

import numpy as np

from nupic_history import SpSnapshots as SNAPS
from nupic_history.utils import compressSdr
from nupic.math import topology


class SpFacade(object):

  def __init__(self, sp, redisClient, save=False, modelId=None):
    """
    A wrapper around the HTM Spatial Pooler that can save SP state to Redis for
    each compute cycle. Adds a "save=" kwarg to compute().

    :param sp: Either an instance of Spatial Pooler or a SP id string
    :param redisClient: Instantiated Redis client
    :param save: list of Snapshots to save with each compute step
    """
    self._redisClient = redisClient
    if isinstance(sp, basestring):
      self._sp = None
      self._id = sp
      self._iteration = self._redisClient.getMaxIteration(self._id)
    else:
      self._sp = sp
      if modelId is None:
        self._id = str(uuid.uuid4()).split('-')[0]
      else:
        self._id = modelId
      self._iteration = -1
    self._input = None
    self._activeColumns = self._getZeroedColumns().tolist()
    self._potentialPools = None
    self._save = save
    # self._adjustSavedSnapshots()


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
      params = {
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


  def compute(self, encoding, learn=False, multiprocess=True):
    """
    Pass-through to Spatial Pooler's compute() function, with the addition of
    the save option.
    :param encoding: encoding to pass to the sp
    :param learn: whether sp will learn on this compute cycle
    """
    sp = self._sp
    columns = np.zeros(sp.getNumColumns(), dtype="uint32")
    sp.compute(encoding, learn, columns)
    self._input = encoding.tolist()
    self._activeColumns = columns.tolist()
    self._advance()
    if multiprocess:
      p = multiprocessing.Process(target=self.save)
      p.start()
    else:
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

      sp.getState(Snapshots.OVERLAPS, iteration=10)

    Will return an array of column overlaps (each being an array).

    The following snapshots can be retrieved:

      Snapshots.INPUT = "input"
      Snapshots.POT_POOLS = "potentialPools"
      Snapshots.CON_SYN = "connectedSynapses"
      Snapshots.PERMS = "permanences"
      Snapshots.ACT_COL = "activeColumns"
      Snapshots.OVERLAPS = "overlaps"
      Snapshots.ACT_DC = "activeDutyCycles"
      Snapshots.OVP_DC = "overlapDutyCycles"
      Snapshots.INH_MASKS = "inhibitionMasks"

    :param args:
    :param kwargs:
    :return:
    """
    iteration = None
    if "iteration" in kwargs:
      iteration = kwargs["iteration"]
    columnIndex = None
    if "columnIndex" in kwargs:
      columnIndex = kwargs["columnIndex"]

    sp = self.getSpForIteration(iteration, columnIndex)

    out = dict()
    for snap in args:
      if not SNAPS.contains(snap):
        raise ValueError("{} is not available in SP History.".format(snap))
      out[snap] = self._getSnapshot(
        sp, snap, iteration=iteration, columnIndex=columnIndex
      )
    return out


  def getSpForIteration(self, iteration, columnIndex):
    if self._retrieveFromAlgorithm(iteration, columnIndex):
      return self._sp
    else:
      return self._redisClient.loadSp(self.getId(), iteration)


  def save(self):
    """
    Saves the current state of the SP to Redis.
    """
    if self._save:
      if not self.isActive():
        raise RuntimeError("Cannot save an inactive SP Facade.")
      if self.getInput() is None:
        raise ValueError(
          "Cannot save SP state because it has never seen input.")
      id = self.getId()
      self._redisClient.saveInput(id, self._input, self._iteration)
      self._redisClient.saveSp(id, self._sp, self._iteration)


  def delete(self):
    """
    Deletes all traces of this SP instance from Redis.
    """
    self._redisClient.deleteSp(self.getId())


  def getNumColumns(self):
    """
    Pass-through to getParams()
    :return: [int] number of columns in the SP
    """
    return self.getParams()["numColumns"]


  # def _adjustSavedSnapshots(self):
  #   # If user specified to save connected synapses, we'll switch it to
  #   # permanences. We are actually not saving connected synapses at all. They
  #   # are always calculated from permanences.
  #   save = self._save
  #   if save is not None and len(save) > 0 and SNAPS.CON_SYN in save:
  #     save.remove(SNAPS.CON_SYN)
  #     if SNAPS.PERMS not in save:
  #       save.append(SNAPS.PERMS)



  def _advance(self):
    self._iteration += 1


  def _retrieveFromAlgorithm(self, iteration, columnIndex=None):
    return self.isActive() \
       and (
         (iteration is None and columnIndex is None)
         or iteration == self.getIteration())


  def _getZeroedColumns(self):
    numCols = self.getParams()["numColumns"]
    return np.zeros(shape=(numCols,))


  def _getZeroedInput(self):
    numInputs = self.getParams()["numInputs"]
    return np.zeros(shape=(numInputs,))


  def _getSnapshot(self, sp, name, iteration=None, columnIndex=None):
    funcName = "_conjure{}".format(name[:1].upper() + name[1:])
    func = getattr(self, funcName)
    return func(sp, iteration=iteration, columnIndex=columnIndex)


  # None of the "_conjureXXX" functions below are directly called. They are all
  # called via string name by the _getSnapshot function, depending on what type
  # of snapshot data is being requested. They are called "conjureXXX" because
  # we won't really be sure where the information is coming from until the
  # function is called. It could come from the SpFacade instance, the
  # SpatialPooler instance, or Redis. It depends on whether the facade is active
  # or not, and whether an iteration is specified. In all cases where an
  # iteration in the past is specified, Redis will be the data source.


  def _conjureInput(self, sp, iteration=None, **kwargs):
    if self._retrieveFromAlgorithm(iteration):
      return compressSdr(self._input)
    else:
      return self._redisClient.loadInput(self.getId(), iteration)


  def _conjureActiveColumns(self, sp, iteration=None, columnIndex=None):
    if self._retrieveFromAlgorithm(iteration, columnIndex):
      out = compressSdr(self._activeColumns)
    else:
      out = sp.getActiveColumns()
    return out


  def _conjureOverlaps(self, sp, iteration=None, **kwargs):
    sp.getOverlaps().tolist()


  def _conjurePotentialPools(self, sp, **kwargs):
    if self._potentialPools is None:
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


  def _conjureConnectedSynapses(self, sp, **kwargs):
    columns = []
    for colIndex in range(0, sp.getNumColumns()):
      connectedSynapses = self._getZeroedInput()
      sp.getConnectedSynapses(colIndex, connectedSynapses)
      columns.append(np.nonzero(connectedSynapses)[0].tolist())
    return columns


  def _conjurePermanences(self, sp, **kwargs):
    out = []
    numColumns = self.getNumColumns()
    for colIndex in range(0, numColumns):
      perms = self._getZeroedInput()
      sp.getPermanence(colIndex, perms)
      out.append([round(perm, 2) for perm in perms.tolist()])
    return out


  def _conjureActiveDutyCycles(self, sp, **kwargs):
    dutyCycles = self._getZeroedColumns()
    sp.getActiveDutyCycles(dutyCycles)
    return dutyCycles.tolist()


  def _conjureBoostFactors(self, sp, **kwargs):
    boostFactors = self._getZeroedColumns()
    sp.getBoostFactors(boostFactors)
    return boostFactors.tolist()


  def _conjureOverlapDutyCycles(self, sp, **kwargs):
    dutyCycles = self._getZeroedColumns()
    sp.getOverlapDutyCycles(dutyCycles)
    return dutyCycles.tolist()


  def _conjureInhibitionMasks(self, sp, **kwargs):
    out = []
    numColumns = self.getNumColumns()
    for colIndex in range(0, numColumns):
      out.append(self._getInhibitionMask(sp, colIndex))
    return out


  def _getInhibitionMask(self, sp, colIndex):
    maskNeighbors = topology.neighborhood(
      colIndex, sp._inhibitionRadius, sp._columnDimensions
    ).tolist()
    return maskNeighbors

