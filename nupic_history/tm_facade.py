import uuid
import multiprocessing
import time
import numpy as np

from nupic_history import TmSnapshots as SNAPS

class TmFacade(object):

  def __init__(self, tm, ioClient, modelId=None, iteration=None):
    self._ioClient = ioClient
    if isinstance(tm, basestring):
      # Loading TM by id from IO.
      self._id = tm
      # Get the latest by default.
      if iteration is None:
        iteration = ioClient.getMaxIteration(self._id)
      self._iteration = iteration
    else:
      if modelId is not None:
        # There is already an SP for this TM with the same ID.
        self._id = modelId
        self._tm = tm
      else:
        # New facade using given fresh TM
        self._tm = tm
        self._id = str(uuid.uuid4()).split('-')[0]
      self._iteration = 0

    self._state = None
    self._input = None
    self._save = None


  def __str__(self):
    return "TM {} has seen {} iterations".format(
      self.getId(), self.getIteration()
    )


  def save(self):
    ioClient = self._ioClient
    id = self.getId()
    iteration = self.getIteration()
    ioClient.saveTemporalMemory(self._tm, id, iteration)


  def load(self):
    ioClient = self._ioClient
    id = self.getId()
    iteration = self.getIteration()
    print "Loading TM {} at iteration {}".format(id, iteration)
    self._tm = ioClient.loadTemporalMemory(
      id, iteration=iteration
    )


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
    self._state = None
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
      self._ioClient.saveTmState(modelId, params, iteration, state)


  def getParams(self):
    """
    Utility to collect the SP params used at creation into a dict.
    :return: [dict] parameters
    """
    tm = self._tm
    if tm is None:
      params =self._ioClient.getTmParams(self.getId())
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


  def _segmentToDict(self, segment, connections):
    return {
      "cell": connections.cellForSegment(segment),
      "synapses": [
        self._synapseToDict(s, connections)
        for s in connections.synapsesForSegment(segment)
      ],
    }


  def _synapseToDict(self, synapse, connections):
    synapseData = connections.dataForSynapse(synapse)
    return {
      "presynapticCell": synapseData.presynapticCell,
      "permanence": synapseData.permanence,
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


  def _conjureActiveCells(self, **kwargs):
    return self._tm.getActiveCells()


  def _conjurePredictiveCells(self, **kwargs):
    return self._tm.getPredictiveCells()


  def _conjureActiveSegments(self, **kwargs):
    return [
      self._segmentToDict(c, self._tm.connections)
      for c in self._tm.getActiveSegments()
      ]
