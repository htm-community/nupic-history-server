from random import random
import time

import numpy as np

from nupic.research.spatial_pooler import SpatialPooler as SP

from nupic_history import SpHistory, SpSnapshots


spHistory = SpHistory()


def runSaveTest():
  inputSize = 600
  outputSize = 2048

  sp = SP(
    inputDimensions=(inputSize,),
    columnDimensions=(outputSize,),
    potentialRadius=16,
    potentialPct=0.85,
    globalInhibition=True,
    localAreaDensity=-1.0,
    numActiveColumnsPerInhArea=40.0,
    stimulusThreshold=1,
    synPermInactiveDec=0.008,
    synPermActiveInc=0.05,
    synPermConnected=0.10,
    minPctOverlapDutyCycle=0.001,
    minPctActiveDutyCycle=0.001,
    dutyCyclePeriod=1000,
    maxBoost=2.0,
    seed=-1,
    spVerbosity=0,
    wrapAround=True
  )
  # Totally nukes any SP History data that exists in Redis.
  spHistory.nuke()
  # Create a facade around the SP that saves history as it runs.
  sp = spHistory.create(sp)
  # If the SP Facade is "active" that means it has a life spatial pooler. If it
  # is not active, it cannot compute, only playback the history.
  assert sp.isActive()

  start = time.time()

  iterations = 10
  for _ in range(0, iterations):
    encoding = np.zeros(shape=(inputSize,))
    for j, _ in enumerate(encoding):
      if random() < 0.1:
        encoding[j] = 1
    # For each compute cycle, save the SP state to Redis for playback later.
    sp.compute(encoding, learn=True, save=True)

  end = time.time()

  print "\nSTORAGE: {} iterations took {} seconds.\n\n".format(iterations, (end - start))

  # This SP's history can be retrieved with an id.
  return sp.getId()


def runFetchTest(spid):
  print "Fetching sp {}".format(spid)
  sp = spHistory.get(spid)
  # This one is not active, but just an interface for retrieving the state of
  # the SP when it was active.
  assert not sp.isActive()

  try:
    sp.save()
  except RuntimeError:
    print "Can't save inactive facade."

  start = time.time()

  # We can playback the life of the SP.
  for i in range(0, sp.getIteration() + 1):
    print "\niteration {}".format(i)
    print sp.getState(SpSnapshots.INPUT, iteration=i).keys()
    print sp.getState(SpSnapshots.ACT_COL, iteration=i).keys()
    print sp.getState(SpSnapshots.POT_POOLS, iteration=i).keys()
    print sp.getState(SpSnapshots.OVERLAPS, iteration=i).keys()
    print sp.getState(SpSnapshots.PERMS, iteration=i).keys()
    print sp.getState(SpSnapshots.ACT_DC, iteration=i).keys()
    print sp.getState(SpSnapshots.OVP_DC, iteration=i).keys()
    print sp.getState(SpSnapshots.CON_SYN, iteration=i).keys()

  end = time.time()
  print "\nRETRIEVAL: {} iterations took {} seconds.".format(sp.getIteration(), (end - start))

if __name__ == "__main__":
  spid = runSaveTest()
  runFetchTest(spid)
