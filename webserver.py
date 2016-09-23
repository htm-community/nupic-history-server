import time
import simplejson as json

import numpy as np
import web

from nupic.research.spatial_pooler import SpatialPooler as SP
from nupic.research.temporal_memory import TemporalMemory as TM

from nupic_history import NupicHistory
from nupic_history import SpSnapshots as SP_SNAPS
from nupic_history import TmSnapshots as TM_SNAPS

global spFacades
spFacades = {}
tmFacades = {}
nupicHistory = NupicHistory()

urls = (
  "/", "Index",
  "/_sp/", "SpInterface",
  "/_sp/(.+)/history/(.+)", "SpHistory",
  "/_tm/", "TmInterface",
)
web.config.debug = False
app = web.application(urls, globals())



class Index:


  def GET(self):
    return "NuPIC History Server"


class SpInterface:


  def POST(self):
    global spFacades
    params = json.loads(web.data())
    requestInput = web.input()
    # We will always return the initial state of columns and overlaps because
    # they are cheap.
    returnSnapshots = [
      SP_SNAPS.ACT_COL,
      SP_SNAPS.OVERLAPS
    ]
    saveSnapshots = []
    if __name__ == '__main__':
      if "save" in requestInput and len(requestInput["save"]) > 0:
        saveSnapshots += [str(s) for s in requestInput["save"].split(",")]
        # Be sure to also return any snapshots that were specified to be saved.
        returnSnapshots += saveSnapshots
        # Remove potential duplicates from both
        returnSnapshots = list(set(returnSnapshots))
        saveSnapshots = list(set(saveSnapshots))
    # from pprint import pprint; pprint(params);
    sp = SP(**params)
    spFacade = nupicHistory.createSpFacade(sp, save=saveSnapshots)
    modelId = spFacade.getId()
    spFacades[modelId] = spFacade

    print "Created SP {} | Saving: {}".format(modelId, saveSnapshots)

    payload = {
      "meta": {
        "id": modelId,
        "saving": returnSnapshots
      }
    }
    spState = spFacade.getState(*returnSnapshots)
    for key in spState:
      payload[key] = spState[key]

    web.header("Content-Type", "application/json")
    return json.dumps(payload)


  def PUT(self):
    requestStart = time.time()
    requestInput = web.input()
    encoding = web.data()
    stateSnapshots = [
      SP_SNAPS.ACT_COL,
    ]

    for snap in SP_SNAPS.listValues():
      getString = "get{}{}".format(snap[:1].upper(), snap[1:])
      if getString in requestInput and requestInput[getString] == "true":
        stateSnapshots.append(snap)

    if "id" not in requestInput:
      print "Request must include a model id."
      return web.badrequest()

    modelId = requestInput["id"]

    if modelId not in spFacades.keys():
      print "Unknown SP id {}!".format(modelId)
      return web.badrequest()

    sp = spFacades[modelId]

    learn = True
    if "learn" in requestInput:
      learn = requestInput["learn"] == "true"

    inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering SP {} compute cycle | Learning: {}".format(modelId, learn)
    sp.compute(inputArray, learn=learn)

    response = sp.getState(*stateSnapshots)

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    requestEnd = time.time()
    print("\tSP compute cycle took %g seconds" % (requestEnd - requestStart))

    return jsonOut



class SpHistory:

  def GET(self, modelId, columnIndex):
    """
    Returns entire history of SP for given column
    """
    sp = spFacades[modelId]
    history = sp.getState(
      SP_SNAPS.PERMS, SP_SNAPS.ACT_COL, columnIndex=int(columnIndex)
    )
    return json.dumps(history)



class TmInterface:


  def POST(self):
    global tmFacades
    params = json.loads(web.data())
    requestInput = web.input()
    # We will always return the active cells because they are cheap.
    returnSnapshots = [TM_SNAPS.ACT_CELLS]
    saveSnapshots = []
    if __name__ == '__main__':
      if "save" in requestInput and len(requestInput["save"]) > 0:
        saveSnapshots += [str(s) for s in requestInput["save"].split(",")]
        # Be sure to also return any snapshots that were specified to be saved.
        returnSnapshots += saveSnapshots
        # Remove potential duplicates from both
        returnSnapshots = list(set(returnSnapshots))
        saveSnapshots = list(set(saveSnapshots))
    from pprint import pprint; pprint(params)
    tm = TM(**params)
    tmFacade = nupicHistory.createTmFacade(
      tm, save=saveSnapshots, modelId=requestInput["id"]
    )
    modelId = tmFacade.getId()
    tmFacades[modelId] = tmFacade

    print "Created TM {} | Saving: {}".format(modelId, saveSnapshots)

    payload = {
      "meta": {
        "id": modelId,
        "saving": returnSnapshots
      }
    }
    tmState = tmFacade.getState(*returnSnapshots)
    for key in tmState:
      payload[key] = tmState[key]

    web.header("Content-Type", "application/json")
    return json.dumps(payload)


  def PUT(self):
    requestStart = time.time()
    requestInput = web.input()
    encoding = web.data()
    stateSnapshots = [
      TM_SNAPS.ACT_CELLS,
      TM_SNAPS.PRD_CELLS,
    ]

    for snap in TM_SNAPS.listValues():
      getString = "get{}{}".format(snap[:1].upper(), snap[1:])
      if getString in requestInput and requestInput[getString] == "true":
        stateSnapshots.append(snap)

    if "id" not in requestInput:
      print "Request must include a model id."
      return web.badrequest()

    modelId = requestInput["id"]

    if modelId not in tmFacades.keys():
      print "Unknown model id {}!".format(modelId)
      return web.badrequest()

    tm = tmFacades[modelId]

    learn = True
    if "learn" in requestInput:
      learn = requestInput["learn"] == "true"
    reset = False
    if "reset" in requestInput:
      reset = requestInput["reset"] == "true"

    inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering TM {} compute cycle | Learning: {}".format(modelId, learn)
    tm.compute(inputArray.tolist(), learn=learn)

    response = tm.getState(*stateSnapshots)

    if reset:
      print "Resetting TM."
      tm.reset()

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    requestEnd = time.time()
    print("\tTM compute cycle took %g seconds" % (requestEnd - requestStart))

    return jsonOut



if __name__ == "__main__":
  app.run()
