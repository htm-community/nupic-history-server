from random import random

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
  spHistory.nuke()
  shim = spHistory.create(sp)
  assert shim.isActive()
  for i in range(2):
    input = np.zeros(shape=(inputSize,))
    for j, _ in enumerate(input):
      if random() < 0.1:
        input[j] = 1
    shim.compute(input, learn=True)
    shim.save()
  return shim.getId()


def runFetchTest(spid):
  print "Fetching sp {}".format(spid)
  shim = spHistory.get(spid)
  assert not shim.isActive()
  for i in range(0, shim.getIteration()):
    print "iteration {}".format(i)
    print shim.getState(SpSnapshots.INPUT, iteration=i)
    print shim.getState(SpSnapshots.ACT_COL, iteration=i)


if __name__ == "__main__":
  spid = runSaveTest()
  runFetchTest(spid)
