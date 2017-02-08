from nupic_history.sp_facade import SpFacade
from nupic_history.tm_facade import TmFacade
from nupic_history.io_client import FileIoClient

from nupic_history import SpSnapshots as SNAPS

class NupicHistory(object):


  def __init__(self, ioClient):
    """
    Provides top-level control over the SP History Facades.
    """
    self._ioClient = ioClient


  def getColumnHistory(self, spId, columnIndex, states):
    out = {}
    for state in states:
      out[state] = []

    for iteration in xrange(self._ioClient.getMaxIteration(spId)):
      spFacade = SpFacade(spId, self._ioClient, iteration=iteration)
      spFacade.load()
      print spFacade._activeColumns
      for state in states:
        # Column activity only needs to be returned for the specified column.
        myState = spFacade.getState(state)[state]
        if state == SNAPS.ACT_COL:
          isActive = columnIndex in myState["indices"]
          if isActive:
            isActive = 1
          else:
            isActive = 0
          out[state].append(isActive)
        else:
          out[state].append(myState[columnIndex])

    return out


  def nuke(self):
    """
    Removes all traces of NuPIC History from Redis.
    :return:
    """
    self._ioClient.nuke(flush=True)
