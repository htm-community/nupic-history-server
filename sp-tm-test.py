from random import random
import time

import numpy as np

from nupic.research.spatial_pooler import SpatialPooler as SP

from nupic_history import SpHistory, SpSnapshots as SNAPS


spHistory = SpHistory()
iterations = 10


def createSpatialPooler(inputSize):
  return SP(
    inputDimensions=(inputSize,),
    columnDimensions=(200,),
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


def runSaveTest():
  spHistory.nuke()

  inputSize = 3

  rawSp = createSpatialPooler(inputSize)

  sp = spHistory.create(
    rawSp,
    # Declaring what internal data should for each compute cycle.
    save=[
      SNAPS.INPUT,
      SNAPS.ACT_COL,
      SNAPS.CON_SYN,
      SNAPS.PERMS,
      SNAPS.OVERLAPS,
      SNAPS.ACT_DC,
      SNAPS.OVP_DC,
      SNAPS.POT_POOLS,
    ]
  )

  start = time.time()


  for _ in range(0, iterations):
    encoding = np.zeros(shape=(inputSize,))
    for j, _ in enumerate(encoding):
      if random() < 0.1:
        encoding[j] = 1
    # For each compute cycle, save the SP state to Redis for playback later.
    sp.compute(encoding, learn=True)

  end = time.time()

  print "\nSTORAGE: {} iterations took {} seconds.\n\n".format(iterations, (end - start))

  return sp


def retrieveByIteration(sp):
  start = time.time()
  iterations = sp.getIteration() + 1
  # We can playback the life of the SP.
  for i in range(0, iterations):
    print "iteration {}".format(i)
    for snap in [SNAPS.INPUT, SNAPS.ACT_COL]:
      state = sp.getState(snap, iteration=i)[snap]
      print "\t{} has {} active bits out of {}".format(snap,
                                                       len(state["indices"]),
                                                       state["length"])
    for snap in [SNAPS.POT_POOLS, SNAPS.OVERLAPS, SNAPS.PERMS, SNAPS.CON_SYN,
                 SNAPS.ACT_DC, SNAPS.OVP_DC]:
      print "\t{} for {} columns".format(snap, len(
        sp.getState(snap, iteration=i)[snap]))
  end = time.time()
  print "\nRETRIEVAL: {} iterations took {} seconds.".format(
    iterations, (end - start)
  )


def retrieveSnapshotByColumn(snapshot, sp, column):
  start = time.time()
  # We can playback the life of one column.
  data = sp.getState(snapshot, columnIndex=column)[snapshot]
  end = time.time()
  print "\nRETRIEVAL of column {} {} ({} iterations) took {} seconds.".format(
    column, snapshot, sp.getIteration(), (end - start)
  )
  return data


def runFetchTest(sp):
  spid = sp.getId()
  print "Fetching sp {}".format(spid)
  sp = spHistory.get(spid)
  history = sp.getState(
    SNAPS.PERMS, SNAPS.CON_SYN, columnIndex=0
  )
  print history
  # retrieveByIteration(sp)
  # columnHistory = retrieveSnapshotByColumn(SNAPS.PERMS, sp, 0)
  # assert len(columnHistory) == iterations


def runHistoryTest():
  sp = runSaveTest()
  time.sleep(1)
  history = sp.getState(
    SNAPS.PERMS, SNAPS.ACT_COL, columnIndex=199
  )
  print history


if __name__ == "__main__":
  runHistoryTest()
  # spid = runSaveTest()
  # time.sleep(5)
  # runFetchTest(spid)
