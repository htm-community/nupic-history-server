import numpy as np


def compressSdr(sdr):
  return {
    "length": len(sdr),
    "indices": [i for i, bit in enumerate(sdr) if bit]
  }


def decompressSdr(sdr, name):
  length = sdr[name]["length"]
  out = np.zeros(length)
  for index in sdr[name]["indices"]:
    out[index] = 1
  return out


def calculateRadius(point1, point2):
  # print "Calculating distance between points:"
  # print point1
  # print point2
  if point1 is None:
    return 10
  p1 = np.array(point1["location"])
  p2 = np.array(point2["location"])
  dist = np.linalg.norm(p1 - p2)
  time_delta = point2["time"] - point1["time"]
  # print "dist: %f" % dist
  # print "time delta: %i" % time_delta
  unitsPerSecond = (dist / time_delta)
  unitsPerSecond = int(round(unitsPerSecond))
  # print "units per second: %f" % unitsPerSecond
  return unitsPerSecond


def radiusForSpeed(self, speed):
  """
  Returns radius for given speed.

  Tries to get the encodings of consecutive readings to be
  adjacent with some overlap.

  @param speed (float) Speed (in units per second)
  @return (int) Radius for given speed
  """
  overlap = 1.5
  coordinatesPerTimestep = speed * self.timestep / self.scale
  radius = int(round(float(coordinatesPerTimestep) / 2 * overlap))
  minRadius = int(math.ceil((math.sqrt(self.w) - 1) / 2))
  return max(radius, minRadius)
