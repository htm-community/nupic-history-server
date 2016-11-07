import inspect


class Snapshots(object):
  """
  This is kindof an Enum. Used to enumerate the different data snapshots the
  SpFacades make available.
  """

  @classmethod
  def listKeys(cls):
    return cls._listBy("key")


  @classmethod
  def listValues(cls):
    return cls._listBy("value")


  @classmethod
  def contains(cls, item):
    return item in cls.listValues()


  @classmethod
  def _listBy(cls, choose):
    index = 1
    if choose == "key":
      index = 0
    attributes = inspect.getmembers(cls, lambda a: not inspect.isroutine(a))
    return [
      a[index] for a in attributes
      if not (a[0].startswith('__') and a[0].endswith('__'))
    ]



class SpSnapshots(Snapshots):

  INPUT = "input"
  POT_POOLS = "potentialPools"
  CON_SYN = "connectedSynapses"
  PERMS = "permanences"
  ACT_COL = "activeColumns"
  OVERLAPS = "overlaps"
  ACT_DC = "activeDutyCycles"
  OVP_DC = "overlapDutyCycles"
  INH_MASKS = "inhibitionMasks"




class TmSnapshots(Snapshots):

  ACT_CELLS = "activeCells"
  PRD_CELLS = "predictiveCells"
