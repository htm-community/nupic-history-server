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
