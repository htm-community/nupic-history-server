import uuid
import multiprocessing

from nupic_history import TmSnapshots as SNAPS

class TmFacade(object):

  def __init__(self, tm, redisClient, save=None, modelId=None):
    self._redisClient = redisClient
    if isinstance(tm, basestring):
      self._tm = None
      self._id = tm
      self._iteration = self._redisClient.getMaxIteration(self._id)
    else:
      self._tm = tm
      if modelId is None:
        self._id = str(uuid.uuid4()).split('-')[0]
      else:
        self._id = modelId
      self._iteration = -1
    self._state = None
    self._input = None
    self._save = None
    if save is not None:
      self._save = save[:]


  def __str__(self):
    return "TM {} has seen {} iterations".format(
      self.getId(), self.getIteration()
    )


  def isActive(self):
    """
    Returns True if this facade contains a live temporal memory. If False, the
    facade cannot compute(), but can be used for history playback.
    :return: has active Spatial Pooler
    """
    return self._tm is not None


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


  def compute(self, activeColumns, learn=True, multiprocess=True):
    """
    Pass-through to Temporal Memory's compute() function, with the addition of
    the save option.
    :param activeColumns: (set) indices of on bits
    :param learn: whether tm will learn on this compute cycle
    """
    tm = self._tm
    tm.compute(activeColumns, learn=learn)
    self._input = activeColumns
    self._advance()
    if multiprocess:
      p = multiprocessing.Process(target=self.save)
      p.start()
    else:
      self.save()


  def reset(self):
    """
    Just a pass-through to the TM.reset() function.
    """
    self._tm.reset()


  def save(self):
    """
    Saves the current state of the TM to Redis.
    """
    if self._save is not None and len(self._save) > 0:
      if not self.isActive():
        raise RuntimeError("Cannot save an inactive TM Facade.")
      if self.getInput() is None:
        raise ValueError(
          "Cannot save TM state because it has never seen input.")
      modelId = self.getId()
      params = self.getParams()
      iteration = self.getIteration()
      state = self.getState(*self._save)
      print "Saving state of TM..."
      self._redisClient.saveTmState(modelId, params, iteration, state)


  def _advance(self):
    self._state = None
    self._iteration += 1


  def _retrieveFromAlgorithm(self, iteration):
    return self.isActive() \
           and (iteration is None or iteration == self.getIteration())


  def getParams(self):
    """
    Utility to collect the SP params used at creation into a dict.
    :return: [dict] parameters
    """
    tm = self._tm
    if tm is None:
      params =self._redisClient.getTmParams(self.getId())
    else:
      params = {
        "cellsPerColumn": tm.getCellsPerColumn(),
        "activationThreshold": tm.getActivationThreshold(),
        "initialPermanence": tm.getInitialPermanence(),
        "connectedPermanence": tm.getConnectedPermanence(),
        "minThreshold": tm.getMinThreshold(),
        "maxNewSynapseCount": tm.getMaxNewSynapseCount(),
        "permanenceIncrement": tm.getPermanenceIncrement(),
        "permanenceDecrement": tm.getPermanenceDecrement(),
        "predictedSegmentDecrement": tm.getPredictedSegmentDecrement(),
        "maxSegmentsPerCell": tm.connections.maxSegmentsPerCell,
        "maxSynapsesPerSegment": tm.connections.maxSynapsesPerSegment,
        "columnDimensions": tm.getColumnDimensions(),
      }
    return params


  def getState(self, *args, **kwargs):
    # tm = self._tm
    # print("active cells " + str(tm.getActiveCells()))
    # print("predictive cells " + str(tm.getPredictiveCells()))
    # print("winner cells " + str(tm.getWinnerCells()))
    # print("# of active segments " + str(tm.connections.numSegments()))

    iteration = None
    if "iteration" in kwargs:
      iteration = kwargs["iteration"]

    if self._state is None:
      self._state = {}
    out = dict()
    for snap in args:
      if not SNAPS.contains(snap):
        raise ValueError("{} is not available in TM History.".format(snap))
      out[snap] = self._getSnapshot(
        snap, iteration=iteration
      )
    return out


  def _synapseToDict(self, synapse):
    return {
      "presynapticCell": synapse.presynapticCell,
      "permanence": synapse.permanence,
    }


  def _segmentToDict(self, segment):
    return {
      "cell": segment.cell,
      "synapses": [self._synapseToDict(s) for s in segment._synapses],
    }


  def _getSnapshot(self, name, iteration=None):
    # Use the cache if we can.
    if name in self._state and iteration == self._iteration:
      print "** Using Cache"
      return self._state[name]
    else:
      funcName = "_conjure{}".format(name[:1].upper() + name[1:])
      func = getattr(self, funcName)
      print "** Calling {}".format(funcName)
      result = func(iteration=iteration)
      self._state[name] = result
      return result

  # None of the "_conjureXXX" functions below are directly called. They are all
  # called via string name by the _getSnapshot function, depending on what type
  # of snapshot data is being requested. They are called "conjureXXX" because
  # we won't really be sure where the information is coming from until the
  # function is called. It could come from the SpFacade instance, the
  # SpatialPooler instance, or Redis. It depends on whether the facade is active
  # or not, and whether an iteration is specified. In all cases where an
  # iteration in the past is specified, Redis will be the data source.


  def _conjureActiveCells(self, iteration=None):
    if self._retrieveFromAlgorithm(iteration):
      print "** getting active cells from TM instance"
      out = self._tm.getActiveCells()
    else:
      print "** getting active cells from Redis"
      out = self._redisClient.getLayerStateByIteration(
        self.getId(), SNAPS.ACT_CELLS, iteration
      )
    return out


  def _conjurePredictiveCells(self, iteration=None):
    if self._retrieveFromAlgorithm(iteration):
      print "** getting active cells from TM instance"
      out = self._tm.getPredictiveCells()
    else:
      print "** getting active cells from Redis"
      out = self._redisClient.getLayerStateByIteration(
        self.getId(), SNAPS.PRD_CELLS, iteration
      )
    return out


  def _conjureActiveSegments(self, iteration=None):
    if self._retrieveFromAlgorithm(iteration):
      print "** getting active segments from TM instance"
      out = [self._segmentToDict(c) for c in self._tm.getActiveSegments()]
    else:
      raise Exception('REDIS storage of active segments is not implemented');
      # print "** getting active segments from Redis"
      # out = self._ioClient.getLayerStateByIteration(
      #   self.getId(), SNAPS.ACT_SEGS, iteration
      # )
    return out
