import numpy as np

import redis

from nupic.research.spatial_pooler import SpatialPooler as SP

from npc_history import SpHistory, SpSnapshots

def runTest():
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

  shim = SpHistory(sp, redis=redis.Redis("localhost"))

  input = np.random.randint(2, size=inputSize)

  for i in range(10):
    shim.compute(input)
    shim.save()



if __name__ == "__main__":
  runTest()
