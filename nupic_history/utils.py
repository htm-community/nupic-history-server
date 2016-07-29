
def compressSdr(sdr):
  return {
    "length": len(sdr),
    "indices": [i for i, bit in enumerate(sdr) if bit]
  }
